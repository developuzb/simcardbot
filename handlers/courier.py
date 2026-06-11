from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import CourierState
from keyboards import (
    courier_menu_keyboard, courier_order_list_keyboard,
    courier_order_actions_keyboard,
)
from sheets_handler import update_courier_completed
from orders_db import get_orders_by_courier, get_order_by_num, update_order
from config import ADMIN_IDS
from utils import format_price
import numbers_db

router = Router()

_OP_NAME_MAP = {
    "ucell": "ucell", "uсell": "ucell",
    "beeline": "beeline",
    "mobiuz": "ums", "ums": "ums", "mobi.uz": "ums",
    "humans": "humans",
    "uzmobile": "uzmobile",
}


def _operator_name_to_id(name: str) -> str | None:
    return _OP_NAME_MAP.get(name.lower().strip().split()[0] if name else "", None)


@router.message(Command("courier"))
async def cmd_courier(message: Message, state: FSMContext, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        await message.answer("⛔ Siz kuryer sifatida ro'yxatdan o'tmagansiz.")
        return
    await state.set_state(CourierState.main_menu)
    await message.answer(
        f"🚴 Salom, <b>{courier_info['name']}</b>!\n\n"
        f"📍 Hududlar: {courier_info.get('regions', '—')}\n"
        f"✔️ Bajarilgan: {courier_info.get('completed', 0)} ta buyurtma\n\n"
        "Quyidan tanlang:",
        reply_markup=courier_menu_keyboard(),
    )


@router.callback_query(F.data == "cur_menu")
async def courier_main_menu(callback: CallbackQuery, state: FSMContext, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(CourierState.main_menu)
    await callback.message.edit_text(
        f"🚴 <b>{courier_info['name']}</b> — Asosiy menyu",
        reply_markup=courier_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cur_profile")
async def courier_profile(callback: CallbackQuery, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    orders = await get_orders_by_courier(courier_info["telegram_id"])
    active = [o for o in orders if o["status"] in ("Tayinlandi", "Yo'lda")]
    text = (
        f"👤 <b>Profilim</b>\n\n"
        f"🚴 Ism: <b>{courier_info['name']}</b>\n"
        f"📞 Tel: {courier_info['phone']}\n"
        f"📍 Hududlar: {courier_info.get('regions', '—')}\n"
        f"🟢 Holat: {courier_info.get('status', '—')}\n"
        f"🔄 Hozir faol buyurtmalar: <b>{len(active)}</b>\n"
        f"✔️ Jami bajarilgan: <b>{courier_info.get('completed', 0)}</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="cur_menu")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "cur_my_orders")
async def show_my_orders(callback: CallbackQuery, state: FSMContext, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(CourierState.viewing_my_orders)

    courier_id = courier_info["telegram_id"]
    orders = await get_orders_by_courier(courier_id)
    active = [o for o in orders if o["status"] in ("Tayinlandi", "Yo'lda")]

    if not active:
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Orqaga", callback_data="cur_menu")
        await callback.message.edit_text(
            "📋 Hozircha tayinlangan buyurtma yo'q.\n\nAdmin siz uchun buyurtma tayinlaganda xabar olasiz.",
            reply_markup=kb.as_markup(),
        )
        return await callback.answer()

    await callback.message.edit_text(
        f"📋 <b>Mening buyurtmalarim</b> ({len(active)} ta faol):\n\nBatafsil ko'rish uchun tanlang:",
        reply_markup=courier_order_list_keyboard(active),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cur_ord_"))
async def show_courier_order_detail(callback: CallbackQuery, state: FSMContext, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("cur_ord_", "")
    order = await get_order_by_num(order_num)

    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)
    if str(order["courier_id"]) != str(courier_info["telegram_id"]):
        return await callback.answer("Bu buyurtma sizga tegishli emas.", show_alert=True)

    text = (
        f"📦 <b>Buyurtma #{order['num']}</b>\n\n"
        f"👤 <b>Mijoz:</b> {order['name']}\n"
        f"📞 <b>Tel:</b> <code>{order['phone']}</code>\n\n"
        f"📍 <b>Hudud:</b> {order['region']}\n"
        f"📡 <b>Operator:</b> {order['operator']}\n"
        f"📱 <b>Sim raqami:</b> <code>{order['sim']}</code>\n"
        f"📦 <b>Tarif:</b> {order['tariff']}\n\n"
        f"💳 <b>Yetkazib berish narxi:</b> {format_price(int(order['delivery_price'] or 0))}\n\n"
        f"🔖 <b>Status:</b> {order['status']}"
    )
    await state.update_data(current_order_num=order_num)
    await callback.message.edit_text(
        text,
        reply_markup=courier_order_actions_keyboard(order_num, order["status"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cur_onway_"))
async def mark_on_way(callback: CallbackQuery, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("cur_onway_", "")
    order = await get_order_by_num(order_num)

    if not order or str(order["courier_id"]) != str(courier_info["telegram_id"]):
        return await callback.answer("Ruxsat yo'q.", show_alert=True)

    ok = await update_order(order_num, {"status": "Yo'lda"})
    if ok:
        await callback.answer("🚗 Status yangilandi: Yo'lda!")
        if order["user_id"]:
            try:
                # Operator ID ni aniqlaymiz (operator nomi orqali)
                op_id = _operator_name_to_id(order.get("operator", ""))
                available = numbers_db.get_available(op_id) if op_id else []

                if available:
                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    b = InlineKeyboardBuilder()
                    for num in available:
                        b.button(
                            text=f"📱 {num}",
                            callback_data=f"pick_num_{order_num}_{op_id}_{num.replace('-', '')}",
                        )
                    b.adjust(2)
                    await callback.bot.send_message(
                        int(order["user_id"]),
                        f"🚗 Kuryer yo'lda! Buyurtma #{order_num}\n"
                        f"Kuryer: <b>{courier_info['name']}</b> — 📞 {courier_info['phone']}\n\n"
                        f"📱 <b>SIM raqamingizni tanlang:</b>",
                        reply_markup=b.as_markup(),
                    )
                else:
                    await callback.bot.send_message(
                        int(order["user_id"]),
                        f"🚗 Buyurtmangiz #{order_num} yo'lda!\n"
                        f"Kuryer: <b>{courier_info['name']}</b>\n"
                        f"📞 {courier_info['phone']}",
                    )
            except Exception:
                pass
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Yetkazib berdim", callback_data=f"cur_done_{order_num}")
        kb.button(text="⬅️ Buyurtmalarga", callback_data="cur_my_orders")
        kb.adjust(1)
        await callback.message.edit_text(
            f"🚗 #{order_num} — <b>Yo'lda</b>\n\n"
            f"👤 {order['name']}\n"
            f"📞 {order['phone']}\n"
            f"📍 {order['region']}",
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("cur_done_"))
async def mark_delivered(callback: CallbackQuery, is_courier: bool = False, courier_info: dict = None):
    if not is_courier:
        return await callback.answer("⛔", show_alert=True)
    order_num = callback.data.replace("cur_done_", "")
    order = await get_order_by_num(order_num)

    if not order or str(order["courier_id"]) != str(courier_info["telegram_id"]):
        return await callback.answer("Ruxsat yo'q.", show_alert=True)

    ok = await update_order(order_num, {"status": "Yetkazildi"})
    if ok:
        await update_courier_completed(courier_info["telegram_id"])
        await callback.answer("✅ Ajoyib! Yetkazib berildi.")
        if order["user_id"]:
            try:
                await callback.bot.send_message(
                    int(order["user_id"]),
                    f"🎉 Buyurtmangiz #{order_num} yetkazildi!\n"
                    f"Xarid uchun rahmat! Yana murojaat eting 😊",
                )
            except Exception:
                pass
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"✔️ Buyurtma #{order_num} yetkazildi.\n"
                    f"Kuryer: {courier_info['name']}",
                )
            except Exception:
                pass

        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Buyurtmalarim", callback_data="cur_my_orders")
        kb.button(text="🏠 Menyu", callback_data="cur_menu")
        kb.adjust(1)
        await callback.message.edit_text(
            f"✅ <b>#{order_num} yetkazildi!</b>\n\n"
            f"Jami bajarilgan: <b>{int(courier_info.get('completed', 0)) + 1}</b> ta",
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer("Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("pick_num_"))
async def customer_pick_number(callback: CallbackQuery):
    """Mijoz kuryer yo'lda paytida SIM raqamini tanlaydi."""
    parts = callback.data.replace("pick_num_", "").split("_", 2)
    if len(parts) < 3:
        return await callback.answer("Xatolik.", show_alert=True)

    order_num, op_id, digits = parts
    raw = f"{digits[:2]}-{digits[2:5]}-{digits[5:7]}-{digits[7:]}"

    ok = await update_order(order_num, {"sim": raw})
    if ok:
        numbers_db.mark_sold(op_id, raw)
        await callback.message.edit_text(
            f"✅ Raqamingiz band qilindi: <code>{raw}</code>\n\n"
            f"Kuryer yetib kelganda shu raqamni aktivlashtiradi 🎉"
        )
        order = await get_order_by_num(order_num)
        if order and order.get("courier_id"):
            try:
                await callback.bot.send_message(
                    int(order["courier_id"]),
                    f"✅ Mijoz #{order_num} raqam tanladi: <code>{raw}</code>",
                )
            except Exception:
                pass
    else:
        await callback.answer("Saqlashda xatolik.", show_alert=True)
