"""
Unit-тесты для кодовой арифметики lesson_pipeline.py — конкретно для
эквивалентных представлений чисел (Этап 2, сессия 2, TASK_STAGE2.md).
Кейс "1/2 = 3/6 = 0.5" — находка сессии 6 Этапа 1, где судья не смог
распознать, что сокращённая и несокращённая дробь — один и тот же ответ.
Run with: docker exec kids-platform-backend-1 python -m pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.lesson_pipeline import check_question_arithmetic, _eval_arith_chain


# ── Эквивалентные дроби (находка сессии 6, чинится в сессии 2 Этапа 2) ────────

def test_fraction_sum_matches_multiple_equivalent_options():
    # Точный кейс сессии 6: 1/3 + 1/6 = 1/2, но среди вариантов есть и
    # несокращённая форма 3/6 — та же величина. Раньше (до сессии 2) код
    # вообще не видел дробные варианты как числа (float("1/2") падает) и
    # никогда не включался на такой quiz.
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Чему равна сумма 1/3 + 1/6?", ["1/2", "2/3", "3/6", "5/6"]
    )
    assert is_arith is True
    assert abs(expected - 0.5) < 0.001
    assert ambiguous is True  # индексы 0 ("1/2") и 2 ("3/6") оба верны


def test_decimal_and_fraction_equivalent_forms_are_ambiguous():
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Чему равно 2/4?", ["0.5", "1/2", "3/4"]
    )
    assert is_arith is True
    assert ambiguous is True  # "0.5" и "1/2" — одно и то же число


def test_single_fraction_option_not_ambiguous():
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Чему равно 1/2?", ["0.5", "1/4", "3/4"]
    )
    assert is_arith is True
    assert ambiguous is False
    assert idx == 0


# ── Регресс: старые кейсы сессии 3-4 не должны сломаться ─────────────────────

def test_order_of_operations_still_correct():
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Какое значение получится в примере 7 + 4 * 2?", ["9", "11", "15"]
    )
    assert is_arith is True
    assert ambiguous is False
    assert idx == 2
    assert expected == 15.0


def test_rule_question_with_text_options_not_arithmetic():
    # Вопрос про порядок действий, а не про числовой результат — код не
    # должен включаться, даже если в тексте есть числа (баг сессии 3).
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "В каком порядке выполняются действия в 10 : 2 * 3?",
        ["Сначала деление, потом умножение", "Сначала умножение, потом деление"],
    )
    assert is_arith is False


def test_simple_subtraction_regression():
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Сколько будет 18 - 9?", ["9", "8", "7"]
    )
    assert is_arith is True
    assert ambiguous is False
    assert idx == 0
    assert expected == 9.0


# ── Известное ограничение, НЕ чинится сегодня (см. CLAUDE.md, сессия 2) ──────

def test_natural_language_fraction_sum_without_explicit_plus_is_not_extracted():
    """Без явного "+" в тексте ("сумма дробей X и Y", а не "X + Y") код не
    может собрать составное выражение — тот же класс ограничения, что
    "словесные задачи" из Этапа 1 (принятое ограничение, не архитектурная
    дыра). Тест фиксирует ТЕКУЩЕЕ поведение (регекс хватает только первую
    отдельную дробь "1/3"), чтобы будущая сессия не приняла его за баг
    заново, если случайно наткнётся на этот же кейс."""
    is_arith, idx, expected, ambiguous = check_question_arithmetic(
        "Найди сумму дробей 1/3 и 1/6", ["1/2", "2/3", "3/6", "5/6"]
    )
    assert is_arith is True
    assert abs(expected - (1 / 3)) < 0.001  # НЕ 0.5 — регекс не увидел implied "+"


def test_eval_arith_chain_fraction_sum_direct():
    # _eval_arith_chain сама по себе умеет дроби, когда выражение явное —
    # ограничение теста выше в extraction (какую подстроку найти в тексте
    # вопроса), не в вычислении.
    assert abs(_eval_arith_chain("1/3+1/6") - 0.5) < 0.001
