from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import ADMIN_IDS
from sheets_handler import is_courier, get_courier


class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            data["is_admin"] = user.id in ADMIN_IDS
            data["is_courier"] = await is_courier(user.id)
            data["courier_info"] = await get_courier(user.id) if data["is_courier"] else None
        else:
            data["is_admin"] = False
            data["is_courier"] = False
            data["courier_info"] = None

        return await handler(event, data)
