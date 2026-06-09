from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import operators_keyboard, main_menu_keyboard, remove_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "📲 <b>Texnoset</b> — SIM karta yetkazib berish xizmatiga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan birini tanlang 👇",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "new_order")
async def start_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OrderState.choosing_operator)
    await callback.message.edit_text(
        "📡 <b>Operatorni tanlang:</b>\n\n"
        "Quyidagi 5 ta operatordan birini tanlang:",
        reply_markup=operators_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "contact")
async def show_contact(callback: CallbackQuery):
    await callback.message.edit_text(
        "📞 <b>Bog'lanish uchun:</b>\n\n"
        "👨‍💼 Operator: @admin_username\n"
        "📱 Tel: +998 90 123 45 67\n"
        "🕐 Ish vaqti: 09:00 - 22:00\n\n"
        "Yoki /start buyrug'i orqali qaytishingiz mumkin.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Bekor qilindi. Qayta boshlash uchun /start bosing.",
        reply_markup=remove_keyboard(),
    )


# Holatdan tashqari (restart yoki sessiya tugaganda) matn yozilsa —
# bot jim qolmasin, menyuni (AI tugmasi bilan) ko'rsatsin.
@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def fallback_no_state(message: Message):
    await message.answer(
        "👋 Davom etamizmi? Quyidagilardan birini tanlang 👇\n\n"
        "<i>SIM karta tanlash uchun «🤖 Mutaxassis yordamida tanlash» tugmasini bosing.</i>",
        reply_markup=main_menu_keyboard(),
    )
