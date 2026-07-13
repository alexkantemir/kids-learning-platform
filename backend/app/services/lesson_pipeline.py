"""
generator→verifier pipeline (TASK_STAGE1). Три независимых LLM-вызова вместо
одного: контент → вопросы по контенту → судья, который сам решает ответ и
сверяется с автором вопросов. Устраняет структурную причину брака в quiz
(одна модель одновременно придумывала и вопрос, и "правильный" ответ).

Живёт рядом со старым generate_and_save_lesson (lesson_generator.py), который
остаётся точкой входа до перезамера. Вызовы 1, 2 и 3 (контент, вопросы,
судья) реализованы — сессии 2–3. Интеграция с generate_and_save_lesson —
сессия 4, флагом с возможностью отката.

Где ответ вычислим кодом (арифметика) — код главнее LLM-судьи: см.
check_question_arithmetic/check_content_arithmetic. Истинность словесных
правил в тексте урока, не сводимая к вычислимой арифметике и не создающая
видимого противоречия внутри текста, — ПРИНЯТОЕ ограничение Этапа 1
(решение владельца, TASK_STAGE1_v4.md): судья проверяет непротиворечивость
текста (verify_content_consistency), но не полную фактическую истинность.
Закрывается человеческой вычиткой банка на Этапе 3, не входит в метрику
брака квизов этого этапа.
"""
import ast
import dataclasses
import operator
import re

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.child import Child
from app.models.lesson import Lesson, LessonStatus, LessonStep, StepType
from app.models.quiz import Quiz, QuizQuestion
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.lesson import AILessonResponse
from app.services.gamification import check_and_award_achievements, update_streak, update_subject_progress
from app.services.gigachat import generate_lesson_raw
from app.services.lesson_generator import STEP_TYPE_MAP, _build_step_data

DIFFICULTY_NAMES = {1: "лёгкий", 2: "средний", 3: "сложный"}
MAX_QUESTION_RETRIES = 2  # регенераций сверх первой попытки, на один вопрос

# Единый набор допустимых символов для ОБОИХ регексов ниже (поиск кандидата
# в check_question_arithmetic и "expr = N" в check_content_arithmetic) — один
# источник правды, чтобы скобки не оказались согласованы в одном месте и
# забыты в другом (см. TASK_STAGE1_v4.md, пункт 3 сессии 4).
_ARITH_CHARSET = r'\d.,()+\-*/×÷:−\s'
_ARITH_CHAIN_RE = re.compile(rf'[{_ARITH_CHARSET}]+')
_EXPR_EQUALS_RE = re.compile(
    rf'([{_ARITH_CHARSET}]*\d[{_ARITH_CHARSET}]*)\s*=\s*(-?\d+(?:[.,]\d+)?)'
)
_ARITH_TRANSLATE = str.maketrans({'×': '*', '÷': '/', '−': '-', ':': '/', ',': '.'})
_ARITH_NORMALIZED_RE = re.compile(r'[\d.()+\-*/]+')  # финальный regex-гейт перед ast.parse

# ── AST-белый список: LLM-строка никогда не доходит до eval/exec ───────────
# Разрешены ТОЛЬКО числовые константы и арифметические операции. Любой
# другой узел (Call, Name, Attribute, Subscript, ...) — ValueError, вычисление
# прерывается. Даже если regex-гейт выше когда-нибудь случайно ослабят,
# этот слой не даёт строке превратиться в исполняемый код.
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise ValueError("недопустимая константа в арифметическом выражении")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"недопустимый узел в арифметическом выражении: {type(node).__name__}")


@dataclasses.dataclass
class LessonContent:
    """Результат вызова 1: только обучающий текст, без единого вопроса."""
    title: str
    age_band: str
    goal: str
    story_intro: str
    explain_steps: list[dict]  # [{"title": str, "content": str}, ...]


@dataclasses.dataclass
class DraftQuestion:
    """Результат вызова 2: один вопрос от автора, ещё не проверенный."""
    kind: str  # "step" (интерактивный шаг в теле урока) | "quiz" (итоговый квиз)
    step_type: str | None  # multiple_choice/fill_blank/match_pairs/sort_items; None для quiz
    question: str
    options: list[str] | None
    author_correct_index: int | None
    raw: dict  # исходный dict от LLM — нужен ниже по пайплайну для сборки шага/quiz-записи


@dataclasses.dataclass
class VerifiedQuestion:
    """Результат вызова 3: вердикт судьи, сверенный с автором."""
    draft: DraftQuestion
    accepted: bool
    verifier_correct_index: int | None  # ответ судьи; None если "нет однозначного ответа"
    reason: str | None  # причина отбраковки, если accepted=False


@dataclasses.dataclass
class ContentVerdict:
    """Результат проверки текста урока (вызов 1) на непротиворечивость."""
    consistent: bool
    issues: list[str]


# ── Кодовая проверка арифметики (код главнее LLM там, где применимо) ────────

def _eval_arith_chain(expr: str) -> float | None:
    """Вычисляет арифметическую цепочку БЕЗ eval/exec: regex-нормализация
    (допускает только цифры/точку/скобки/+-*/) — затем ast.parse строит
    дерево выражения, которое обходит _safe_eval_node с белым списком узлов.
    Скобки поддержаны на обоих уровнях согласованно (см. _ARITH_CHARSET) —
    Python сам соблюдает порядок операций и группировку в скобках."""
    normalized = re.sub(r'\s+', '', expr.translate(_ARITH_TRANSLATE))
    if not normalized or not any(c in normalized for c in '+-*/'):
        return None  # без оператора — это не выражение, а голое число
    if not _ARITH_NORMALIZED_RE.fullmatch(normalized):
        return None
    try:
        tree = ast.parse(normalized, mode='eval')
        return _safe_eval_node(tree)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError, OverflowError, RecursionError):
        return None


def check_question_arithmetic(
    question_text: str, options: list[str] | None,
) -> tuple[bool, int | None, float | None]:
    """Если question_text содержит вычислимую арифметическую цепочку
    (учитывает порядок операций и скобки — через ast, не eval, и не одну
    пару число-оператор-число, как было в старом lesson_validator) —
    вычисляет её кодом и ищет совпадающий вариант в options.

    Возвращает (is_arithmetic, correct_index_by_code, expected_value).
    is_arithmetic=False — код не применим, решает судья (вызов 3).

    Важно: код включается, ТОЛЬКО если варианты ответа сами числовые.
    Иначе вопрос может спрашивать не "чему равно выражение", а "в каком
    порядке/почему" (например, про сам порядок операций) — числа в тексте
    вопроса есть, а ответ не является результатом вычисления. Без этой
    проверки код ложно бракует корректные вопросы такого рода (найдено
    живым прогоном в сессии 3 на теме "Порядок действий в примерах")."""
    if not options:
        return False, None, None

    numeric_options: list[float | None] = []
    for opt in options:
        try:
            numeric_options.append(float(str(opt).strip().translate(_ARITH_TRANSLATE)))
        except ValueError:
            numeric_options.append(None)
    if not any(v is not None for v in numeric_options):
        return False, None, None  # варианты не числа — не вопрос "чему равно", код не судья

    # finditer, не search: широкий charset (см. _ARITH_CHARSET) может сперва
    # зацепить тривиальный фрагмент вроде одинокого пробела или скобки перед
    # настоящим выражением — перебираем кандидатов, пока не найдётся тот,
    # что реально вычисляется (есть оператор и валиден по ast).
    expected = None
    for m in _ARITH_CHAIN_RE.finditer(question_text):
        expected = _eval_arith_chain(m.group(0))
        if expected is not None:
            break
    if expected is None:
        return False, None, None

    correct_idx = None
    for i, val in enumerate(numeric_options):
        if val is not None and abs(val - expected) < 0.001:
            correct_idx = i
            break
    return True, correct_idx, expected


def check_content_arithmetic(content: LessonContent) -> list[dict]:
    """Проверяет кодом все выражения вида 'X op Y ... = N' внутри текста
    урока (вызов 1) — например, "7 + 4 * 2 = 15" в объяснении. Возвращает
    список найденных несовпадений (пусто = арифметика в тексте верна)."""
    problems: list[dict] = []
    for step in content.explain_steps:
        text = step.get("content") or ""
        for m in _EXPR_EQUALS_RE.finditer(text):
            expr_str, claimed_str = m.group(1), m.group(2)
            expected = _eval_arith_chain(expr_str)
            if expected is None:
                continue
            claimed = float(claimed_str.replace(',', '.'))
            if abs(expected - claimed) > 0.001:
                problems.append({
                    "step_title": step.get("title") or "",
                    "expression": expr_str.strip(),
                    "claimed": claimed,
                    "expected": expected,
                })
    return problems


async def generate_lesson_content(
    child: Child, topic: Topic, subject: Subject, difficulty: int,
) -> LessonContent:
    """Вызов 1 — генератор контента. Только текст урока, без вопросов."""
    prompt = _build_content_prompt(child, topic, subject, difficulty)
    raw = await generate_lesson_raw(prompt)
    return _parse_content(raw)


async def generate_questions(content: LessonContent) -> list[DraftQuestion]:
    """Вызов 2 — генератор вопросов строго по тексту из вызова 1."""
    prompt = _build_questions_prompt(content)
    raw = await generate_lesson_raw(prompt)
    return _parse_questions(raw)


async def verify_question(content: LessonContent, question: DraftQuestion) -> VerifiedQuestion:
    """Вызов 3 — судья. Видит текст урока + вопрос + варианты БЕЗ пометки
    правильного, сам решает ответ. Где ответ вычислим кодом (арифметика) —
    код главнее судьи, LLM вообще не вызывается (быстрее и не может
    ошибиться там, где есть точный расчёт)."""
    is_arith, code_idx, expected = check_question_arithmetic(question.question, question.options)
    if is_arith:
        accepted = code_idx is not None and code_idx == question.author_correct_index
        reason = None
        if not accepted:
            reason = (
                f"Код вычислил {expected:g} — это options[{code_idx}]."
                if code_idx is not None
                else f"Код вычислил {expected:g}, такого варианта нет среди options."
            )
        return VerifiedQuestion(draft=question, accepted=accepted,
                                verifier_correct_index=code_idx, reason=reason)

    prompt = _build_verifier_prompt(content, question)
    raw = await generate_lesson_raw(prompt)
    return _parse_verdict(question, raw)


async def verify_content_consistency(content: LessonContent) -> ContentVerdict:
    """Судья проверяет текст урока (вызов 1) на внутренние противоречия и
    явные фактические ошибки в правилах — независимо от квиза (решение
    владельца по итогам сессии 2, TASK_STAGE1_v4.md)."""
    prompt = _build_consistency_prompt(content)
    raw = await generate_lesson_raw(prompt)
    return _parse_consistency(raw)


async def _regenerate_single_question(
    content: LessonContent, rejected: DraftQuestion, reason: str,
) -> DraftQuestion | None:
    """Просит модель заменить один отбракованный вопрос новым — с учётом
    причины отбраковки, строго по тому же тексту урока."""
    lesson_text = "\n\n".join(f"{s['title']}: {s['content']}" for s in content.explain_steps)
    is_quiz = rejected.kind == "quiz"
    kind_hint = "вопрос финального квиза" if is_quiz else f"интерактивный шаг типа {rejected.step_type}"
    format_hint = (
        '{"question": "...", "options": ["...", "...", "..."], "correct": 0, "explanation": "..."}'
        if is_quiz else
        f'{{"type": "{rejected.step_type}", "title": "...", "task": "...", '
        '"options": ["...", "...", "..."], "correct_index": 0, '
        '"feedback_correct": "...", "feedback_wrong": "...", "hint": "..."}'
    )

    prompt = f"""Текст урока:

--- ТЕКСТ УРОКА ---
{lesson_text}
--- КОНЕЦ ТЕКСТА ---

Предыдущий вариант вопроса ({kind_hint}) отбракован проверкой: {reason}

Придумай ДРУГОЙ вопрос того же типа, строго по тексту урока, без этой
ошибки. Индекс правильного варианта — с нуля; перед тем как его записать,
вычисли ответ вручную и проверь, что он действительно совпадает с одним
из options.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков, один объект (не массив),
строго в формате: {format_hint}"""

    try:
        raw = await generate_lesson_raw(prompt)
    except Exception:
        return None

    if is_quiz:
        return DraftQuestion(
            kind="quiz", step_type=None,
            question=raw.get("question") or "",
            options=raw.get("options"),
            author_correct_index=raw.get("correct"),
            raw=raw,
        )
    return DraftQuestion(
        kind="step", step_type=raw.get("type") or rejected.step_type,
        question=raw.get("task") or raw.get("text") or "",
        options=raw.get("options"),
        author_correct_index=raw.get("correct_index"),
        raw=raw,
    )


async def verify_and_repair_questions(
    content: LessonContent,
    drafts: list[DraftQuestion],
    max_retries: int = MAX_QUESTION_RETRIES,
) -> tuple[list[VerifiedQuestion], list[DraftQuestion]]:
    """Верифицирует каждый проверяемый вопрос (multiple_choice/quiz — есть
    options + author_correct_index), с ретраями на отбраковку. Вопрос, не
    принятый после лимита ретраев, НЕ попадает в итог (критерий готовности
    этапа). Возвращает (принятые вопросы, вопросы без проверяемого ответа —
    fill_blank/match_pairs/sort_items проходят как есть, вне объёма судьи
    на этом этапе)."""
    verified: list[VerifiedQuestion] = []
    passthrough: list[DraftQuestion] = []

    for draft in drafts:
        if draft.options is None or draft.author_correct_index is None:
            passthrough.append(draft)
            continue

        current = draft
        verdict: VerifiedQuestion | None = None
        for attempt in range(max_retries + 1):
            verdict = await verify_question(content, current)
            if verdict.accepted:
                break
            if attempt == max_retries:
                break
            replacement = await _regenerate_single_question(content, current, verdict.reason or "")
            if replacement is None:
                break
            current = replacement

        if verdict is not None and verdict.accepted:
            verified.append(verdict)

    return verified, passthrough


def assemble_lesson_dict(
    content: LessonContent,
    verified: list[VerifiedQuestion],
    passthrough: list[DraftQuestion],
) -> dict:
    """Собирает финальный словарь урока из проверенного контента и вопросов
    — форма совместима со старым generate_lesson_raw() (title/age_band/goal/
    story_intro/steps/quiz/reward), чтобы существующий validate_lesson() и
    скрипты замера могли работать с обоими пайплайнами одинаково. Используется
    и в интеграции (сессия 4, пункт 6), и в скриптах перезамера
    (reports/quiz_quality_rebuild_*/). Отбракованные и не восстановленные
    ретраями вопросы сюда не попадают — их просто нет среди verified."""
    steps: list[dict] = [
        {"type": "explain", "title": s["title"], "content": s["content"]}
        for s in content.explain_steps
    ]
    quiz: list[dict] = []

    for vq in verified:
        (steps if vq.draft.kind == "step" else quiz).append(vq.draft.raw)
    for d in passthrough:
        (steps if d.kind == "step" else quiz).append(d.raw)

    return {
        "title": content.title,
        "age_band": content.age_band,
        "goal": content.goal,
        "story_intro": content.story_intro,
        "steps": steps,
        "quiz": quiz,
        "reward": {"xp": 20, "badge_candidate": None},
    }


MIN_QUIZ_QUESTIONS = 2  # меньше — урок непригоден, needs_review (после отбраковки судьёй)


async def generate_and_save_lesson_new(
    child_id: int, topic_id: int, difficulty: int, db: AsyncSession,
) -> Lesson:
    """Точка входа НОВОГО пайплайна (вызов1 -> вызов2 -> вызов3/судья ->
    сборка). Включается флагом settings.USE_NEW_LESSON_PIPELINE в
    app/api/endpoints/lessons.py — старый generate_and_save_lesson
    (lesson_generator.py) не тронут и продолжает быть путём по умолчанию.

    DB-writing часть (шаги/quiz/геймификация) сознательно ДУБЛИРУЕТ, а не
    переиспользует код старого пути — чтобы интеграция нового пайплайна
    не требовала ни строчки правок в проверенном старом коде (см.
    TASK_STAGE1_v4.md, сессия 4, пункт 6, «старый код не удалять»).
    Откат — выключить флаг, эта функция просто перестаёт вызываться."""
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
        age_band=f"{child.age}-{child.age + 1}",
        status=LessonStatus.generating,
        child_id=child_id,
        topic_id=topic_id,
        generation_attempts=1,
    )
    db.add(lesson)
    await db.flush()

    content = await generate_lesson_content(child, topic, subject, difficulty)
    drafts = await generate_questions(content)
    verified, passthrough = await verify_and_repair_questions(content, drafts)
    raw = assemble_lesson_dict(content, verified, passthrough)

    quiz_count = sum(1 for d in passthrough if d.kind == "quiz")
    quiz_count += sum(1 for v in verified if v.draft.kind == "quiz")
    if quiz_count < MIN_QUIZ_QUESTIONS:
        lesson.status = LessonStatus.needs_review
        lesson.validation_errors = [{
            "field": "quiz",
            "message": f"После проверки судьёй осталось {quiz_count} вопрос(ов) quiz, нужно ≥{MIN_QUIZ_QUESTIONS}",
            "severity": "critical",
        }]
        await db.flush()
        raise ValueError(
            f"Урок требует ручной проверки: после верификации осталось {quiz_count} quiz-вопросов"
        )

    try:
        lesson_data = AILessonResponse.model_validate(raw)
    except (ValidationError, ValueError, KeyError) as e:
        lesson.status = LessonStatus.needs_review
        lesson.validation_errors = [{"field": "schema", "message": str(e)[:500], "severity": "critical"}]
        await db.flush()
        raise ValueError(f"Урок требует ручной проверки после сборки: {str(e)[:300]}") from e

    lesson.title = lesson_data.title
    lesson.age_band = lesson_data.age_band
    lesson.goal = lesson_data.goal
    lesson.story_intro = lesson_data.story_intro
    lesson.xp_reward = lesson_data.reward.xp
    lesson.badge_candidate = lesson_data.reward.badge_candidate
    lesson.raw_ai_response = raw
    lesson.status = LessonStatus.ready

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

    quiz_row = Quiz(lesson_id=lesson.id)
    db.add(quiz_row)
    await db.flush()

    for i, q in enumerate(lesson_data.quiz):
        question = QuizQuestion(
            quiz_id=quiz_row.id,
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

    return lesson


# ── Промпты ──────────────────────────────────────────────────────────────

def _build_content_prompt(child: Child, topic: Topic, subject: Subject, difficulty: int) -> str:
    difficulty_name = DIFFICULTY_NAMES.get(difficulty, "средний")

    return f"""Ты создаёшь ТОЛЬКО обучающий текст урока для ребёнка {child.age} лет
({child.grade} класс). Тема: "{topic.title}". Предмет: {subject.name}.
Сложность: {difficulty_name}.

Твоя единственная задача — объяснить материал понятно и увлекательно.
НЕ придумывай вопросы, тесты, варианты ответов, задания на проверку —
это делает отдельный шаг с другой ролью, у тебя её нет.

ИНТЕРФЕЙС ТЕКСТОВЫЙ: никаких картинок, изображений, схем.

Структура: 2–4 логических блока объяснения, каждый — отдельная мысль темы,
с конкретным примером (числа, слова, ситуации из жизни ребёнка {child.age} лет).
Не повторяй один и тот же пример в разных блоках.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков, строго такой структуры:

{{
  "title": "Название урока",
  "age_band": "{child.age}-{child.age + 1}",
  "goal": "Чему научится ребёнок за урок, одна фраза",
  "story_intro": "Короткая вступительная история, 2-3 предложения",
  "steps": [
    {{"title": "Название блока 1", "content": "Объяснение с конкретным примером..."}},
    {{"title": "Название блока 2", "content": "Следующий блок объяснения..."}}
  ]
}}

Создай урок по теме "{topic.title}" для ребёнка {child.age} лет в этом формате."""


def _build_questions_prompt(content: LessonContent) -> str:
    lesson_text = "\n\n".join(
        f"{s['title']}: {s['content']}" for s in content.explain_steps
    )

    return f"""Вот текст урока, который уже написан и зафиксирован — его менять нельзя:

--- ТЕКСТ УРОКА ---
Тема: {content.title}
Цель: {content.goal}

{lesson_text}
--- КОНЕЦ ТЕКСТА ---

Придумай вопросы и задания СТРОГО по этому тексту. Каждый факт, число или
правило в вопросе должны быть либо прямо написаны в тексте выше, либо быть
элементарным следствием текста (например, арифметика с числами из текста).
Не вводи фактов, которых нет в тексте.

ТИПЫ ИНТЕРАКТИВНЫХ ШАГОВ (нужно 2–4 штуки, чередуй, не более 2 подряд
одного типа):
- multiple_choice: выбор из 3 вариантов, correct_index = 0/1/2 (0-based!)
- fill_blank: вписать пропущенное слово/число (текст с ___ на месте пропуска)
- match_pairs: соотнести левый и правый столбец (минимум 3 пары)
- sort_items: расставить элементы в правильном порядке

ДЛЯ КАЖДОГО ИНТЕРАКТИВНОГО ШАГА БЕЗ ИСКЛЮЧЕНИЙ (multiple_choice, fill_blank,
match_pairs, sort_items — ВСЕ четыре типа, не только multiple_choice)
ОБЯЗАТЕЛЬНЫ ВСЕ ТРИ ПОЛЯ (см. пример JSON ниже — там они показаны для
каждого типа шага, повтори этот набор полей независимо от типа):
- "feedback_correct": 1-2 предложения почему ответ верный
- "feedback_wrong": наводящая подсказка без раскрытия ответа
- "hint": краткая подсказка для второй попытки

Весь текст — на русском языке. Не вставляй английские слова.

ПРАВИЛА для "multiple_choice":
• task = один чёткий вопрос по тексту урока. options = 3 коротких варианта.
• correct_index = ИНДЕКС правильного варианта в options, С НУЛЯ (0-based).
  Первый вариант верный → correct_index = 0. Второй → 1. Третий → 2.
  Перед тем как записать correct_index, вычисли ответ вручную и проверь,
  что options[correct_index] действительно верен.

ПРАВИЛА для "fill_blank":
• question = инструкция ("Вставь пропущенное слово")
• text = предложение с ___ на месте пропуска (строго три подчёркивания)
• correct_answers = массив допустимых вариантов ответа: ["ответ", "Ответ"]

ПРАВИЛА для "match_pairs": pairs = [{{"left": "...", "right": "..."}}], от 3 пар.

ПРАВИЛА для "sort_items":
• instruction = чёткая инструкция, ПО КАКОМУ КРИТЕРИЮ сортировать (например,
  "Расставь дроби от меньшей к большей", "Расположи шаги в правильном
  порядке"). Без явного критерия сортировки — не создавай этот тип шага.
• items = элементы в произвольном порядке (не смешивай разнородные понятия
  в одном списке — только однородные по критерию из instruction).
• correct_order = те же элементы в порядке, который однозначно следует из
  instruction и текста урока.

ФИНАЛЬНЫЙ КВИЗ (отдельно от шагов выше, 3-4 вопроса, проверяет понимание
всего урока):
• question, options (3 варианта), correct = ИНДЕКС верного варианта (0-based,
  та же логика, что и correct_index выше), explanation — почему это верно,
  со ссылкой на текст урока.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков, строго такой структуры:

{{
  "steps": [
    {{
      "type": "multiple_choice",
      "title": "Проверь себя",
      "task": "Вопрос по тексту урока?",
      "options": ["вариант1", "вариант2", "вариант3"],
      "correct_index": 0,
      "feedback_correct": "...",
      "feedback_wrong": "...",
      "hint": "..."
    }},
    {{
      "type": "fill_blank",
      "title": "Заполни пропуск",
      "question": "Вставь пропущенное слово:",
      "text": "Предложение с ___ на месте пропуска.",
      "correct_answers": ["ответ", "Ответ"],
      "feedback_correct": "...",
      "feedback_wrong": "...",
      "hint": "..."
    }},
    {{
      "type": "match_pairs",
      "title": "Соотнеси пары",
      "pairs": [{{"left": "...", "right": "..."}}, {{"left": "...", "right": "..."}}, {{"left": "...", "right": "..."}}],
      "feedback_correct": "...",
      "feedback_wrong": "...",
      "hint": "..."
    }},
    {{
      "type": "sort_items",
      "title": "Расставь по порядку",
      "instruction": "Чёткий критерий сортировки",
      "items": ["...", "...", "..."],
      "correct_order": ["...", "...", "..."],
      "feedback_correct": "...",
      "feedback_wrong": "...",
      "hint": "..."
    }}
  ],
  "quiz": [
    {{"question": "Вопрос?", "options": ["А", "Б", "В"], "correct": 0, "explanation": "Объяснение со ссылкой на текст урока."}}
  ]
}}

Придумай вопросы и задания по тексту урока выше в этом формате JSON."""


def _build_verifier_prompt(content: LessonContent, question: DraftQuestion) -> str:
    lesson_text = "\n\n".join(f"{s['title']}: {s['content']}" for s in content.explain_steps)
    options_text = "\n".join(f"{i}: {opt}" for i, opt in enumerate(question.options or []))

    return f"""Вот текст урока:

--- ТЕКСТ УРОКА ---
{lesson_text}
--- КОНЕЦ ТЕКСТА ---

Вот вопрос и варианты ответа к нему. Тебе НЕ сообщается, какой вариант
считается правильным — определи это сам, строго по тексту урока выше
(и, если нужно, по элементарной логике, прямо следующей из текста).

Вопрос: {question.question}
Варианты:
{options_text}

Если ровно один вариант однозначно верен — определи его индекс (с нуля).
Если ни один вариант не верен, или верны сразу несколько, или текста
недостаточно, чтобы определить ответ однозначно, — не выбирай индекс и
объясни проблему.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "verdict": "single" | "none" | "multiple" | "insufficient_text",
  "correct_index": 0,
  "reasoning": "Краткое объяснение, почему именно этот ответ следует из текста (или почему ответа нет)."
}}

"correct_index" заполняй числом, ТОЛЬКО если verdict == "single", иначе
поставь null."""


def _build_consistency_prompt(content: LessonContent) -> str:
    lesson_text = "\n\n".join(f"{s['title']}: {s['content']}" for s in content.explain_steps)

    return f"""Вот текст обучающего урока для ребёнка. Проверь его на
ВНУТРЕННЮЮ непротиворечивость и явные фактические ошибки в правилах —
не орфографию и не стиль, а именно факты и логику.

--- ТЕКСТ УРОКА ---
{lesson_text}
--- КОНЕЦ ТЕКСТА ---

Ищи конкретно:
- противоречит ли одно утверждение другому внутри текста (например,
  сформулированное правило не совпадает с примером, который тут же решён
  по-другому правилу);
- содержит ли текст явно неверное общее правило, даже если конкретные
  числовые примеры в тексте всё же посчитаны верно.

Отвечай ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "consistent": true,
  "issues": []
}}

Если нашёл проблему — "consistent": false, "issues": ["конкретное
противоречие или ошибка, с цитатой из текста", ...]. Если проблем нет —
"consistent": true, "issues": []."""


# ── Парсинг ответов LLM ──────────────────────────────────────────────────

def _parse_content(raw: dict) -> LessonContent:
    return LessonContent(
        title=raw.get("title") or "",
        age_band=raw.get("age_band") or "",
        goal=raw.get("goal") or "",
        story_intro=raw.get("story_intro") or "",
        explain_steps=[
            {"title": s.get("title") or "", "content": s.get("content") or ""}
            for s in (raw.get("steps") or [])
        ],
    )


def _parse_questions(raw: dict) -> list[DraftQuestion]:
    drafts: list[DraftQuestion] = []

    for step in raw.get("steps") or []:
        stype = step.get("type", "")
        if stype in ("multiple_choice", "game"):
            question_text = step.get("task") or ""
            options = step.get("options")
            correct = step.get("correct_index")
        elif stype == "fill_blank":
            question_text = step.get("text") or ""
            options = None
            correct = None
        elif stype == "sort_items":
            question_text = step.get("instruction") or ""
            options = None
            correct = None
        else:  # match_pairs и прочее — нет проверяемого единственного ответа
            question_text = step.get("title") or ""
            options = None
            correct = None

        drafts.append(DraftQuestion(
            kind="step",
            step_type=stype or None,
            question=question_text,
            options=options,
            author_correct_index=correct,
            raw=step,
        ))

    for q in raw.get("quiz") or []:
        drafts.append(DraftQuestion(
            kind="quiz",
            step_type=None,
            question=q.get("question") or "",
            options=q.get("options"),
            author_correct_index=q.get("correct"),
            raw=q,
        ))

    return drafts


def _parse_verdict(question: DraftQuestion, raw: dict) -> VerifiedQuestion:
    verdict = raw.get("verdict")
    verifier_idx = raw.get("correct_index")
    reasoning = raw.get("reasoning") or ""

    if verdict == "single" and isinstance(verifier_idx, int):
        accepted = verifier_idx == question.author_correct_index
        reason = None
        if not accepted:
            options = question.options or []
            picked = options[verifier_idx] if 0 <= verifier_idx < len(options) else "?"
            reason = (f"Судья выбрал индекс {verifier_idx} ({picked}), "
                      f"автор — {question.author_correct_index}. {reasoning}")
        return VerifiedQuestion(draft=question, accepted=accepted,
                                verifier_correct_index=verifier_idx, reason=reason)

    return VerifiedQuestion(draft=question, accepted=False, verifier_correct_index=None,
                            reason=f"Судья: {verdict or 'нет вердикта'} — {reasoning}")


def _parse_consistency(raw: dict) -> ContentVerdict:
    return ContentVerdict(
        consistent=bool(raw.get("consistent", True)),
        issues=[str(i) for i in (raw.get("issues") or [])],
    )
