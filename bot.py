import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from middlewares.auth import RoleMiddleware
from handlers import start, operator, tariff, number, location, admin, courier, ai_chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middleware — hamma updatega role ma'lumotini qo'shadi
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())

    # Routerlar: admin va courier birinchi (prioritet)
    dp.include_router(admin.router)
    dp.include_router(courier.router)
    dp.include_router(ai_chat.router)
    dp.include_router(start.router)
    dp.include_router(operator.router)
    dp.include_router(tariff.router)
    dp.include_router(number.router)
    dp.include_router(location.router)

    logger.info("Bot ishga tushmoqda...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
