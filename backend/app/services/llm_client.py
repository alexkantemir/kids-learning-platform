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

import httpx

from app.core.config import settings
from app.services.gigachat import generate_lesson_raw as _gigachat_generate

logger = logging.getLogger(__name__)

PROXYAPI_MESSAGES_URL = "https://api.proxyapi.ru/anthropic/v1/messages"
PROXYAPI_MAX_TOKENS = 4096
PROXYAPI_TIMEOUT_SECONDS = 90.0


def _strip_markdown_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
    return content


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
    # Claude (через этот прокси) может вернуть "thinking"-блок ПЕРЕД текстовым
    # (extended thinking) — content[0] не всегда содержит ответ. Найдено
    # сессией 1 Этапа 2 живым смоук-тестом: content = [{"type":"thinking",...},
    # {"type":"text","text":...}]. Ищем блок по типу, не по индексу.
    text_block = next((b for b in data.get("content", []) if b.get("type") == "text"), None)
    if text_block is None:
        raise RuntimeError(f"В ответе proxyapi нет текстового блока: {data}")
    content = _strip_markdown_fence(text_block["text"])
    return json.loads(content)


async def generate_llm_raw(prompt: str) -> dict:
    """Единая точка входа для нового пайплайна (lesson_pipeline.py).
    Бэкенд выбирается settings.LLM_PROVIDER — пайплайн не знает деталей
    ни одного из них."""
    if settings.LLM_PROVIDER == "proxyapi":
        return await _proxyapi_generate(prompt)
    return await _gigachat_generate(prompt)
