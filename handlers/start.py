from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import (
    main_menu_keyboard, remove_keyboard, back_to_main_keyboard,
)
from data import OPERATORS, TARIFFS
from config import (
    ADMIN_CONTACT, ADMIN_PHONE, FOUNDER_CONTACT, OFFICE_ADDRESS, WORK_DAYS,
    DELIVERY_TYPES, PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_BADGE,
    WORK_START_HOUR, WORK_END_HOUR, REFERRAL_DISCOUNT,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import settings_store
import referrals_store
import web_bridge
from handlers import dispatch, ai_chat

router = Router()


# ─── BOSH SAHIFA ─────────────────────────────────────────────────

def _welcome_text(name: str) -> str:
    return (
        "✨ <b>TEXNOSET</b> ✨\n"
        "<i>SIM karta — eshigingizgacha yetkazib beramiz</i>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"Assalomu alaykum, <b>{name}</b>! 👋\n\n"
        "📡 Barcha operatorlar: Ucell, Beeline, Mobiuz, Humans, Uzmobile\n"
        "⚡ Bugun buyurtma — bugun yetkazamiz (atigi <b>1 soatda</b> ham)\n"
        "🎁 70 000+ tariflarga <b>1+1</b>: ikkinchi SIM <b>BEPUL</b>\n"
        "👥 Do'st taklifiga chegirma\n"
        "🤖 Suxrob (AI yordamchi) — eng mos tarifni topib beradi\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "✅ Rasmiy SIM · Pasport bilan rasmiylashtiriladi · To'lov topshirilganda (naqd/karta)\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Quyidan tanlang — yoki savolingizni shu yerga yozing, javob beraman 👇"
    )


_SUXROB_GREETING = (
    "💬 <b>Suxrob AI:</b> Assalomu alaykum! 👋\n"
    "Sizga qandaydir masalada yordam kerakmi? Shu yerga bemalol yozing — "
    "savolingizga javob beraman 😊"
)


# ─── SAVDOGA UNDOVCHI NUDGE XABARLARI (Suxrob AI, 2-xabar) ───────

def _nudge_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="🛒 Buyurtma berish", callback_data="new_order")
    b.button(text="🤖 AI yordamchi", callback_data="open_ai_chat")
    b.adjust(2)
    return b.as_markup()


_PROMO_NUDGE = (
    "💬 <b>Suxrob AI:</b> 1+1 va bepul yetkazish — bugun olsangiz ikki marta tejaysiz 😊\n"
    "Tayyor bo'lsangiz «🛒 Buyurtma berish»ni bosing. Ikkilanayotgan bo'lsangiz "
    "«🤖 AI yordamchi»ga yozing — eng foydali tarifni o'zim topib beraman 👇"
)
_TARIFFS_NUDGE = (
    "💬 <b>Suxrob AI:</b> Qaysi biri mosligini bilmasangiz, menga «arzonroq» yoki "
    "«internet ko'p» deb yozing — bir zumda eng mosini tanlab beraman 😊\n"
    "Yoki to'g'ridan «🛒 Buyurtma berish»ni bosing 👇"
)
_ABOUT_NUDGE = (
    "💬 <b>Suxrob AI:</b> Ishonch hosil qildingizmi? 😊 SIM qo'lingizga tekkanda to'laysiz, "
    "yoqmasa olishingiz shart emas — hech qanday xavf yo'q!\n"
    "«🛒 Buyurtma berish»ni bossangiz, bir necha daqiqada rasmiylashtiramiz 👇"
)


async def _send_home(message: Message, name: str):
    """Bosh sahifa: rasm (bo'lsa) + menyu, so'ng Suxrob AI salomi."""
    text = _welcome_text(name)
    photo_id = settings_store.get_welcome_photo()
    sent = False
    if photo_id:
        try:
            await message.answer_photo(photo_id, caption=text, reply_markup=main_menu_keyboard())
            sent = True
        except Exception:
            pass
    if not sent:
        await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext, command: CommandObject = None,
                    is_admin: bool = False):
    await state.clear()
    # Referal havola: /start ref<referrer_id>
    payload = (command.args if command else None) or ""
    if payload.startswith("ref"):
        rid = payload[3:].strip()
        if rid.isdigit() and referrals_store.register(message.from_user.id, rid):
            await message.answer(
                f"🎁 Xush kelibsiz! Do'stingiz tavsiyasi bilan keldingiz — "
                f"birinchi buyurtmangizga <b>{REFERRAL_DISCOUNT:,} so'm chegirma</b> qo'shildi!"
            )
    # Saytdan kelgan buyurtma: /start ord<token> -> buyurtma botda davom etadi
    if payload.startswith("ord"):
        token = payload[3:].strip()
        pdata = web_bridge.pop_pending(token) if token else None
        if pdata:
            pdata["user_id"] = message.from_user.id
            if not str(pdata.get("name", "")).strip():
                pdata["name"] = message.from_user.full_name
            try:
                num = await dispatch.place_web_order(message.bot, pdata)
                await message.answer(
                    f"✅ <b>Buyurtmangiz qabul qilindi!</b>  №<b>{num}</b>\n"
                    "Saytda tanlaganingiz bo'yicha rasmiylashtiramiz — operatorimiz "
                    "tez orada siz bilan bog'lanadi. 🚀"
                )
            except Exception:
                await message.answer(
                    "✅ Buyurtmangiz qabul qilindi! Operatorimiz tez orada bog'lanadi."
                )
            await _send_home(message, message.from_user.first_name or "mehmon")
            return
        await message.answer(
            "⏳ Buyurtma ma'lumotini topa olmadim (eskirgan bo'lishi mumkin). "
            "Quyidan 🛒 «Buyurtma berish»ni tanlab, shu yerda davom eting 👇"
        )
    # Suxrob (sun'iy intellekt) bilan suhbat: /start ai_yordamchi
    if payload == "ai_yordamchi":
        if not is_admin:
            try:
                await dispatch.ensure_lead_topic(message.bot, message.from_user)
            except Exception:
                pass
        await ai_chat.start_ai_chat(message, state)
        return
    # Mijoz keldi — buyurtmalar guruhida unга topic ochamiz (adminlar uchun emas).
    # Best-effort: asosiy oqimni hech qachon buzmaydi.
    if not is_admin:
        try:
            await dispatch.ensure_lead_topic(message.bot, message.from_user)
        except Exception:
            pass
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
        + "\n".join(delivery_lines) + "\n\n"
        "👥 <b>DO'STNI TAKLIF QILING</b>\n"
        f"Do'stingiz havolangiz orqali kelsa — birinchi buyurtmasiga {REFERRAL_DISCOUNT:,} so'm chegirma 🎁\n"
        "«👥 Do'st taklif qil» tugmasidan havolangizni oling.\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "⏱ Bugun buyurtma bersangiz — bugunoq yetkazamiz! Pastdan boshlang 👇"
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
        promo = f" 🎁 {PROMO_1PLUS1_MIN_PRICE:,}+ da 1+1" if max_price >= PROMO_1PLUS1_MIN_PRICE else ""
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
        "4️⃣ Raqamni oldindan operator bilan kelishasiz yoki <b>kuryer oldida</b> tanlaysiz 📱\n"
        "5️⃣ Pasport bilan rasmiylashtiriladi, to'lovni topshirilganda qilasiz 🪪\n\n"
        "💵 <b>To'lov:</b> SIM qo'lingizga tekkanda — naqd yoki karta\n"
        "🪪 <b>Pasport:</b> kuryer kelganda tayyor bo'lsin\n"
        "✅ Rasmiy SIM · Yoqmasa — olishingiz shart emas\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "Savol bo'lsa — «📞 Aloqa» orqali yozing."
    )
    await _show_section(callback, text, back_to_main_keyboard())


# ─── ALOQA ───────────────────────────────────────────────────────

def _contact_keyboard() -> object:
    b = InlineKeyboardBuilder()
    b.button(text="📍 Ofis lokatsiyasi", callback_data="show_office_loc")
    b.button(text="🤖 AI yordamchi", callback_data="open_ai_chat")
    b.button(text="⬅️ Bosh sahifa", callback_data="back_to_main")
    b.adjust(1, 2)
    return b.as_markup()


@router.callback_query(F.data == "contact")
async def show_contact(callback: CallbackQuery):
    text = (
        "📞 <b>BIZ BILAN BOG'LANISH</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"📱 Telefon: <code>{ADMIN_PHONE}</code>\n"
        f"💬 Telegram: {ADMIN_CONTACT}\n"
        f"👤 Asoschi: Suxrob — {FOUNDER_CONTACT}\n\n"
        f"🏢 <b>Manzil:</b> {OFFICE_ADDRESS}\n"
        f"🕐 <b>Ish vaqti:</b> {WORK_DAYS}, {WORK_START_HOUR:02d}:00 – {WORK_END_HOUR:02d}:00\n\n"
        "Ofis joylashuvini ko'rish uchun pastdagi tugmani bosing 👇"
    )
    await _show_section(callback, text, _contact_keyboard())


@router.callback_query(F.data == "show_office_loc")
async def show_office_location(callback: CallbackQuery):
    o = settings_store.get_office()
    try:
        await callback.message.answer_location(latitude=o["lat"], longitude=o["lon"])
    except Exception:
        pass
    await callback.message.answer(
        f"📍 <b>Texnoset ofisi</b>\n🏢 {OFFICE_ADDRESS}\n\n"
        f"📱 {ADMIN_PHONE} · {ADMIN_CONTACT}",
        reply_markup=back_to_main_keyboard(),
    )
    await callback.answer()


# ─── DO'ST TAKLIF QILISH (REFERAL) ───────────────────────────────

@router.callback_query(F.data == "show_referral")
async def show_referral(callback: CallbackQuery):
    uid = callback.from_user.id
    try:
        me = await callback.bot.me()
        link = f"https://t.me/{me.username}?start=ref{uid}"
    except Exception:
        link = ""
    invited = referrals_store.invited_count(uid)
    share = (
        "Salom! 😊 Texnoset orqali SIM kartani uyga yetkazib olish mumkin — "
        "operatorni tanlaysan, kuryer eshiginggacha olib keladi. "
        f"Mana havola: {link}"
    )
    text = (
        "👥 <b>DO'STNI TAKLIF QILING</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"Do'stingiz havolangiz orqali kelsa, uning birinchi buyurtmasiga "
        f"<b>{REFERRAL_DISCOUNT:,} so'm chegirma</b> tushadi 🎁\n\n"
        f"🔗 <b>Havolangiz:</b>\n<code>{link}</code>\n\n"
        f"👤 Siz taklif qilganlar: <b>{invited}</b> ta\n\n"
        "Quyidagi tayyor matnni do'stlaringizga yuboring 👇\n"
        f"<blockquote>{share}</blockquote>"
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

# Eslatma: holatdan tashqari erkin matnni endi ai_chat.home_assistant
# (Suxrob AI) javob beradi — kuryerlar guruhiga arala