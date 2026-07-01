import dataclasses
import logging
import time

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lesson import Lesson, LessonStep, LessonStatus, StepType
from app.models.quiz import Quiz, QuizQuestion
from app.models.ai_request import AIRequest, AIRequestStatus
from app.models.child import Child
from app.models.topic import Topic
from app.models.subject import Subject
from app.schemas.lesson import AILessonResponse
from app.services.gigachat import generate_lesson_raw
from app.services.gamification import update_streak, check_and_award_achievements, update_subject_progress
from app.services.lesson_validator import (
    validate_lesson, apply_auto_fixes, build_retry_hint, ValidationResult
)

logger = logging.getLogger(__name__)

DIFFICULTY_NAMES = {1: "лёгкий", 2: "средний", 3: "сложный"}

STEP_TYPE_MAP = {
    "explain": ("explain", None),
    "game": ("game", "multiple_choice"),
    "multiple_choice": ("game", "multiple_choice"),
    "fill_blank": ("game", "fill_blank"),
    "match_pairs": ("game", "match_pairs"),
    "sort_items": ("game", "sort_items"),
}

MAX_RETRIES = 3


def _build_prompt(child: Child, topic: Topic, subject: Subject, difficulty: int,
                  retry_hint: str | None = None) -> str:
    difficulty_name = DIFFICULTY_NAMES.get(difficulty, "средний")

    base = f"""Ты создаёшь интерактивный урок для ребёнка {child.age} лет ({child.grade} класс).
Тема: "{topic.title}". Предмет: {subject.name}. Сложность: {difficulty_name}.

ИНТЕРФЕЙС ТЕКСТОВЫЙ: никаких картинок, изображений, схем нет.

ТИПЫ ШАГОВ (чередуй, не более 2 подряд "explain"):
- explain: текстовое объяснение концепции
- multiple_choice: выбор из вариантов (3 варианта, correct_index = 0/1/2)
- fill_blank: вписать пропущенное слово (текст с ___ на месте пропуска)
- match_pairs: соотнести левый и правый столбец (минимум 3 пары)
- sort_items: расставить элементы в правильном порядке

ДЛЯ КАЖДОГО ШАГА НЕ "explain" ОБЯЗАТЕЛЬНО добавить:
- "feedback_correct": 1-2 предложения почему ответ верный, дружелюбно
- "feedback_wrong": наводящая подсказка без раскрытия ответа
- "hint": краткая подсказка для второй попытки

ПРАВИЛА для "multiple_choice":
• task = один чёткий вопрос. options = 3 коротких текстовых ответа.
• correct_index = ИНДЕКС правильного ответа в массиве options, НАЧИНАЯ С НУЛЯ (0-based).
  Если правильный ответ ПЕРВЫЙ в options — correct_index = 0.
  Если ВТОРОЙ — correct_index = 1. Если ТРЕТИЙ — correct_index = 2.
  НИКОГДА не ставь correct_index = текст ответа или число больше 2.
  ОБЯЗАТЕЛЬНО проверь математику: вычисли выражение вручную и убедись что options[correct_index] содержит верный ответ.

ПРАВИЛА для "fill_blank":
• question = обязательная инструкция, что нужно сделать (например: "Вставь пропущенное слово", "Найди пропущенное число")
• text = предложение с ___ на месте пропуска (строго три подчёркивания: ___)
• Если пропуск ОДИН: correct_answers = плоский массив вариантов: ["ответ", "Ответ"]
• Если пропусков НЕСКОЛЬКО: correct_answers = массив массивов, по одному на каждый пропуск:
  [["ответ1", "Ответ1"], ["ответ2", "Ответ2"]]
• Количество элементов в correct_answers ДОЛЖНО совпадать с количеством ___ в text.
  ОБЯЗАТЕЛЬНО проверь математику: вычисли выражение вручную перед тем как записать correct_answers.

ПРАВИЛА для "match_pairs":
• pairs = [{{"left": "...", "right": "..."}}] — не менее 3 пар

ПРАВИЛА для "sort_items":
• instruction = что нужно расположить
• items = элементы в ПРОИЗВОЛЬНОМ порядке
• correct_order = правильный порядок тех же элементов (должен содержать ровно те же элементы что items)

ПРАВИЛА для quiz: ОБЯЗАТЕЛЬНО 3-4 вопроса.
• correct = ИНДЕКС правильного ответа в массиве options, НАЧИНАЯ С НУЛЯ (0-based).
  correct = 0 если первый вариант верный, correct = 1 если второй, correct = 2 если третий.
  НИКОГДА не пиши в correct сам текст ответа или число больше 2.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков. Пример структуры:

{{
  "title": "Название урока",
  "age_band": "{child.age}-{child.age + 1}",
  "goal": "Цель урока",
  "story_intro": "Вступительная история",
  "steps": [
    {{
      "type": "explain",
      "title": "Как это работает",
      "content": "Объяснение концепции..."
    }},
    {{
      "type": "multiple_choice",
      "title": "Проверь себя",
      "task": "Сколько будет 45 + 27?",
      "options": ["72", "52", "63"],
      "correct_index": 0,
      "feedback_correct": "Верно! 45+27=72.",
      "feedback_wrong": "Сначала сложи единицы: 5+7=12.",
      "hint": "Считай по частям: сначала единицы, потом десятки."
    }},
    {{
      "type": "fill_blank",
      "title": "Заполни пропуск",
      "question": "Вставь пропущенное слово:",
      "text": "Число, на которое делим, называется ___.",
      "correct_answers": ["делитель", "Делитель"],
      "feedback_correct": "Правильно! Делитель — это число, на которое делят.",
      "feedback_wrong": "Вспомни термины деления.",
      "hint": "Де-ли-тель."
    }}
  ],
  "quiz": [
    {{"question": "Вопрос?", "options": ["А", "Б", "В"], "correct": 0, "explanation": "Объяснение."}},
    {{"question": "Вопрос 2?", "options": ["А", "Б", "В"], "correct": 1, "explanation": "Объяснение."}}
  ],
  "reward": {{"xp": 20, "badge_candidate": null}}
}}

Теперь создай урок по теме "{topic.title}" для ребёнка {child.age} лет в том же формате JSON:"""

    if retry_hint:
        base += f"\n\nИСПРАВЬ СЛЕДУЮЩИЕ ОШИБКИ ИЗ ПРЕДЫДУЩЕГО ОТВЕТА:\n{retry_hint}"

    return base


def _build_step_data(step) -> dict | None:
    if step.type == "fill_blank":
        data: dict = {"correct_answers": step.correct_answers or []}
        if step.question:
            data["question"] = step.question
        return data
    if step.type == "match_pairs":
        return {"pairs": step.pairs or []}
    if step.type == "sort_items":
        return {
            "instruction": step.instruction or step.task or "",
            "items": step.items or [],
            "correct_order": step.correct_order or [],
        }
    return None


async def generate_and_save_lesson(
    child_id: int,
    topic_id: int,
    difficulty: int,
    db: AsyncSession,
) -> Lesson:
    child_result = await db.execute(select(Child).where(Child.id == child_id))
    child = child_result.scalar_one_or_none()
    if not child:
        raise ValueError(f"Child {child_id} not found")

    topic_result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = topic_result.scalar_one_or_none()
    if not topic:
        raise ValueError(f"Topic {topic_id} not found")

    subject_result = await db.execute(select(Subject).where(Subject.id == topic.subject_id))
    subject = subject_result.scalar_one_or_none()

    lesson = Lesson(
        title=f"Урок: {topic.title}",
        age_band=f"{child.age}-{child.age+1}",
        status=LessonStatus.generating,
        child_id=child_id,
        topic_id=topic_id,
        generation_attempts=0,
    )
    db.add(lesson)
    await db.flush()

    retry_hint: str | None = None
    last_val_result: ValidationResult | None = None

    for attempt_num in range(1, MAX_RETRIES + 1):
        ai_request = AIRequest(
            lesson_id=lesson.id,
            status=AIRequestStatus.pending,
            attempt_number=attempt_num,
        )
        db.add(ai_request)
        await db.flush()

        prompt = _build_prompt(child, topic, subject, difficulty, retry_hint)
        start_time = time.monotonic()

        # ── 1. Call GigaChat ──────────────────────────────────────────────
        try:
            raw_response = await generate_lesson_raw(prompt)
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            ai_request.status = AIRequestStatus.failed
            ai_request.error_message = str(e)[:500]
            ai_request.duration_ms = duration_ms
            await db.flush()
            logger.warning("GigaChat call failed (attempt %d/%d): %s", attempt_num, MAX_RETRIES, e)
            if attempt_num == MAX_RETRIES:
                lesson.status = LessonStatus.failed
                lesson.generation_attempts = attempt_num
                await db.flush()
                raise
            continue

        duration_ms = int((time.monotonic() - start_time) * 1000)
        ai_request.duration_ms = duration_ms

        # ── 2. Validate raw response ──────────────────────────────────────
        val_result = validate_lesson(raw_response)
        last_val_result = val_result
        fixed_raw = apply_auto_fixes(raw_response, val_result.auto_fixed)

        ai_request.validation_result = val_result.to_dict()
        ai_request.auto_fixed_log = [dataclasses.asdict(f) for f in val_result.auto_fixed]

        blocking = [e for e in val_result.errors if e.severity in ('critical', 'major')]

        if blocking and attempt_num < MAX_RETRIES:
            retry_hint = build_retry_hint(blocking)
            ai_request.status = AIRequestStatus.invalid_response
            ai_request.error_message = f"Validation: {len(blocking)} blocking errors"
            await db.flush()
            logger.warning("Lesson validation failed (attempt %d/%d), retrying: %s",
                           attempt_num, MAX_RETRIES,
                           [f"{e.field}:{e.message}" for e in blocking])
            continue

        # ── 3. Pydantic validation ────────────────────────────────────────
        try:
            lesson_data = AILessonResponse.model_validate(fixed_raw)
        except (ValidationError, ValueError, KeyError) as e:
            ai_request.status = AIRequestStatus.invalid_response
            ai_request.error_message = str(e)[:500]
            await db.flush()
            logger.warning("Pydantic validation failed (attempt %d/%d): %s", attempt_num, MAX_RETRIES, e)
            if attempt_num < MAX_RETRIES:
                retry_hint = (retry_hint or '') + f"\nИсправь структуру JSON: {str(e)[:300]}"
                continue
            # Final attempt — save as needs_review
            lesson.status = LessonStatus.needs_review
            lesson.generation_attempts = attempt_num
            lesson.validation_errors = [{"field": "schema", "message": str(e)[:500], "severity": "critical"}]
            await db.flush()
            raise ValueError(f"Урок требует ручной проверки после {MAX_RETRIES} попыток") from e

        # ── 4. Final blocking check (last attempt) ────────────────────────
        if blocking:
            ai_request.status = AIRequestStatus.invalid_response
            ai_request.error_message = f"Final attempt: {len(blocking)} validation errors remain"
            lesson.status = LessonStatus.needs_review
            lesson.generation_attempts = attempt_num
            lesson.validation_errors = [dataclasses.asdict(e) for e in blocking]
            await db.flush()
            logger.error("Lesson %d needs review after %d attempts", lesson.id, attempt_num)
            raise ValueError(f"Урок требует ручной проверки после {attempt_num} попыток")

        # ── 5. SUCCESS — save to DB ───────────────────────────────────────
        ai_request.status = AIRequestStatus.success

        lesson.title = lesson_data.title
        lesson.age_band = lesson_data.age_band
        lesson.goal = lesson_data.goal
        lesson.story_intro = lesson_data.story_intro
        lesson.xp_reward = lesson_data.reward.xp
        lesson.badge_candidate = lesson_data.reward.badge_candidate
        lesson.raw_ai_response = raw_response
        lesson.status = LessonStatus.ready
        lesson.generation_attempts = attempt_num

        for i, step in enumerate(lesson_data.steps):
            db_step_type_str, db_step_subtype = STEP_TYPE_MAP.get(step.type, ("explain", None))

            task_val = None
            if step.type in ("game", "multiple_choice"):
                task_val = step.task
            elif step.type == "fill_blank":
                task_val = step.text or step.task
            elif step.type == "sort_items":
                task_val = step.instruction or step.task

            lesson_step = LessonStep(
                lesson_id=lesson.id,
                sort_order=i,
                step_type=StepType(db_step_type_str),
                step_subtype=db_step_subtype,
                title=step.title or "Шаг",
                content=step.content if step.type == "explain" else (step.explanation or step.feedback_correct),
                task=task_val,
                options=step.options,
                correct_option_index=step.correct_index,
                feedback_correct=step.feedback_correct,
                feedback_wrong=step.feedback_wrong,
                hint=step.hint,
                step_data=_build_step_data(step),
            )
            db.add(lesson_step)

        quiz = Quiz(lesson_id=lesson.id)
        db.add(quiz)
        await db.flush()

        for i, q in enumerate(lesson_data.quiz):
            question = QuizQuestion(
                quiz_id=quiz.id,
                sort_order=i,
                question=q.question,
                options=q.options,
                correct_index=q.correct,
                explanation=q.explanation,
            )
            db.add(question)

        await update_streak(child)
        child.xp += lesson_data.reward.xp
        if subject:
            await update_subject_progress(child_id, subject.id, lesson_data.reward.xp, db)
        new_achievements = await check_and_award_achievements(child, db)

        await db.flush()
        await db.refresh(lesson)
        lesson._new_achievements = new_achievements

        if val_result.auto_fixed:
            logger.info("Lesson %d: %d auto-fixes applied", lesson.id, len(val_result.auto_fixed))
        if val_result.warnings:
            logger.info("Lesson %d: %d warnings", lesson.id, len(val_result.warnings))

        return lesson

    # Should never reach here
    lesson.status = LessonStatus.failed
    await db.flush()
    raise RuntimeError("generate_and_save_lesson: exhausted retry loop unexpectedly")
