import asyncio
import os
import logging
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from middlewares.auth import RoleMiddleware
from handlers import start, admin, ai_chat, dispatch, ads
import ai_analytics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Kunlik hisobot vaqti (Toshkent, UTC+5). Default 21:00.
_REPORT_HOUR_TASHKENT = int(os.getenv("DAILY_REPORT_HOUR", "21"))
_REPORT_HOUR_UTC = (_REPORT_HOUR_TASHKENT - 5) % 24


async def daily_report_loop(bot: Bot):
    """Har kuni belgilangan vaqtda adminlarga AI hisobot yuboradi."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=_REPORT_HOUR_UTC, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            report = ai_analytics.daily_report_text()
            insight = await ai_analytics.generate_insight()
            full = f"{report}\n\n🤖 <b>AI tahlil:</b>\n{insight}"
            # Kunlik hisobot — buyurtmalar guruhining UMUMIY (General) qismiga.
            # Guruh ulanmagan bo'lsa — adminlar shaxsiy chatiga (fallback).
            if not await dispatch.post_to_orders_group(bot, full):
                sent = 0
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, full)
                        sent += 1
                    except Exception as e:
                        logger.warning("Kunlik hisobot %s ga yuborilmadi: %s", admin_id, e)
                logger.info("Kunlik hisobot yuborildi (%s admin).", sent)
            else:
                logger.info("Kunlik hisobot buyurtmalar guruhiga (General) yuborildi.")
        except Exception as e:
            logger.error(f"daily_report xatolik: {e}")


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

    # Routerlar: dispatch (guruh + statuslar), keyin ads (reklama —
    # admin'dan oldin, holat/forward handlerlari prioritet olishi uchun)
    dp.include_router(dispatch.router)
    dp.include_router(ads.router)
    dp.include_router(admin.router)
    dp.include_router(ai_chat.router)
    dp.include_router(start.router)

    logger.info("Bot ishga tushmoqda...")
    report_task = asyncio.create_task(daily_report_loop(bot))
    followup_task = asyncio.create_task(ai_chat.followup_loop(bot))
    ads_task = asyncio.create_task(ads.ads_loop(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        report_task.cancel()
        followup_task.cancel()
        ads_task.cancel()
        await bot.session.close()


def _start_static_web():
    """Statik saytni (website/index.html) shu jarayonда beradi — alohida
    'web' dyno o'rniga. Heroku 'web' dyno $PORT'ni 60s ichida ushlashi shart,
    shuning uchun bot polling'idan OLDIN, alohida thread'da ishga tushiramiz."""
    try:
        import web_server
        web_server.main()  # serve_forever (bloklaydi — shuning uchun threadда)
    except Exception as e:
        logger.error("Statik web server xatolik: %s", e)


if __name__ == "__main__":
    # Bitta dyno: sayt (web thread) + bot (asyncio). Xarajatni 2x kamaytiradi.
    import threading
    threading.Thread(target=_start_static_web, daemon=True).start()
    asyncio.run(main())
