"""
Validator for AI-generated lessons before saving to DB.
Works on the raw dict returned by GigaChat (before Pydantic validation).
"""
import re
import dataclasses
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclasses.dataclass
class ValidationError:
    field: str
    message: str
    severity: str  # 'critical' | 'major'
    step_index: int = -1


@dataclasses.dataclass
class ValidationWarning:
    field: str
    message: str
    step_index: int = -1


@dataclasses.dataclass
class AutoFix:
    field: str
    old_value: Any
    new_value: Any
    description: str
    step_index: int = -1


@dataclasses.dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = dataclasses.field(default_factory=list)
    warnings: list[ValidationWarning] = dataclasses.field(default_factory=list)
    auto_fixed: list[AutoFix] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [dataclasses.asdict(e) for e in self.errors],
            "warnings": [dataclasses.asdict(w) for w in self.warnings],
            "auto_fixed": [dataclasses.asdict(f) for f in self.auto_fixed],
        }


# ── Math utilities ─────────────────────────────────────────────────────────────

_ARITH_RE = re.compile(r'(\d+(?:\.\d+)?)\s*([+\-×\*\/÷−])\s*(\d+(?:\.\d+)?)')
_ARITH_KEYWORDS = re.compile(
    r'сколько будет|вычисли|посчитай|реши пример|найди результат', re.IGNORECASE
)
_BLANK_RE = re.compile(r'_{1,}(\s+_{1,})*|\.\.\.')
_OP_MAP = {'×': '*', '÷': '/', '−': '-', '+': '+', '-': '-', '*': '*', '/': '/'}

_SAFE_GLOBALS: dict = {"__builtins__": {}}


def _extract_arith(text: str) -> tuple[str, float] | None:
    m = _ARITH_RE.search(text)
    if not m:
        return None
    a, op, b = m.group(1), m.group(2), m.group(3)
    py_op = _OP_MAP.get(op, op)
    expr = f"{a} {py_op} {b}"
    try:
        result = float(eval(expr, _SAFE_GLOBALS))  # noqa: S307 safe: only numbers+ops
        return expr, result
    except Exception:
        return None


def _is_arithmetic_step(step: dict) -> bool:
    text = step.get('task') or step.get('text') or step.get('question') or ''
    return bool(_ARITH_RE.search(text) or _ARITH_KEYWORDS.search(text))


def _to_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Level 2: math validation ───────────────────────────────────────────────────

def _check_multiple_choice_math(step: dict, i: int) -> AutoFix | ValidationError | None:
    question = step.get('task') or step.get('question') or ''
    options: list = step.get('options') or []
    correct = step.get('correct_index')
    if correct is None:
        correct = step.get('correct')

    extracted = _extract_arith(question)
    if not extracted:
        return None
    expr, expected = extracted

    if not isinstance(correct, int) or not (0 <= correct < len(options)):
        return None

    claimed = _to_float(options[correct])
    if claimed is None or abs(claimed - expected) < 0.001:
        return None  # correct or non-numeric — skip

    # Wrong answer: search correct index in options
    correct_idx = next(
        (j for j, opt in enumerate(options) if abs((_to_float(opt) or float('nan')) - expected) < 0.001),
        None,
    )
    if correct_idx is not None:
        return AutoFix(
            step_index=i,
            field='correct_index',
            old_value=correct,
            new_value=correct_idx,
            description=f"Исправлен индекс: {expr} = {int(expected)}, верный вариант «{options[correct_idx]}» (индекс {correct_idx})",
        )
    return ValidationError(
        step_index=i,
        field='correct_index',
        message=f"Правильный ответ {int(expected)} ({expr}) отсутствует среди вариантов: [{', '.join(options)}]",
        severity='critical',
    )


def _check_fill_blank_math(step: dict, i: int) -> AutoFix | None:
    text = step.get('text') or step.get('task') or ''
    correct_answers: list[str] = step.get('correct_answers') or []

    # "X плюс/минус __ равно Y"
    p1 = re.search(
        r'(\d+)\s*(плюс|минус|[+\-])\s*_{1,}.*?(\d+)', text, re.IGNORECASE
    )
    # "__ плюс/минус X равно Y"
    p2 = re.search(
        r'_{1,}\s*(плюс|минус|[+\-])\s*(\d+).*?(\d+)', text, re.IGNORECASE
    )

    expected: float | None = None
    if p1:
        a, op, result = float(p1.group(1)), p1.group(2).lower(), float(p1.group(3))
        if op in ('плюс', '+'):
            expected = result - a
        elif op in ('минус', '-'):
            expected = a - result
    elif p2:
        op, b, result = p2.group(1).lower(), float(p2.group(2)), float(p2.group(3))
        if op in ('плюс', '+'):
            expected = result - b
        elif op in ('минус', '-'):
            expected = result + b

    if expected is None:
        return None

    has_correct = any(
        abs((_to_float(a) or float('nan')) - expected) < 0.001
        for a in correct_answers
    )
    if not has_correct:
        new_val = str(int(expected)) if expected == int(expected) else str(expected)
        return AutoFix(
            step_index=i,
            field='correct_answers',
            old_value=correct_answers,
            new_value=[new_val],
            description=f"Исправлен ответ fill_blank: вычислено {new_val}, было [{', '.join(correct_answers)}]",
        )
    return None


# ── Level 3: hint quality ──────────────────────────────────────────────────────

def _check_hint_quality(step: dict, i: int) -> ValidationWarning | None:
    hint = (step.get('hint') or '').strip()
    question = (step.get('task') or step.get('question') or '').strip()
    options: list = step.get('options') or []
    correct = step.get('correct_index')
    if correct is None:
        correct = step.get('correct')
    correct_answers: list = step.get('correct_answers') or []

    correct_answer = None
    if isinstance(correct, int) and 0 <= correct < len(options):
        correct_answer = options[correct]
    elif correct_answers:
        correct_answer = correct_answers[0]

    if hint and correct_answer and correct_answer.lower() in hint.lower():
        return ValidationWarning(step_index=i, field='hint',
                                 message='Подсказка содержит правильный ответ — слишком легко для ребёнка')
    if hint and question and hint == question:
        return ValidationWarning(step_index=i, field='hint',
                                 message='Подсказка идентична вопросу — бесполезна')
    return None


# ── Main validator ─────────────────────────────────────────────────────────────

VALID_TYPES = {'explain', 'multiple_choice', 'game', 'fill_blank', 'match_pairs', 'sort_items'}
INTERACTIVE_TYPES = {'multiple_choice', 'game', 'fill_blank', 'match_pairs', 'sort_items'}
MIN_LENGTHS = {'feedback_correct': 20, 'feedback_wrong': 20, 'hint': 15}


def validate_lesson(lesson: dict) -> ValidationResult:
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []
    auto_fixed: list[AutoFix] = []

    # ── Level 1: structural ──────────────────────────────────────────────────
    title = lesson.get('title') or ''
    if not title or not (3 <= len(title.strip()) <= 150):
        errors.append(ValidationError(field='title',
                                      message=f'Название должно быть 3–150 символов, получено {len(title)}',
                                      severity='critical'))

    steps = lesson.get('steps') or []
    if not isinstance(steps, list):
        errors.append(ValidationError(field='steps', message='steps должен быть массивом', severity='critical'))
        return ValidationResult(valid=False, errors=errors)
    if not (2 <= len(steps) <= 10):
        errors.append(ValidationError(field='steps',
                                      message=f'Шагов должно быть 2–10, получено {len(steps)}',
                                      severity='critical'))
        # Continue — still validate individual steps for better error reporting

    for i, step in enumerate(steps):
        stype = step.get('type', '')

        if stype not in VALID_TYPES:
            errors.append(ValidationError(step_index=i, field='type',
                                          message=f'Неизвестный тип шага: {stype!r}',
                                          severity='critical'))
            continue

        # ── multiple_choice / game ────────────────────────────────────────
        if stype in ('multiple_choice', 'game'):
            options = step.get('options') or []
            correct = step.get('correct_index')

            if not isinstance(options, list) or not (2 <= len(options) <= 5):
                errors.append(ValidationError(step_index=i, field='options',
                                              message='options должен содержать 2–5 элементов',
                                              severity='critical'))
            elif not all(isinstance(o, str) and o.strip() for o in options):
                errors.append(ValidationError(step_index=i, field='options',
                                              message='Все варианты должны быть непустыми строками',
                                              severity='major'))
            else:
                if not isinstance(correct, int) or not (0 <= correct < len(options)):
                    errors.append(ValidationError(step_index=i, field='correct_index',
                                                  message=f'correct_index={correct!r} вне диапазона 0..{len(options)-1}',
                                                  severity='major'))
                else:
                    # Duplicate options
                    if len(set(o.strip().lower() for o in options)) < len(options):
                        errors.append(ValidationError(step_index=i, field='options',
                                                      message='Варианты ответа содержат дубликаты',
                                                      severity='major'))
                    # Math check
                    if _is_arithmetic_step(step):
                        fix_or_err = _check_multiple_choice_math(step, i)
                        if isinstance(fix_or_err, AutoFix):
                            auto_fixed.append(fix_or_err)
                        elif isinstance(fix_or_err, ValidationError):
                            errors.append(fix_or_err)

            # Feedback / hint presence & length
            for fname in ('feedback_correct', 'feedback_wrong', 'hint'):
                val = (step.get(fname) or '').strip()
                if not val:
                    errors.append(ValidationError(step_index=i, field=fname,
                                                  message=f'{fname} обязательно для интерактивных шагов',
                                                  severity='major'))
                elif len(val) < MIN_LENGTHS[fname]:
                    warnings.append(ValidationWarning(step_index=i, field=fname,
                                                      message=f'{fname} слишком короткое ({len(val)} сим., мин. {MIN_LENGTHS[fname]})'))

            w = _check_hint_quality(step, i)
            if w:
                warnings.append(w)

        # ── fill_blank ────────────────────────────────────────────────────
        elif stype == 'fill_blank':
            text = step.get('text') or step.get('task') or ''
            correct_answers = step.get('correct_answers') or []

            if not (step.get('question') or step.get('instruction') or '').strip():
                errors.append(ValidationError(step_index=i, field='question',
                                              message='fill_blank должен содержать поле question с инструкцией',
                                              severity='major'))

            blank_count = len(re.findall(r'_{1,}', text))
            if not _BLANK_RE.search(text):
                errors.append(ValidationError(step_index=i, field='text',
                                              message='text должен содержать маркер пропуска (___)',
                                              severity='critical'))

            if not isinstance(correct_answers, list) or len(correct_answers) == 0:
                errors.append(ValidationError(step_index=i, field='correct_answers',
                                              message='correct_answers должен содержать хотя бы 1 элемент',
                                              severity='major'))
            else:
                if blank_count > 1:
                    if len(correct_answers) != blank_count:
                        errors.append(ValidationError(
                            step_index=i, field='correct_answers',
                            message=(f'В тексте {blank_count} пропуска, '
                                     f'но correct_answers содержит {len(correct_answers)} элементов'),
                            severity='critical'))
                    elif not all(isinstance(a, list) for a in correct_answers):
                        errors.append(ValidationError(
                            step_index=i, field='correct_answers',
                            message='При нескольких пропусках correct_answers должен быть массивом массивов',
                            severity='major'))
                else:
                    if not any(isinstance(a, str) and a.strip() for a in correct_answers):
                        errors.append(ValidationError(step_index=i, field='correct_answers',
                                                      message='correct_answers должен содержать хотя бы 1 непустой элемент',
                                                      severity='major'))
                    else:
                        fix = _check_fill_blank_math(step, i)
                        if fix:
                            auto_fixed.append(fix)

            for fname in ('feedback_correct', 'feedback_wrong', 'hint'):
                val = (step.get(fname) or '').strip()
                if not val:
                    errors.append(ValidationError(step_index=i, field=fname,
                                                  message=f'{fname} обязательно для интерактивных шагов',
                                                  severity='major'))

        # ── match_pairs ───────────────────────────────────────────────────
        elif stype == 'match_pairs':
            pairs = step.get('pairs') or []
            if not isinstance(pairs, list) or len(pairs) < 2:
                errors.append(ValidationError(step_index=i, field='pairs',
                                              message='pairs должен содержать минимум 2 пары',
                                              severity='critical'))
            else:
                for j, pair in enumerate(pairs):
                    if not isinstance(pair, dict) or not (pair.get('left') or '').strip() or not (pair.get('right') or '').strip():
                        errors.append(ValidationError(step_index=i, field=f'pairs[{j}]',
                                                      message='Каждая пара должна иметь непустые left и right',
                                                      severity='major'))

        # ── sort_items ────────────────────────────────────────────────────
        elif stype == 'sort_items':
            items = step.get('items') or []
            correct_order = step.get('correct_order') or []

            if not isinstance(items, list) or len(items) < 3:
                errors.append(ValidationError(step_index=i, field='items',
                                              message='items должен содержать минимум 3 элемента',
                                              severity='critical'))
            elif not isinstance(correct_order, list) or len(correct_order) != len(items):
                errors.append(ValidationError(step_index=i, field='correct_order',
                                              message=f'correct_order должен содержать те же {len(items)} элементов',
                                              severity='critical'))
            elif set(str(x) for x in items) != set(str(x) for x in correct_order):
                errors.append(ValidationError(step_index=i, field='correct_order',
                                              message='correct_order содержит элементы не из items',
                                              severity='critical'))

        # ── explain ───────────────────────────────────────────────────────
        elif stype == 'explain':
            content = (step.get('content') or '').strip()
            if len(content) < 50:
                warnings.append(ValidationWarning(step_index=i, field='content',
                                                  message=f'Объяснение короткое ({len(content)} сим., рекомендуется 50+)'))

    # ── Level 3: consecutive explain duplication ──────────────────────────
    for i in range(len(steps) - 1):
        if steps[i].get('type') == 'explain' and steps[i + 1].get('type') == 'explain':
            w1 = set((steps[i].get('content') or '').lower().split())
            w2 = set((steps[i + 1].get('content') or '').lower().split())
            if w1 and w2:
                overlap = len(w1 & w2) / max(len(w1), len(w2))
                if overlap > 0.7:
                    warnings.append(ValidationWarning(
                        step_index=i, field='content',
                        message=f'Шаги {i} и {i+1} (explain) похожи на {int(overlap*100)}% — возможное дублирование',
                    ))

    has_blocking = any(e.severity in ('critical', 'major') for e in errors)
    return ValidationResult(valid=not has_blocking, errors=errors, warnings=warnings, auto_fixed=auto_fixed)


def apply_auto_fixes(lesson: dict, fixes: list[AutoFix]) -> dict:
    """Return a copy of lesson with auto-fixes applied."""
    import copy
    lesson = copy.deepcopy(lesson)
    for fix in fixes:
        if 0 <= fix.step_index < len(lesson.get('steps', [])):
            lesson['steps'][fix.step_index][fix.field] = fix.new_value
            logger.info("Auto-fix step %d.%s: %s", fix.step_index, fix.field, fix.description)
    return lesson


def build_retry_hint(errors: list[ValidationError]) -> str:
    hints: list[str] = []
    for e in errors:
        if e.field == 'correct_index':
            hints.append(
                'correct_index — это ИНДЕКС в массиве options, начиная с 0. '
                'Проверь математику вручную и убедись, что правильный ответ присутствует среди вариантов.'
            )
        elif e.field == 'correct_answers':
            hints.append('Проверь математику: вычисли выражение вручную и запиши верный ответ в correct_answers.')
        elif e.field in ('feedback_correct', 'feedback_wrong', 'hint'):
            hints.append(f'Поле {e.field} не должно быть пустым — добавь содержательный текст.')
        elif e.field == 'text':
            hints.append('В шаге fill_blank поле text должно содержать маркер ___ на месте пропуска.')
        elif e.field == 'correct_order':
            hints.append('correct_order должен содержать ровно те же элементы, что и items, в правильном порядке.')
        else:
            hints.append(f'Исправь поле {e.field} в шаге {e.step_index}: {e.message}')
    return '\n'.join(dict.fromkeys(hints))
