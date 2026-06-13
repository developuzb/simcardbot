"""Umumiy AI client — OpenAI-compatible API orqali.

Hozir BEPUL Google Gemini ishlatilmoqda (gemini-2.5-flash), uning
OpenAI-compatible endpointi orqali:
https://generativelanguage.googleapis.com/v1beta/openai/
Sozlamalar config.py / .env dan o'qiladi, shuning uchun boshqa
OpenAI-compatible provayderga o'tish uchun faqat .env ni o'zgartirish kifoya.
"""
from openai import AsyncOpenAI
from config import TOKENMIX_API_KEY, TOKENMIX_BASE_URL, TOKENMIX_MODEL

MODEL = TOKENMIX_MODEL
BASE_URL = TOKENMIX_BASE_URL

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=TOKENMIX_API_KEY,
            base_url=BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
    return _client


async def complete(system: str, messages: list, max_tokens: int = 512) -> str:
    """Sof matn javob qaytaradi.

    OpenAI-compatible endpoint ga mos ravishda system prompt
    xabarlarni boshiga qo'shiladi.
    """
    client = get_client()
    full_messages = [{"role": "system", "content": system}] + messages
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=full_messages,
    )
    content = resp.choices[0].message.content
    return (content or "").strip()
