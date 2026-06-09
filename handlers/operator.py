from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import tariffs_keyboard, operators_keyboard
from data import OPERATORS, TARIFFS
import analytics_store

router = Router()


@router.callback_query(OrderState.choosing_operator, F.data.startswith("op_"))
async def choose_operator(callback: CallbackQuery, state: FSMContext):
    op_id = callback.data.replace("op_", "")
    operator = OPERATORS.get(op_id)
    if not operator:
        await callback.answer("Xatolik! Qaytadan urinib ko'ring.", show_alert=True)
        return

    analytics_store.operator_asked(op_id)
    await state.update_data(
        operator_id=op_id,
        operator_name=operator["name"],
        operator_emoji=operator["emoji"]
    )
    await state.set_state(OrderState.choosing_tariff)

    def tariff_block(t: dict) -> str:
        lines = [ln.strip() for ln in t["desc"].split("•") if ln.strip()]
        body = "\n".join(lines)
        return (
            f"📦 <b>{t['name']}</b> — <b>{t['price']:,} so'm</b>/oy\n"
            f"<blockquote>{body}</blockquote>"
        )

    tariff_list = "\n\n".join(tariff_block(t) for t in TARIFFS.get(op_id, []))

    await callback.message.edit_text(
        f"{operator['emoji']} <b>{operator['name']}</b> tariflari:\n\n"
        f"{tariff_list}\n\n"
        f"Kerakli tarifni tanlang 👇",
        reply_markup=tariffs_keyboard(op_id)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_operators")
async def back_to_operators(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.choosing_operator)
    await callback.message.edit_text(
        "📡 <b>Operatorni tanlang:</b>\n\n"
        "Quyidagi 5 ta operatordan birini tanlang:",
        reply_markup=operators_keyboard()
    )
    await callback.answer()
