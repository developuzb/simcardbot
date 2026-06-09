from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import numbers_keyboard, tariffs_keyboard
from data import TARIFFS
from config import PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_TEXT
import analytics_store

router = Router()


@router.callback_query(OrderState.choosing_tariff, F.data.startswith("tariff_"))
async def choose_tariff(callback: CallbackQuery, state: FSMContext):
    tariff_id = callback.data.replace("tariff_", "")
    user_data = await state.get_data()
    op_id = user_data.get("operator_id")

    selected_tariff = None
    for t in TARIFFS.get(op_id, []):
        if t["id"] == tariff_id:
            selected_tariff = t
            break

    if not selected_tariff:
        await callback.answer("Xatolik! Qaytadan urinib ko'ring.", show_alert=True)
        return

    analytics_store.tariff_chosen(op_id, tariff_id)
    await state.update_data(
        tariff_id=tariff_id,
        tariff_name=selected_tariff["name"],
        tariff_price=selected_tariff["price"],
        tariff_desc=selected_tariff["desc"]
    )
    await state.set_state(OrderState.choosing_number)

    op_name = user_data.get("operator_name", "")
    op_emoji = user_data.get("operator_emoji", "")

    lines = [ln.strip() for ln in selected_tariff["desc"].split("•") if ln.strip()]
    desc_block = "<blockquote>" + "\n".join(lines) + "</blockquote>"

    promo_line = ""
    if selected_tariff["price"] >= PROMO_1PLUS1_MIN_PRICE:
        promo_line = f"\n{PROMO_1PLUS1_TEXT}\n"

    await callback.message.edit_text(
        f"✅ <b>{op_emoji} {op_name}</b> — <b>{selected_tariff['name']}</b> tanlandi\n"
        f"💰 <b>{selected_tariff['price']:,} so'm</b>/oy\n"
        f"{promo_line}\n"
        f"{desc_block}\n\n"
        f"📱 <b>Sim raqamni tanlang:</b>\n"
        f"Mavjud raqamlardan birini tanlang yoki tasodifiy raqam oling 👇",
        reply_markup=numbers_keyboard(op_id)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    op_id = user_data.get("operator_id")
    op_name = user_data.get("operator_name", "")
    op_emoji = user_data.get("operator_emoji", "")

    await state.set_state(OrderState.choosing_tariff)
    await callback.message.edit_text(
        f"{op_emoji} <b>{op_name}</b> tariflari:\n\n"
        "Kerakli tarifni tanlang 👇",
        reply_markup=tariffs_keyboard(op_id)
    )
    await callback.answer()
