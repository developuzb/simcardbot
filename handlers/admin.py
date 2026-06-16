import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import AdminState
from keyboards import (
    admin_menu_keyboard, admin_orders_filter_keyboard, orders_list_keyboard,
    office_menu_keyboard, office_location_request_keyboard, remove_keyboard,
    analytics_menu_keyboard,
)
import settings_store
import ai_analytics
from orders_db import get_all_orders, get_order_by_num, get_stats
from utils import format_price

logger = logging.getLogger(__name__)
router = Router()

_STATUS_ICONS = {
    "Yangi": "🆕", "Tasdiqlangan": "📢", "Kuryerda": "🚴", "Yo'lda": "🚗",
    "Yetkazildi": "✅", "Mijoz yo'q": "🚫", "Bekor": "❌", "Hudud tashqarisida": "🟠",
}


# ─── /admin BUYRUG'I ──────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        if message.chat.type == "private":
            await message.answer("⛔ Ruxsat yo'q.")
        return  # guruhda — jim
    # Faqat shaxsiy chat yoki buyurtmalar guruhida (boshqa guruhlarда emas)
    if message.chat.type != "private" and message.chat.id != settings_store.get_orders_group():
        return
    await state.set_state(AdminState.main_menu)
    await _show_admin_menu(message)


async def _show_admin_menu(target):
    text = "🔧 <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:"
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=admin_menu_keyboard())
        except Exception:
            await target.message.answer(text, reply_markup=admin_menu_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_back_menu")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
    await state.set_state(AdminState.main_menu)
    await _show_admin_menu(callback)


# ─── STATISTIKA ───────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def show_stats(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    stats = await get_stats()
    status_lines = "\n".join(
        f"{_STATUS_ICONS.get(s, '•')} {s}: <b>{c}</b>"
        for s, c in stats["by_status"].items()
    )
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{stats['total']}</b>\n\n"
        f"{status_lines}\n\n"
        f"💰 Jami daromad (yetkazilgan): <b>{format_price(stats['revenue'])}</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ─── BUYURTMALAR (faqat ko'rish) ─────────────────────────────────

@router.callback_query(F.data == "adm_orders")
async def show_orders_filter(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.viewing_orders)
    await callback.message.edit_text(
        "📋 <b>Buyurtmalar</b>\n\nStatus bo'yicha filtrlang:",
        reply_markup=admin_orders_filter_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_filter_"))
async def filter_orders(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    status_key = callback.data.replace("adm_filter_", "")
    status = None if status_key == "all" else status_key

    orders = await get_all_orders(status=status)
    if not orders:
        await callback.answer(f"'{status or 'hamma'}' statusda buyurtma yo'q.", show_alert=True)
        return

    await state.update_data(orders_status=status_key)
    label = status or "Barchasi"
    await callback.message.edit_text(
        f"📋 <b>{label}</b> buyurtmalar ({len(orders)} ta):",
        reply_markup=orders_list_keyboard(orders, page=0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_page_"))
async def paginate_orders(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    page = int(callback.data.replace("adm_page_", ""))
    data = await state.get_data()
    status_key = data.get("orders_status")
    status = None if status_key == "all" else status_key
    orders = await get_all_orders(status=status)
    await callback.message.edit_reply_markup(reply_markup=orders_list_keyboard(orders, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ord_"))
async def show_order_detail(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_ord_", "")
    order = await get_order_by_num(order_num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)

    icon = _STATUS_ICONS.get(order["status"], "📦")
    promo_line = "🎁 1+1 aksiya\n" if order.get("promo") else ""
    courier_line = f"🚴 <b>Kuryer:</b> {order['courier_name']}\n" if order.get("courier_name") else ""
    rating_line = f"⭐ <b>Baho:</b> {'⭐' * int(order['rating'])}\n" if order.get("rating") else ""
    maps = ""
    if order.get("lat") and order.get("lon"):
        maps = f"🗺 <a href='https://maps.google.com/?q={order['lat']},{order['lon']}'>Xaritada ochish</a>\n"

    text = (
        f"{icon} <b>Buyurtma #{order['num']}</b>\n"
        f"🕐 {order['date']} {order['time']}\n\n"
        f"👤 <b>Mijoz:</b> {order['name']}\n"
        f"📞 <b>Tel:</b> <code>{order['phone']}</code>\n"
        f"🆔 <b>TG ID:</b> {order['user_id']}\n\n"
        f"📡 <b>Operator:</b> {order['operator']}\n"
        f"📦 <b>Tarif:</b> {order['tariff']}\n"
        f"{promo_line}"
        f"📍 <b>Hudud:</b> {order['region']}\n"
        f"{maps}"
        f"🚚 <b>Yetkazish:</b> {order.get('delivery_type', '—')} — {format_price(int(order['delivery_price'] or 0))}\n"
        f"💰 <b>Tarif:</b> {format_price(int(order['tariff_price'] or 0))}\n"
        f"💳 <b>Jami:</b> {format_price(int(order['total'] or 0))}\n\n"
        f"🔖 <b>Status:</b> {order['status']}\n"
        f"{courier_line}{rating_line}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Buyurtmalarga", callback_data="adm_orders")
    kb.button(text="🏠 Menyu", callback_data="adm_back_menu")
    kb.adjust(2)
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), disable_web_page_preview=True)
    await callback.answer()


# ─── AI ANALITIKA ────────────────────────────────────────────────

@router.callback_query(F.data == "adm_analytics")
async def show_analytics_menu(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.main_menu)
    await callback.message.edit_text(
        "📈 <b>AI Analitika</b>\n\n"
        "🤖 <b>AI Insight</b> — Claude buyurtma va suhbatlarni tahlil qilib, "
        "biznes tavsiya beradi.\n"
        "📊 <b>AI Statistika</b> — raqamli ko'rsatkichlar.\n\n"
        "Quyidan tanlang 👇",
        reply_markup=analytics_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_an_stats")
async def show_analytics_stats(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await callback.message.edit_text(ai_analytics.format_stats(), reply_markup=analytics_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_an_insight")
async def show_analytics_insight(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await callback.answer("🤖 Tahlil qilinmoqda...")
    try:
        await callback.message.edit_text("🤖 AI tahlil qilmoqda, bir lahza...")
    except Exception:
        pass
    insight = await ai_analytics.generate_insight()
    try:
        await callback.message.edit_text(
            f"🤖 <b>AI Insight</b>\n\n{insight}", reply_markup=analytics_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            f"🤖 <b>AI Insight</b>\n\n{insight}", reply_markup=analytics_menu_keyboard(),
        )


# ─── OFIS LOKATSIYASI ────────────────────────────────────────────

@router.callback_query(F.data == "adm_office")
async def show_office(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.main_menu)
    o = settings_store.get_office()
    text = (
        "📍 <b>Ofis lokatsiyasi va yetkazish hududi</b>\n\n"
        f"🌐 Koordinata: <code>{o['lat']:.5f}, {o['lon']:.5f}</code>\n"
        f"📏 Radius: <b>{o['radius_km']:.0f} km</b>\n\n"
        "Mijoz lokatsiyasi shu nuqtadan belgilangan radius ichida bo'lsa — "
        "buyurtma qabul qilinadi. Uzoq bo'lsa, mijoz admin bilan bog'lanishga yo'naltiriladi.\n\n"
        "Quyidan o'zgartiring 👇"
    )
    await callback.message.edit_text(text, reply_markup=office_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_office_set")
async def office_set_prompt(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.setting_office_location)
    await callback.message.answer(
        "📍 <b>Ofis lokatsiyasini yuboring</b>\n\n"
        "Pastdagi tugmani bosib, ofisingiz turgan joyni yuboring. "
        "Shu nuqta yetkazish hududining markazi bo'ladi.",
        reply_markup=office_location_request_keyboard(),
    )
    await callback.answer()


@router.message(AdminState.setting_office_location, F.location)
async def office_set_location(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    lat = message.location.latitude
    lon = message.location.longitude
    o = settings_store.get_office()
    ok = settings_store.set_office(lat, lon)
    logger.info("OFIS_LOKATSIYASI_SET lat=%s lon=%s radius=%s", lat, lon, o["radius_km"])
    await state.set_state(AdminState.main_menu)
    if ok:
        await message.answer(
            "✅ <b>Ofis lokatsiyasi saqlandi!</b>\n\n"
            f"🌐 Koordinata: <code>{lat:.6f}, {lon:.6f}</code>\n"
            f"📏 Radius: <b>{o['radius_km']:.0f} km</b>\n\n"
            "⚠️ <i>Doimiy bo'lishi uchun shu koordinatani DELIVERY_LAT/DELIVERY_LON "
            "env'ga yozish kerak (restartда saqlanishi uchun).</i>",
            reply_markup=remove_keyboard(),
        )
        await message.answer("🔧 Admin panel:", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("⚠️ Saqlashda xatolik.", reply_markup=remove_keyboard())


@router.callback_query(F.data == "adm_office_radius")
async def office_radius_prompt(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.setting_office_radius)
    o = settings_store.get_office()
    await callback.message.edit_text(
        f"📏 <b>Yetkazish radiusi</b>\n\n"
        f"Joriy: <b>{o['radius_km']:.0f} km</b>\n\n"
        "Yangi radiusni km da kiriting (faqat raqam). <i>Masalan: 12</i>\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdminState.setting_office_radius)
async def office_set_radius(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        radius = float(raw)
        if radius <= 0 or radius > 200:
            raise ValueError
    except ValueError:
        await message.answer("❗ 0 dan 200 gacha raqam kiriting. Masalan: 12")
        return
    settings_store.set_radius(radius)
    await state.set_state(AdminState.main_menu)
    await message.answer(
        f"✅ Radius <b>{radius:.0f} km</b> qilib saqlandi.",
        reply_markup=admin_menu_keyboard(),
    )


# ─── FILE ID OLISH (rasm/fayl yuborilsa) ────────────────────────

@router.message(F.photo, F.chat.type == "private")
async def photo_file_id(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    fid = message.photo[-1].file_id
    await state.update_data(last_photo_id=fid)
    kb = InlineKeyboardBuilder()
    kb.button(text="🖼 Bosh sahifa rasmi qilish", callback_data="adm_set_welcome_photo")
    kb.adjust(1)
    await message.reply(
        f"🆔 <b>File ID:</b>\n<code>{fid}</code>\n\n"
        "Bosh sahifaga qo'yish uchun tugmani bosing 👇",
        reply_markup=kb.as_markup(),
    )


@router.message(F.document, F.chat.type == "private")
async def document_file_id(message: Message, is_admin: bool = False):
    if not is_admin:
        return
    await message.reply(f"🆔 <b>File ID:</b>\n<code>{message.document.file_id}</code>")


@router.callback_query(F.data == "adm_set_welcome_photo")
async def set_welcome_photo(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    data = await state.get_data()
    fid = data.get("last_photo_id")
    if not fid:
        return await callback.answer("Avval rasm yuboring.", show_alert=True)
    if settings_store.set_welcome_photo(fid):
        logger.info("WELCOME_PHOTO_SET file_id=%s", fid)
        await callback.answer("✅ O'rnatildi!")
        await callback.message.answer(
            "✅ <b>Bosh sahifa rasmi o'rnatildi!</b> /start bosib ko'ring.\n\n"
            "⚠️ <i>Doimiy bo'lishi uchun bu file_id ni WELCOME_PHOTO_ID env'ga yozing.</i>"
        )
    else:
        await callback.answer("Saqlashda xatolik.", show_alert=True)


# ─── BROADCAST ───────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.broadcasting)
    await callback.message.edit_text(
        "📢 <b>Xabar yuborish</b>\n\n"
        "Yuborishni istagan xabaringizni yozing.\n"
        "Barcha buyurtma bergan foydalanuvchilarga yetkaziladi.\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdminState.broadcasting)
async def broadcast_message(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    orders = await get_all_orders()
    user_ids = {o["user_id"] for o in orders if o.get("user_id")}

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.bot.send_message(
                int(uid),
                f"📢 <b>Admin xabari:</b>\n\n{message.text or message.caption or ''}",
            )
            sent += 1
        except Exception:
            failed += 1

    await state.set_state(AdminState.main_menu)
    await message.answer(
        f"📢 Xabar yuborildi:\n✅ Muvaffaqiyatli: {sent}\n❌ Yuborilmadi: {failed}",
        reply_markup=admin_menu_keyboard(),
    )
