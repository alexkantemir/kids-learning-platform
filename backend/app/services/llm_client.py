"""
Абстракция LLM-клиента (TASK_STAGE2.md, Этап 2, сессия 1). Новый пайплайн
(lesson_pipeline.py) зовёт только generate_llm_raw() и не знает, какой
бэкенд под ней — GigaChat (settings.LLM_PROVIDER="gigachat", по умолчанию)
или proxyapi.ru (settings.LLM_PROVIDER="proxyapi", сильная модель, цель
Этапа 2). Старый пайплайн (lesson_generator.py) НЕ тронут — по-прежнему
зовёт app.services.gigachat.generate_lesson_raw() напрямую, независимо
от этого переключателя (он остаётся эталоном для сравнения и запасным
путём, см. TASK_STAGE2.md, «Ограничения»).

proxyapi.ru предоставляет Anthropic-совместимый API (Messages API,
1-в-1 формат официального Anthropic SDK) — см. https://proxyapi.ru/docs/anthropic-text-generation.
Ключ и модель — в .env, в git/логи не попадают.
"""
import json
import logging
import re

import httpx

from app.core.config import settings
from app.services.gigachat import generate_lesson_raw as _gigachat_generate

logger = logging.getLogger(__name__)

PROXYAPI_MESSAGES_URL = "https://api.proxyapi.ru/anthropic/v1/messages"
PROXYAPI_MAX_TOKENS = 4096
PROXYAPI_TIMEOUT_SECONDS = 90.0

# Цены proxyapi.ru, ₽ за 1M токенов (сверено WebFetch в сессии 1 Этапа 2,
# https://proxyapi.ru/pricing/list, 2026-07-22). Обновлять при смене модели
# или если цены на сайте изменятся — это не автоматический прайс-лист.
PROXYAPI_PRICING_RUB_PER_1M = {
    "claude-sonnet-5": {"input": 800, "output": 4500},
    "claude-haiku-4-5": {"input": 295, "output": 1474},
    "claude-haiku-4-5-20251001": {"input": 295, "output": 1474},
}


class BudgetExceededError(RuntimeError):
    """Достигнут жёсткий лимит бюджета — предохранитель (TASK_STAGE2.md,
    сессия 2) перед платным замером сессии 3."""


class CostGuard:
    """Считает потраченное в рублях по логу usage и останавливает прогон,
    как только сумма достигает limit_rub. Подключается к llm_client через
    set_cost_guard() — по умолчанию гвардов нет (проды/дев-тесты с GigaChat
    ничего не платят и не должны спотыкаться об эту защиту)."""

    def __init__(self, limit_rub: float):
        self.limit_rub = limit_rub
        self.usage_log: list[dict] = []

    def record(self, model: str, usage: dict) -> None:
        entry = {
            "model": model,
            "input_tokens": usage.get("input_tokens", 0) or 0,
            "output_tokens": usage.get("output_tokens", 0) or 0,
        }
        self.usage_log.append(entry)
        cost = self.total_cost_rub()
        if cost >= self.limit_rub:
            raise BudgetExceededError(
                f"Достигнут лимит бюджета: потрачено ~{cost:.2f}₽ >= лимита {self.limit_rub}₽ "
                f"(после {len(self.usage_log)} вызовов). Прогон остановлен предохранителем."
            )

    def total_cost_rub(self) -> float:
        return estimate_cost_rub(self.usage_log)


def estimate_cost_rub(usage_log: list[dict]) -> float:
    """Грубая оценка по прайс-листу выше. Не заменяет фактический счёт
    proxyapi.ru — только ориентир для предохранителя и отчётов."""
    total = 0.0
    for entry in usage_log:
        pricing = PROXYAPI_PRICING_RUB_PER_1M.get(entry["model"])
        if not pricing:
            continue
        total += entry["input_tokens"] / 1_000_000 * pricing["input"]
        total += entry["output_tokens"] / 1_000_000 * pricing["output"]
    return total


_cost_guard: CostGuard | None = None


def set_cost_guard(guard: CostGuard | None) -> None:
    """Скрипты замера вызывают это ДО прогона, чтобы включить предохранитель
    (например, set_cost_guard(CostGuard(limit_rub=900)) — жёсткий стоп до
    900₽ перед полным платным замером сессии 3, TASK_STAGE2.md)."""
    global _cost_guard
    _cost_guard = guard


def get_cost_guard() -> CostGuard | None:
    return _cost_guard


def _strip_markdown_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
    return content


_TRAILING_COMMA_QUOTE_RE = re.compile(r',\s*"\s*([}\]])')


def _repair_trailing_comma_quote(content: str) -> str:
    """Sonnet (через этот прокси) иногда заканчивает объект висячим ',"'
    перед закрывающей скобкой — как будто начал писать ещё один ключ и
    оборвался (например '..."reasoning":"текст","}' вместо '..."текст"}').
    Не обрыв по max_tokens (usage показывает маленький ответ, есть
    stop_reason=end_turn) — стабильно воспроизводится на нескольких разных
    ответах судьи в одном прогоне (сессия 2 Этапа 2). Применяется ТОЛЬКО
    как fallback, если обычный json.loads уже упал — не трогаем валидный
    JSON на всякий случай."""
    return _TRAILING_COMMA_QUOTE_RE.sub(r'\1', content)


def _parse_json_response(content: str) -> dict:
    """strict=False — Sonnet иногда вставляет буквальный перевод строки
    внутри значения JSON-строки (например, в длинном "content" explain-блока)
    вместо экранированного \\n — формально невалидный JSON, но однозначно
    разбираемый (найдено живым прогоном сессии 2 Этапа 2, тема "Проценты",
    упала с "Invalid control character"). Если и это не парсится — пробуем
    repair висячей запятой-кавычки (см. _repair_trailing_comma_quote) —
    другой, отдельно наблюдавшийся в том же прогоне сбой формата."""
    try:
        return json.loads(content, strict=False)
    except json.JSONDecodeError:
        repaired = _repair_trailing_comma_quote(content)
        return json.loads(repaired, strict=False)


async def _proxyapi_generate(prompt: str) -> dict:
    """Вызов сильной модели через proxyapi.ru (Anthropic Messages API)."""
    if not settings.PROXYAPI_KEY:
        raise RuntimeError(
            "settings.LLM_PROVIDER=proxyapi, но PROXYAPI_KEY пуст — добавь ключ в .env"
        )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            PROXYAPI_MESSAGES_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.PROXYAPI_KEY}",
            },
            json={
                "model": settings.PROXYAPI_MODEL,
                "max_tokens": PROXYAPI_MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=PROXYAPI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    data = response.json()

    # Записываем usage СРАЗУ после получения ответа — деньги уже потрачены,
    # независимо от того, распарсится ли контент ниже (сессия 2, Этапа 2:
    # предохранитель бюджета перед платным замером сессии 3). Если гварда
    # нет (по умолчанию) — просто no-op.
    if _cost_guard is not None:
        _cost_guard.record(settings.PROXYAPI_MODEL, data.get("usage", {}))

    # Claude (через этот прокси) может вернуть "thinking"-блок ПЕРЕД текстовым
    # (extended thinking) — content[0] не всегда содержит ответ. Найдено
    # сессией 1 Этапа 2 живым смоук-тестом: content = [{"type":"thinking",...},
    # {"type":"text","text":...}]. Ищем блок по типу, не по индексу.
    text_block = next((b for b in data.get("content", []) if b.get("type") == "text"), None)
    if text_block is None:
        raise RuntimeError(f"В ответе proxyapi нет текстового блока: {data}")
    content = _strip_markdown_fence(text_block["text"])
    return _parse_json_response(content)


async def generate_llm_raw(prompt: str) -> dict:
    """Единая точка входа для нового пайплайна (lesson_pipeline.py).
    Бэкенд выбирается settings.LLM_PROVIDER — пайплайн не знает деталей
    ни одного из них."""
    if settings.LLM_PROVIDER == "proxyapi":
        return await _proxyapi_generate(prompt)
    return await _gigachat_generate(prompt)
