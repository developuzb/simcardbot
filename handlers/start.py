from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import (
    main_menu_keyboard, remove_keyboard, back_to_main_keyboard,
)
from data import OPERATORS, TARIFFS
from config import (
    ADMIN_CONTACT, DELIVERY_TYPES, PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_BADGE,
)
import settings_store

router = Router()


# ─── BOSH SAHIFA ─────────────────────────────────────────────────

def _welcome_text(name: str) -> str:
    return (
        "✨ <b>TEXNOSET</b> ✨\n"
        "<i>SIM karta — eshigingizgacha yetkazib beramiz</i>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"Assalomu alaykum, <b>{name}</b>! 👋\n\n"
        "📡 Barcha operatorlar: Ucell, Beeline, Mobiuz, Humans, Uzmobile\n"
        "⚡ Tezkor yetkazish — atigi <b>1 soatda</b>\n"
        "🎁 70 000+ tariflarga <b>1+1</b>: ikkinchi SIM <b>BEPUL</b>\n"
        "🤖 Suxrob — shaxsiy maslahatchingiz har doim yoningizda\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Boshlash uchun quyidan tanlang 👇"
    )


async def _send_home(message: Message, name: str):
    """Bosh sahifa: rasm o'rnatilgan bo'lsa — rasm + matn, aks holda matn."""
    text = _welcome_text(name)
    photo_id = settings_store.get_welcome_photo()
    if photo_id:
        try:
            await message.answer_photo(
                photo_id, caption=text, reply_markup=main_menu_keyboard(),
            )
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await _send_home(message, message.from_user.first_name or "mehmon")


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_home(callback.message, callback.from_user.first_name or "mehmon")
    await callback.answer()


async def _show_section(callback: CallbackQuery, text: str, kb):
    """Bo'limni ochadi — rasm-xabardan ham (edit ishlamasa, yangi xabar)."""
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# ─── BUYURTMA ────────────────────────────────────────────────────
# «🛒 Tezkor buyurtma» (new_order) endi AI oqimi orqali ishlaydi —
# handlers/ai_chat.py dagi open_quick_order. Eski qo'lda oqim olib tashlandi.


# ─── AKSIYALAR ───────────────────────────────────────────────────

@router.callback_query(F.data == "show_promo")
async def show_promo(callback: CallbackQuery):
    delivery_lines = []
    for dt in DELIVERY_TYPES.values():
        price = "<b>BEPUL</b> 🎁" if dt["price"] == 0 else f"{dt['price']:,} so'm"
        delivery_lines.append(f"{dt['emoji']} {dt['name']} — {dt['desc']} — {price}")
    text = (
        "🎁 <b>AKSIYALAR</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"🔥 <b>1+1 — IKKINCHI SIM BEPUL!</b>\n"
        f"{PROMO_1PLUS1_MIN_PRICE:,} so'm va undan qimmat har qanday tarifga "
        "ikkinchi SIM kartani sovg'a qilamiz 🎉\n\n"
        "🚀 <b>YETKAZIB BERISH</b>\n"
        + "\n".join(delivery_lines) + "\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Aksiyali tarifni tanlash uchun pastdan boshlang 👇"
    )
    await _show_section(callback, text, back_to_main_keyboard())


# ─── TARIFLAR (umumiy) ───────────────────────────────────────────

@router.callback_query(F.data == "show_tariffs")
async def show_tariffs(callback: CallbackQuery):
    lines = ["📋 <b>TARIFLAR</b>", "➖➖➖➖➖➖➖➖➖➖", "Barcha operatorlar mavjud:\n"]
    for op_id, op in OPERATORS.items():
        tariffs = TARIFFS.get(op_id, [])
        if not tariffs:
            continue
        min_price = min(t["price"] for t in tariffs)
        max_price = max(t["price"] for t in tariffs)
        promo = f" {PROMO_1PLUS1_BADGE}" if max_price >= PROMO_1PLUS1_MIN_PRICE else ""
        lines.append(f"{op['emoji']} <b>{op['name']}</b> — {min_price:,} so'mdan{promo}")
    lines.append(
        "\n🤖 <b>Aniq tarif tanlash uchun «AI yordamchi»dan foydalaning</b> — "
        "u savollaringizga javob berib, eng mosini topib beradi!"
    )
    await _show_section(callback, "\n".join(lines), back_to_main_keyboard())


# ─── BIZ HAQIMIZDA ───────────────────────────────────────────────

@router.callback_query(F.data == "show_about")
async def show_about(callback: CallbackQuery):
    text = (
        "ℹ️ <b>BIZ HAQIMIZDA</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "📲 <b>Texnoset</b> — SIM kartani uyingizgacha yetkazib beruvchi xizmat.\n\n"
        "Qanday ishlaydi:\n"
        "1️⃣ Operator va tarifni tanlaysiz (yoki AI yordam beradi)\n"
        "2️⃣ Telefon va joylashuvni yuborasiz\n"
        "3️⃣ Kuryer SIM kartalar bilan yetib keladi\n"
        "4️⃣ Yoqqan raqamni <b>kuryer oldida</b> tanlaysiz 📱\n\n"
        "✅ Ishonchli, tez va qulay!\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Savol bo'lsa — «📞 Aloqa» orqali yozing."
    )
    await _show_section(callback, text, back_to_main_keyboard())


# ─── ALOQA ───────────────────────────────────────────────────────

@router.callback_query(F.data == "contact")
async def show_contact(callback: CallbackQuery):
    text = (
        "📞 <b>BIZ BILAN BOG'LANISH</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"👨‍💼 Admin: {ADMIN_CONTACT}\n"
        "🕐 Ish vaqti: 09:00 – 22:00 (dushanba–shanba)\n\n"
        "Savol, taklif yoki muammo bo'lsa — bemalol yozing, "
        "tez orada javob beramiz! 🤝"
    )
    await _show_section(callback, text, back_to_main_keyboard())


# ─── BEKOR QILISH ────────────────────────────────────────────────

@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Bekor qilindi. Qayta boshlash uchun /start bosing.",
        reply_markup=remove_keyboard(),
    )


# Holatdan tashqari (restart yoki sessiya tugaganda) matn yozilsa —
# bot jim qolmasin, bosh sahifani ko'rsatsin. Faqat shaxsiy chatda —
# kuryerlar guruhidagi suhbatlarga aralashmaydi.
@router.message(StateFilter(None), F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def fallback_no_state(message: Message):
    await _send_home(message, message.from_user.first_name or "mehmon")
