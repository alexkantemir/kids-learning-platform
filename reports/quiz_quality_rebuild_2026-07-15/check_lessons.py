"""
check_lessons.py — автоматический скоринг уроков, сгенерированных
generate_test_lessons.py, для ОБОИХ пайплайнов (TASK_STAGE1_v4.md, пункт 5).

Считает: настоящий validate_lesson() (как есть, без изменений) + новую
кодовую проверку арифметики quiz-вопросов (check_question_arithmetic из
lesson_pipeline.py — учитывает порядок операций и скобки, чего не умеет
старый _ARITH_RE внутри lesson_validator.py).

Это АВТОМАТИЧЕСКИЙ скоринг, не полная замена ручной сверки. Он ловит:
- всё, что ловит validate_lesson() (структура, длины полей, шаги);
- дефекты quiz, сводимые к арифметике (неверный correct/index).
Он НЕ ловит: quiz-вопросы без вычислимой арифметики, где ответ неверен по
смыслу/фактам, или где верны сразу два варианта / не верен ни один — это
по-прежнему требует ручной вычитки (см. методологию в CLAUDE.md, раздел
"БАЗОВАЯ МЕТРИКА КАЧЕСТВА КВИЗОВ"). Числа отсюда — нижняя граница брака,
не окончательная цифра.

Запуск внутри backend-контейнера ПОСЛЕ generate_test_lessons.py:
    docker compose exec backend python \
        reports_scratch/check_lessons.py
"""
import json
from pathlib import Path

from app.services.lesson_pipeline import check_question_arithmetic
from app.services.lesson_validator import validate_lesson

OUT_DIR = Path(__file__).parent


def check_quiz_arithmetic(quiz: list[dict]) -> list[dict]:
    """check_question_arithmetic теперь возвращает 4-й элемент — ambiguous
    (Этап 2, сессия 2: код понимает эквивалентные дроби, 1/2 и 3/6 —
    находка сессии 6 Этапа 1)."""
    problems = []
    for i, q in enumerate(quiz):
        question = q.get("question") or ""
        options = q.get("options") or []
        claimed = q.get("correct")
        is_arith, code_idx, expected, ambiguous = check_question_arithmetic(question, options)
        if not is_arith:
            continue
        if ambiguous:
            problems.append({
                "quiz_index": i, "question": question,
                "issue": f"несколько вариантов численно равны {expected} (например, разные записи одной дроби) — неоднозначно",
            })
        elif code_idx is None:
            problems.append({
                "quiz_index": i, "question": question,
                "issue": f"код вычислил {expected}, такого варианта нет среди options",
            })
        elif code_idx != claimed:
            problems.append({
                "quiz_index": i, "question": question,
                "issue": f"код вычислил {expected} (это options[{code_idx}]), но correct={claimed}",
            })
    return problems


def check_pipeline(dir_name: str) -> dict:
    lessons_dir = OUT_DIR / dir_name
    results = []
    for path in sorted(lessons_dir.glob("lesson_*.json")):
        lesson = json.loads(path.read_text(encoding="utf-8"))
        val_result = validate_lesson(lesson)
        quiz = lesson.get("quiz") or []
        quiz_problems = check_quiz_arithmetic(quiz)
        blocking = [e for e in val_result.errors if e.severity in ("critical", "major")]
        defective = bool(quiz_problems) or bool(blocking)
        results.append({
            "file": path.name,
            "title": lesson.get("title"),
            "validate_lesson_valid": val_result.valid,
            "validate_lesson_errors": [f"{e.field}: {e.message}" for e in blocking],
            "quiz_problems": quiz_problems,
            "defective": defective,
            "quiz_question_count": len(quiz),
            "quiz_defect_count": len(quiz_problems),
        })
    return {"results": results}


def summarize(label: str, data: dict) -> None:
    results = data["results"]
    total_lessons = len(results)
    defective_lessons = sum(1 for r in results if r["defective"])
    total_questions = sum(r["quiz_question_count"] for r in results)
    defective_questions = sum(r["quiz_defect_count"] for r in results)

    print(f"\n=== {label} ===")
    if total_lessons:
        print(f"Уроков: {total_lessons}, с браком: {defective_lessons} "
              f"({100 * defective_lessons / total_lessons:.0f}%)")
    else:
        print("Уроков не найдено — сначала запусти generate_test_lessons.py")
    if total_questions:
        print(f"Вопросов quiz: {total_questions}, дефектных (авто): {defective_questions} "
              f"({100 * defective_questions / total_questions:.0f}%)")
    for r in results:
        if r["defective"]:
            print(f"  БРАК: {r['file']} ({r['title']})")
            for e in r["validate_lesson_errors"]:
                print(f"    validate_lesson: {e}")
            for p in r["quiz_problems"]:
                print(f"    quiz[{p['quiz_index']}]: {p['issue']}")


def main() -> None:
    old_data = check_pipeline("lessons_out_old")
    new_data = check_pipeline("lessons_out_new")

    (OUT_DIR / "check_output_old.json").write_text(
        json.dumps(old_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "check_output_new.json").write_text(
        json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summarize("СТАРЫЙ ПАЙПЛАЙН (монолитный, lesson_generator.py)", old_data)
    summarize("НОВЫЙ ПАЙПЛАЙН (generator->verifier, lesson_pipeline.py)", new_data)
    print("\nЭто автоскоринг (структура + вычислимая арифметика). Финальная "
          "цифра брака требует ручной вычитки не-арифметических quiz-вопросов "
          "(см. quiz_dump.txt после ручной сверки, методология в CLAUDE.md).")


if __name__ == "__main__":
    main()
