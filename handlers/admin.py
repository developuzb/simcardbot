from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import AdminState
from keyboards import (
    admin_menu_keyboard, admin_orders_filter_keyboard, admin_order_detail_keyboard,
    admin_couriers_keyboard, admin_courier_detail_keyboard,
    select_courier_keyboard, orders_list_keyboard,
    office_menu_keyboard, office_location_request_keyboard, remove_keyboard,
    analytics_menu_keyboard,
)
import settings_store
import ai_analytics
from sheets_handler import (
    get_all_orders, get_order_by_num, update_order,
    get_all_couriers, get_courier, add_courier, remove_courier,
    get_stats, update_courier_completed, invalidate_courier_cache,
    get_orders_by_courier,
)
from utils import format_price
import logging

logger = logging.getLogger(__name__)
router = Router()


# ─── /admin BUYRUG'I ──────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await message.answer("⛔ Ruxsat yo'q.")
        return
    await state.set_state(AdminState.main_menu)
    await _show_admin_menu(message)


async def _show_admin_menu(target: Message | CallbackQuery):
    text = "🔧 <b>Admin panel</b>\n\nQuyidagi bo'limlardan birini tanlang:"
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=admin_menu_keyboard())
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
    yolda = stats["Yo'lda"]
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{stats['total']}</b>\n\n"
        f"🆕 Yangi: <b>{stats['Yangi']}</b>\n"
        f"✅ Tayinlandi: <b>{stats['Tayinlandi']}</b>\n"
        f"🚗 Yo'lda: <b>{yolda}</b>\n"
        f"✔️ Yetkazildi: <b>{stats['Yetkazildi']}</b>\n"
        f"❌ Bekor: <b>{stats['Bekor']}</b>\n\n"
        f"💰 Jami daromad: <b>{format_price(stats['revenue'])}</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ─── BUYURTMALAR ─────────────────────────────────────────────────

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
        label = status or "hamma"
        await callback.answer(f"'{label}' statusda buyurtma yo'q.", show_alert=True)
        return

    await state.update_data(filtered_orders=[o["num"] for o in orders], orders_page=0, orders_status=status_key)
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
    await state.update_data(orders_page=page)
    await callback.message.edit_reply_markup(reply_markup=orders_list_keyboard(orders, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ord_"))
async def show_order_detail(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_ord_", "")
    order = await get_order_by_num(order_num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)

    courier_line = ""
    if order["courier_name"]:
        courier_line = f"\n🚴 <b>Kuryer:</b> {order['courier_name']} (ID: {order['courier_id']})"

    text = (
        f"📦 <b>Buyurtma #{order['num']}</b>\n"
        f"🕐 {order['date']} {order['time']}\n\n"
        f"👤 <b>Mijoz:</b> {order['name']}\n"
        f"📞 <b>Tel:</b> {order['phone']}\n"
        f"🆔 <b>TG ID:</b> {order['user_id']}\n\n"
        f"📡 <b>Operator:</b> {order['operator']}\n"
        f"📦 <b>Tarif:</b> {order['tariff']}\n"
        f"📱 <b>Raqam:</b> {order['sim']}\n\n"
        f"📍 <b>Hudud:</b> {order['region']}\n"
        f"🚚 <b>Yetkazish:</b> {format_price(int(order['delivery_price'] or 0))}\n"
        f"💰 <b>Tarif:</b> {format_price(int(order['tariff_price'] or 0))}\n"
        f"💳 <b>Jami:</b> {format_price(int(order['total'] or 0))}\n\n"
        f"🔖 <b>Status:</b> {order['status']}"
        f"{courier_line}"
    )
    await state.set_state(AdminState.viewing_order_detail)
    await state.update_data(current_order_num=order_num)
    await callback.message.edit_text(
        text,
        reply_markup=admin_order_detail_keyboard(order_num, order["status"]),
    )
    await callback.answer()


# ─── BUYURTMA AMALLAR ────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_accept_"))
async def accept_order(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_accept_", "")
    ok = await update_order(order_num, {"status": "Tayinlandi"})
    if ok:
        await callback.answer("✅ Buyurtma qabul qilindi!")
        order = await get_order_by_num(order_num)
        if order and order["user_id"]:
            try:
                await callback.bot.send_message(
                    int(order["user_id"]),
                    f"✅ Buyurtmangiz #{order_num} qabul qilindi! Kuryer tez orada tayinlanadi.",
                )
            except Exception:
                pass
        # Detail sahifasini yangilash
        await show_order_detail(callback, state, is_admin=True)
    else:
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


@router.callback_query(F.data.startswith("adm_cancel_"))
async def cancel_order_admin(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_cancel_", "")
    ok = await update_order(order_num, {"status": "Bekor"})
    if ok:
        await callback.answer("❌ Bekor qilindi.")
        order = await get_order_by_num(order_num)
        if order and order["user_id"]:
            try:
                await callback.bot.send_message(
                    int(order["user_id"]),
                    f"❌ Buyurtmangiz #{order_num} bekor qilindi. Batafsil: /start → Aloqa.",
                )
            except Exception:
                pass
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Buyurtmalarga", callback_data="adm_orders")
        await callback.message.edit_text(
            f"❌ Buyurtma #{order_num} bekor qilindi.",
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("adm_delivered_"))
async def mark_delivered(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_delivered_", "")
    order = await get_order_by_num(order_num)
    ok = await update_order(order_num, {"status": "Yetkazildi"})
    if ok:
        if order and order["courier_id"]:
            await update_courier_completed(order["courier_id"])
        await callback.answer("✔️ Yetkazildi deb belgilandi!")
        if order and order["user_id"]:
            try:
                await callback.bot.send_message(
                    int(order["user_id"]),
                    f"🎉 Buyurtmangiz #{order_num} yetkazildi! Xarid uchun rahmat!",
                )
            except Exception:
                pass
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Buyurtmalarga", callback_data="adm_orders")
        await callback.message.edit_text(
            f"✔️ Buyurtma #{order_num} yetkazildi deb belgilandi.",
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


# ─── KURYER TAYINLASH ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_assign_"))
async def assign_courier_prompt(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("adm_assign_", "")
    couriers = await get_all_couriers()
    active = [c for c in couriers if c.get("status") == "Faol"]
    if not active:
        return await callback.answer("Faol kuryer yo'q. Avval kuryer qo'shing.", show_alert=True)
    await state.set_state(AdminState.assigning_courier)
    await state.update_data(assigning_order_num=order_num)
    await callback.message.edit_text(
        f"🚴 <b>#{order_num}</b> buyurtmaga kuryer tanlang:",
        reply_markup=select_courier_keyboard(active, order_num),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_set_cur_"))
async def set_courier(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    parts = callback.data.replace("adm_set_cur_", "").split("_", 1)
    order_num, courier_id = parts[0], parts[1]

    courier = await get_courier(courier_id)
    if not courier:
        return await callback.answer("Kuryer topilmadi.", show_alert=True)

    ok = await update_order(order_num, {
        "status": "Tayinlandi",
        "courier_id": courier_id,
        "courier_name": courier["name"],
    })
    if ok:
        await callback.answer(f"✅ {courier['name']} tayinlandi!")
        order = await get_order_by_num(order_num)
        try:
            courier_name = courier["name"]
            region = order["region"] if order else ""
            phone = order["phone"] if order else ""
            sim = order["sim"] if order else ""
            name = order["name"] if order else ""
            msg = (
                f"📦 <b>Yangi buyurtma tayinlandi!</b>\n\n"
                f"#{order_num} — {name}\n"
                f"📍 Hudud: {region}\n"
                f"📞 Tel: {phone}\n"
                f"📱 Sim: {sim}\n\n"
                f"Buyurtmani ko'rish: /courier"
            )
            await callback.bot.send_message(int(courier_id), msg)
        except Exception:
            pass
        if order and order["user_id"]:
            try:
                await callback.bot.send_message(
                    int(order["user_id"]),
                    f"🚴 Buyurtmangiz #{order_num} uchun kuryer tayinlandi!\n"
                    f"Kuryer: <b>{courier['name']}</b>\n"
                    f"Tel: {courier['phone']}",
                )
            except Exception:
                pass
        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Buyurtma tafsiloti", callback_data=f"adm_ord_{order_num}")
        kb.button(text="⬅️ Menyu", callback_data="adm_back_menu")
        kb.adjust(1)
        await callback.message.edit_text(
            f"✅ #{order_num} buyurtmaga <b>{courier['name']}</b> tayinlandi.",
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


# ─── KURYERLAR BOSHQARUVI ────────────────────────────────────────

@router.callback_query(F.data == "adm_couriers")
async def show_couriers(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.managing_couriers)
    couriers = await get_all_couriers()
    text = f"🚴 <b>Kuryerlar</b> ({len(couriers)} ta)\n\nBirini tanlang yoki yangi qo'shing:"
    await callback.message.edit_text(text, reply_markup=admin_couriers_keyboard(couriers))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cur_"))
async def show_courier_detail(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    courier_id = callback.data.replace("adm_cur_", "")
    courier = await get_courier(courier_id)
    if not courier:
        return await callback.answer("Kuryer topilmadi.", show_alert=True)

    orders = await get_orders_by_courier(courier_id)
    active_count = sum(1 for o in orders if o["status"] in ("Tayinlandi", "Yo'lda"))

    text = (
        f"🚴 <b>{courier['name']}</b>\n\n"
        f"📞 Tel: {courier['phone']}\n"
        f"📍 Hududlar: {courier['regions']}\n"
        f"🟢 Holat: {courier['status']}\n"
        f"✔️ Bajarilgan: {courier['completed']} ta\n"
        f"🔄 Hozirgi faol: {active_count} ta\n"
        f"📅 Qo'shilgan: {courier['joined']}"
    )
    await callback.message.edit_text(text, reply_markup=admin_courier_detail_keyboard(courier_id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_del_cur_"))
async def delete_courier(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    courier_id = callback.data.replace("adm_del_cur_", "")
    courier = await get_courier(courier_id)
    name = courier["name"] if courier else courier_id
    ok = await remove_courier(courier_id)
    invalidate_courier_cache()
    if ok:
        await callback.answer(f"🗑 {name} o'chirildi.")
        couriers = await get_all_couriers()
        await callback.message.edit_text(
            f"🚴 <b>Kuryerlar</b> ({len(couriers)} ta):",
            reply_markup=admin_couriers_keyboard(couriers),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


@router.callback_query(F.data == "adm_add_courier")
async def start_add_courier(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.adding_courier_id)
    await callback.message.edit_text(
        "➕ <b>Yangi kuryer qo'shish</b>\n\n"
        "Kuryer Telegram ID sini yuboring.\n"
        "<i>ID ni bilish uchun kuryer @userinfobot ga /start yubormog'i lozim.</i>\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdminState.adding_courier_id)
async def add_courier_id(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    tg_id = message.text.strip()
    if not tg_id.lstrip("-").isdigit():
        await message.answer("❗ Faqat raqam kiriting. Qaytadan:")
        return
    await state.update_data(new_courier_id=tg_id)
    await state.set_state(AdminState.adding_courier_name)
    await message.answer("👤 Kuryer to'liq ismini kiriting:")


@router.message(AdminState.adding_courier_name)
async def add_courier_name(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    await state.update_data(new_courier_name=message.text.strip())
    await state.set_state(AdminState.adding_courier_phone)
    await message.answer("📞 Kuryer telefon raqamini kiriting (+998...):")


@router.message(AdminState.adding_courier_phone)
async def add_courier_phone(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    phone = message.text.strip()
    await state.update_data(new_courier_phone=phone)
    await state.set_state(AdminState.adding_courier_region)
    await message.answer(
        "📍 Kuryer ishlaydigan hududlarni kiriting:\n"
        "<i>Masalan: Toshkent shahar, Toshkent viloyati</i>"
    )


@router.message(AdminState.adding_courier_region)
async def add_courier_region(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    regions = message.text.strip()
    data = await state.get_data()
    tg_id = data["new_courier_id"]
    name = data["new_courier_name"]
    phone = data["new_courier_phone"]

    ok = await add_courier(tg_id, name, phone, regions)
    invalidate_courier_cache()
    if ok:
        await state.set_state(AdminState.managing_couriers)
        await message.answer(
            f"✅ <b>{name}</b> kuryerlar ro'yxatiga qo'shildi!\n\n"
            f"📞 {phone}\n📍 {regions}\n🆔 {tg_id}",
            reply_markup=admin_menu_keyboard(),
        )
        try:
            await message.bot.send_message(
                int(tg_id),
                "🎉 Siz kuryer sifatida ro'yxatdan o'tdingiz!\n"
                "Buyurtmalarni ko'rish uchun /courier buyrug'ini yuboring.",
            )
        except Exception:
            pass
    else:
        await message.answer(f"⚠️ Bu ID ({tg_id}) allaqachon ro'yxatda. Boshqa ID kiriting.")
        await state.set_state(AdminState.adding_courier_id)


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
    text = ai_analytics.format_stats()
    await callback.message.edit_text(text, reply_markup=analytics_menu_keyboard())
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
            f"🤖 <b>AI Insight</b>\n\n{insight}",
            reply_markup=analytics_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            f"🤖 <b>AI Insight</b>\n\n{insight}",
            reply_markup=analytics_menu_keyboard(),
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
            "⚠️ <i>Eslatma: bu doimiy bo'lishi uchun koordinatani "
            "tizimga (config) ham yozish kerak. Ushbu koordinatani adminga yuboring.</i>\n\n"
            "Endi shu nuqtadan belgilangan radius ichidagi buyurtmalar qabul qilinadi.",
            reply_markup=remove_keyboard(),
        )
        await message.answer("🔧 Admin panel:", reply_markup=admin_menu_keyboard())
    else:
        await message.answer(
            "⚠️ Saqlashda xatolik. Qayta urinib ko'ring.",
            reply_markup=remove_keyboard(),
        )


@router.callback_query(F.data == "adm_office_radius")
async def office_radius_prompt(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.setting_office_radius)
    o = settings_store.get_office()
    await callback.message.edit_text(
        f"📏 <b>Yetkazish radiusi</b>\n\n"
        f"Joriy: <b>{o['radius_km']:.0f} km</b>\n\n"
        "Yangi radiusni km da kiriting (faqat raqam).\n"
        "<i>Masalan: 12</i>\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdminState.setting_office_radius)
async def office_set_radius(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    raw = message.text.strip().replace(",", ".")
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
    user_ids = {o["user_id"] for o in orders if o["user_id"]}

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
