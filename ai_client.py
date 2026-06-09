"""Umumiy Anthropic client — AI chat va AI analitika shu yerdan foydalanadi.

Proxy (aiprimetech.io) bilan ishlaydi. Model: claude-sonnet-4-6
(haiku bu proxy'da buzilgan, shuning uchun sonnet ishlatamiz).
"""
import anthropic
from config import ANTHROPIC_API_KEY

MODEL = "claude-sonnet-4-6"
BASE_URL = "https://aiprimetech.io"

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
    return _client


async def complete(system: str, messages: list, max_tokens: int = 512) -> str:
    """Sof matn javob qaytaradi."""
    client = get_client()
    resp = await client.messages.create(
        model=MODEL, max_tokens=max_tokens,
        system=system, messages=messages,
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
