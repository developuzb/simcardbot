import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import location_keyboard
from data import OPERATORS
import numbers_db

router = Router()


@router.callback_query(OrderState.choosing_number, F.data.startswith("num_"))
async def choose_number(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    op_id = user_data.get("operator_id")
    op_prefix = OPERATORS[op_id]["prefix"]

    num_data = callback.data.replace("num_", "")

    if num_data == "random":
        numbers = numbers_db.get_available(op_id)
        raw_number = random.choice(numbers) if numbers else "000-000-00-00"
    else:
        digits = num_data
        raw_number = f"{digits[:2]}-{digits[2:5]}-{digits[5:7]}-{digits[7:]}"

    full_number = f"{op_prefix[3:]}-{raw_number}"

    await state.update_data(sim_number=full_number)
    await state.set_state(OrderState.entering_name)

    await callback.message.edit_text(
        f"✅ <b>Raqam tanlandi:</b> <code>{full_number}</code>\n\n"
        f"👤 Iltimos, to'liq ismingizni yozing:\n"
        f"<i>(Yetkazib berish uchun kerak)</i>"
    )
    await callback.answer()


@router.message(OrderState.entering_name)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❗ Iltimos, to'liq ismingizni kiriting (kamida 3 harf).")
        return

    await state.update_data(name=name)
    await state.set_state(OrderState.entering_phone)
    await message.answer(
        f"✅ <b>{name}</b>\n\n"
        f"📞 Bog'lanish uchun telefon raqamingizni kiriting:\n"
        f"<i>Namuna: +998901234567</i>"
    )


@router.message(OrderState.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not (phone.startswith("+998") and len(phone) == 13 and phone[1:].isdigit()):
        await message.answer(
            "❗ Noto'g'ri format. Iltimos, quyidagi formatda kiriting:\n"
            "<code>+998901234567</code>"
        )
        return

    await state.update_data(contact_phone=phone)
    await state.set_state(OrderState.sharing_location)
    await message.answer(
        f"✅ <b>{phone}</b>\n\n"
        f"📍 <b>Lokatsiyangizni yuboring</b>\n\n"
        f"Yetkazib berish hududini aniqlab, narxni hisoblaymiz.\n"
        f"Quyidagi tugmani bosing 👇",
        reply_markup=location_keyboard()
    )
