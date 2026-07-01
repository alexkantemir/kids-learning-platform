import json
import uuid
import logging
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
TOKEN_CACHE_KEY = "gigachat:access_token"
TOKEN_TTL_SECONDS = 1700  # slightly less than 1800 to refresh before expiry


async def _get_redis() -> aioredis.Redis:
    return await aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_gigachat_token() -> str:
    """Get GigaChat access token, using Redis cache."""
    redis = await _get_redis()
    try:
        cached = await redis.get(TOKEN_CACHE_KEY)
        if cached:
            return cached

        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                GIGACHAT_AUTH_URL,
                headers={
                    "Authorization": f"Basic {settings.GIGACHAT_CLIENT_SECRET}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": settings.GIGACHAT_SCOPE},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            token = data["access_token"]

        await redis.setex(TOKEN_CACHE_KEY, TOKEN_TTL_SECONDS, token)
        return token
    finally:
        await redis.aclose()


async def generate_lesson_raw(prompt: str) -> dict[str, Any]:
    """Call GigaChat API and return parsed JSON response."""
    token = await get_gigachat_token()

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            GIGACHAT_CHAT_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "model": "GigaChat",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ты — помощник учителя для детей. Ты создаёшь увлекательные уроки в игровой форме. "
                            "Всегда отвечай строго в формате JSON без дополнительного текста."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 3000,
            },
            timeout=60.0,
        )
        response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Extract JSON from content (model may wrap it in ```json ... ```)
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

    return json.loads(content)
