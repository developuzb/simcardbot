from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import ADMIN_IDS


class RoleMiddleware(BaseMiddleware):
    """Har bir update'ga is_admin bayrog'ini qo'shadi.

    Kuryerlar endi alohida ro'yxat emas — kuryerlar guruhi a'zoligi
    orqali aniqlanadi (dispatch.py). Shu sababli bu yerda Sheets'ga
    murojaat yo'q (har xabarda sekinlik va xatolik bermaydi).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        data["is_admin"] = bool(user and user.id in ADMIN_IDS)
        return await handler(event, data)
