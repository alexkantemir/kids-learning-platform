"""
Unit tests for lesson_validator.
Run with: docker exec kids-platform-backend-1 python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.lesson_validator import validate_lesson, apply_auto_fixes, build_retry_hint


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mc_step(**kwargs):
    base = {
        "type": "multiple_choice",
        "title": "Вопрос",
        "feedback_correct": "Верно! Потому что...",
        "feedback_wrong": "Подумай ещё раз...",
        "hint": "Вспомни правило.",
    }
    base.update(kwargs)
    return base


def _lesson(*steps, title="Тест урок"):
    return {"title": title, "steps": list(steps)}


# ── Math: multiple_choice ─────────────────────────────────────────────────────

def test_fixes_wrong_correct_index_34_plus_56():
    """34 + 56 = 90, but GigaChat said index 0 (which is '91')."""
    step = _mc_step(
        task="Сколько будет 34 + 56?",
        options=["91", "80", "90"],
        correct_index=0,
    )
    result = validate_lesson(_lesson(step))
    assert len(result.auto_fixed) == 1
    assert result.auto_fixed[0].new_value == 2   # '90' is at index 2
    assert result.auto_fixed[0].field == "correct_index"
    # After fix, lesson is valid
    fixed = apply_auto_fixes(_lesson(step), result.auto_fixed)
    assert fixed["steps"][0]["correct_index"] == 2


def test_no_fix_when_math_correct():
    """45 + 27 = 72, correct_index=0 pointing to '72' — should pass."""
    step = _mc_step(
        task="Сколько будет 45 + 27?",
        options=["72", "52", "63"],
        correct_index=0,
    )
    result = validate_lesson(_lesson(_explain_step(), step))
    assert result.auto_fixed == []
    assert result.valid


def test_critical_error_when_correct_answer_absent():
    """5 + 5 = 10 but options are [8, 9, 11] — can't auto-fix."""
    step = _mc_step(
        task="Сколько будет 5 + 5?",
        options=["8", "9", "11"],
        correct_index=0,
    )
    result = validate_lesson(_lesson(step, _explain_step()))
    assert any(e.severity == "critical" and e.field == "correct_index" for e in result.errors)
    assert result.valid is False


def test_non_arithmetic_question_passes():
    """Non-math question — validator should not apply math check."""
    step = _mc_step(
        task="Какая планета ближайшая к Солнцу?",
        options=["Земля", "Меркурий", "Венера"],
        correct_index=1,
    )
    result = validate_lesson(_lesson(_explain_step(), step))
    assert result.auto_fixed == []
    math_errors = [e for e in result.errors if e.field == "correct_index"]
    assert math_errors == []


def test_subtraction_fix():
    """79 − 23 = 56, correct_index points to '57'."""
    step = _mc_step(
        task="Реши: 79 − 23 = ?",
        options=["57", "56", "60"],
        correct_index=0,
    )
    result = validate_lesson(_lesson(step))
    assert len(result.auto_fixed) == 1
    assert result.auto_fixed[0].new_value == 1  # '56' at index 1


# ── Math: fill_blank ──────────────────────────────────────────────────────────

def test_fixes_fill_blank_wrong_answer():
    """__ минус 23 равно 56 → correct answer is 79, not 80."""
    step = {
        "type": "fill_blank",
        "title": "Пропуск",
        "text": "__ минус 23 равно 56.",
        "correct_answers": ["80"],
        "feedback_correct": "Верно! Потому что...",
        "feedback_wrong": "Подумай ещё раз...",
        "hint": "Вспомни обратное действие.",
    }
    result = validate_lesson(_lesson(step))
    assert len(result.auto_fixed) == 1
    assert result.auto_fixed[0].new_value == ["79"]


def test_fill_blank_correct_answer_passes():
    step = {
        "type": "fill_blank",
        "title": "Пропуск",
        "text": "__ плюс 23 равно 56.",
        "correct_answers": ["33"],
        "feedback_correct": "Верно! Потому что...",
        "feedback_wrong": "Подумай ещё раз...",
        "hint": "Вспомни обратное действие.",
    }
    result = validate_lesson(_lesson(step))
    assert result.auto_fixed == []


# ── Structural validation ─────────────────────────────────────────────────────

def test_correct_index_out_of_range():
    step = _mc_step(
        task="Вопрос?",
        options=["А", "Б"],
        correct_index=5,
    )
    result = validate_lesson(_lesson(step, _explain_step()))
    assert any(e.field == "correct_index" for e in result.errors)
    assert result.valid is False


def test_fill_blank_missing_blank_marker():
    step = {
        "type": "fill_blank",
        "title": "Пропуск",
        "text": "Напиши число.",     # no ___
        "correct_answers": ["5"],
        "feedback_correct": "Верно! Потому что...",
        "feedback_wrong": "Подумай ещё раз...",
        "hint": "Это маленькое число.",
    }
    result = validate_lesson(_lesson(step))
    assert any(e.field == "text" for e in result.errors)


def test_sort_items_wrong_correct_order():
    step = {
        "type": "sort_items",
        "title": "Порядок",
        "instruction": "Расставь:",
        "items": ["А", "Б", "В"],
        "correct_order": ["А", "Б", "Г"],   # 'Г' not in items
        "feedback_correct": "Верно! Потому что...",
        "feedback_wrong": "Подумай ещё раз...",
        "hint": "Начни с первого.",
    }
    result = validate_lesson(_lesson(step))
    assert any(e.severity == "critical" and e.field == "correct_order" for e in result.errors)


def test_missing_feedback_fields():
    step = {
        "type": "multiple_choice",
        "title": "Вопрос",
        "task": "Что это?",
        "options": ["А", "Б", "В"],
        "correct_index": 0,
        # feedback_correct, feedback_wrong, hint — all missing
    }
    result = validate_lesson(_lesson(step, _explain_step()))
    missing = {e.field for e in result.errors}
    assert "feedback_correct" in missing
    assert "feedback_wrong" in missing
    assert "hint" in missing


def test_valid_lesson_passes():
    result = validate_lesson(_full_valid_lesson())
    assert result.valid is True
    assert result.errors == []


def test_title_too_short():
    lesson = _full_valid_lesson()
    lesson["title"] = "АБ"
    result = validate_lesson(lesson)
    assert any(e.field == "title" for e in result.errors)


def test_duplicate_options():
    step = _mc_step(
        task="Вопрос?",
        options=["А", "А", "Б"],
        correct_index=0,
    )
    result = validate_lesson(_lesson(step, _explain_step()))
    assert any(e.field == "options" for e in result.errors)


# ── retry hint ────────────────────────────────────────────────────────────────

def test_build_retry_hint_deduplicates():
    from app.services.lesson_validator import ValidationError as VE
    errors = [
        VE(field="correct_index", message="wrong", severity="major", step_index=0),
        VE(field="correct_index", message="wrong", severity="major", step_index=1),
        VE(field="hint", message="empty", severity="major", step_index=2),
    ]
    hint = build_retry_hint(errors)
    # correct_index hint should appear only once
    assert hint.count("correct_index") <= 1 or hint.count("ИНДЕКС") >= 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _explain_step():
    return {
        "type": "explain",
        "title": "Объяснение",
        "content": "Это очень важная концепция, которую нужно понять прежде чем двигаться дальше. " * 2,
    }


def _full_valid_lesson() -> dict:
    return {
        "title": "Тестовый урок по математике",
        "age_band": "9-10",
        "goal": "Научиться",
        "story_intro": "Давным-давно...",
        "steps": [
            _explain_step(),
            _mc_step(
                task="Какая планета ближайшая к Солнцу?",
                options=["Земля", "Меркурий", "Венера"],
                correct_index=1,
            ),
            {
                "type": "fill_blank",
                "title": "Пропуск",
                "question": "Вставь пропущенное слово:",
                "text": "Столица России — ___.",
                "correct_answers": ["Москва", "москва"],
                "feedback_correct": "Верно! Москва — столица России.",
                "feedback_wrong": "Подумай о главном городе страны.",
                "hint": "Этот город на реке Москва.",
            },
        ],
        "quiz": [
            {"question": "Вопрос?", "options": ["А", "Б", "В"], "correct": 0, "explanation": "Потому что А."},
        ],
        "reward": {"xp": 20, "badge_candidate": None},
    }
