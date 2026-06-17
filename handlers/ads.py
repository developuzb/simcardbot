"""Reklama (avto-post) moduli.

Admin reklama postini kiritadi → tasdiqlaydi → bot belgilangan vaqt(lar)da
ro'yxatga olingan guruh/kanallarga avtomatik yuboradi (navbat bilan).

Guruh qo'shish (2 usul):
  1. Buyurtma guruhining UMUMIY (General) qismiga reklama guruhidan istalgan
     postni FORWARD qiling → bot uni qo'shishni taklif qiladi.
  2. Reklama guruhida /reklama_guruh_qosh buyrug'ini yuboring.
Har ikkalasida ham bot o'sha guruh/kanalda ADMIN bo'lishi shart (post yuborish uchun).

Boshqaruv: /admin → 📣 Reklama.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import ads_store
import settings_store
from states import AdminState, AdsState
from keyboards import ads_menu_keyboard, admin_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ─── YUBORISH (scheduler + "Hozir yuborish") ─────────────────────

async def send_ads_round(bot) -> int:
    """Navbatdagi reklama postini barcha guruhlarga yuboradi.
    Yuborilgan guruhlar sonini qaytaradi."""
    groups = ads_store.get_groups()
    post = ads_store.next_rotation_post()
    if not groups or not post:
        return 0
    text = post.get("text") or ""
    photo = post.get("photo") or ""
    sent = 0
    for g in groups:
        try:
            if photo:
                await bot.send_photo(g["id"], photo, caption=(text or None))
            else:
                await bot.send_message(g["id"], text)
            sent += 1
        except Exception as e:
            logger.warning("Reklama yuborilmadi (guruh %s): %s", g.get("id"), e)
    logger.info("Reklama yuborildi: %s/%s guruh (post #%s)", sent, len(groups), post.get("id"))
    return sent


async def ads_loop(bot):
    """Har ~30 soniyada Toshkent vaqtini tekshiradi; belgilangan soatda
    reklamani yuboradi. Bir daqiqada bir martadan ko'p yuborilmaydi."""
    last_key = None
    while True:
        await asyncio.sleep(30)
        try:
            if not ads_store.is_enabled():
                continue
            times = ads_store.get_times()
            if not times:
                continue
            now_tk = datetime.now(timezone.utc) + timedelta(hours=5)  # Toshkent UTC+5
            hhmm = now_tk.strftime("%H:%M")
            if hhmm in times:
                key = now_tk.strftime("%Y-%m-%d ") + hhmm
                if key != last_key:
                    last_key = key
                    await send_ads_round(bot)
        except Exception as e:
            logger.error("ads_loop xatolik: %s", e)


# ─── ADMIN MENYU ─────────────────────────────────────────────────

async def _show_ads_menu(target):
    enabled = ads_store.is_enabled()
    groups = ads_store.get_groups()
    posts = ads_store.get_posts()
    times = ads_store.get_times()
    text = (
        "📣 <b>Reklama — avto-post</b>\n\n"
        f"Holat: {'🟢 Yoqilgan' if enabled else '🔴 Oʻchiq'}\n"
        f"👥 Guruhlar: <b>{len(groups)}</b>\n"
        f"🗂 Postlar: <b>{len(posts)}</b>\n"
        f"⏰ Vaqtlar: <b>{', '.join(times) if times else '—'}</b> (Toshkent)\n\n"
        "• Postni navbat bilan barcha guruhlarga belgilangan vaqtda yuboradi.\n"
        "• Guruh qoʻshish: reklama guruhida <code>/reklama_guruh_qosh</code> yoki "
        "buyurtma guruhining General qismiga oʻsha guruhdan post forward qiling."
    )
    kb = ads_menu_keyboard(enabled)
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm_ads")
async def adm_ads(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.main_menu)
    await _show_ads_menu(callback)


# ─── GURUH QO'SHISH: FORWARD (General'da) ────────────────────────

def _forward_source_chat(message: Message):
    o = getattr(message, "forward_origin", None)
    if o is not None:
        return getattr(o, "chat", None) or getattr(o, "sender_chat", None)
    return getattr(message, "forward_from_chat", None)  # eski API fallback


@router.message(F.forward_origin)
async def ads_forward_register(message: Message, is_admin: bool = False):
    """Buyurtma guruhining General qismiga guruh/kanaldan post forward qilinsa —
    uni reklama guruhi sifatida qo'shishni taklif qiladi."""
    if not is_admin:
        return
    gid = settings_store.get_orders_group()
    if not gid or message.chat.id != gid or message.message_thread_id:
        return  # faqat buyurtma guruhining General qismi
    chat = _forward_source_chat(message)
    if not chat or getattr(chat, "type", None) not in ("group", "supergroup", "channel"):
        return  # foydalanuvchidan forward bo'lsa — e'tiborsiz
    b = InlineKeyboardBuilder()
    b.button(text="✅ Reklama guruhi qil", callback_data=f"ads_grpadd_{chat.id}")
    b.button(text="✖️ Yoʻq", callback_data="ads_grpcancel")
    b.adjust(1)
    await message.reply(
        f"➕ <b>{(chat.title or chat.id)}</b> ni reklama roʻyxatiga qoʻshaymi?\n"
        f"🆔 <code>{chat.id}</code>\n\n"
        "⚠️ Bot shu guruh/kanalda <b>admin</b> boʻlishi shart (post yuborish uchun).",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data == "ads_grpcancel")
async def ads_grpcancel(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    try:
        await callback.message.edit_text("✖️ Bekor qilindi.")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ads_grpadd_"))
async def ads_grpadd(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    try:
        cid = int(callback.data[len("ads_grpadd_"):])
    except ValueError:
        return await callback.answer("Xato.", show_alert=True)
    title = str(cid)
    try:
        ch = await callback.bot.get_chat(cid)
        title = ch.title or str(cid)
    except Exception:
        pass
    added = ads_store.add_group(cid, title)
    await callback.answer("✅ Qoʻshildi" if added else "Allaqachon bor")
    try:
        await callback.message.edit_text(
            f"{'✅ Reklama guruhi qoʻshildi' if added else 'ℹ️ Allaqachon roʻyxatda'}: "
            f"<b>{title}</b>\n🆔 <code>{cid}</code>"
        )
    except Exception:
        pass


# ─── GURUH QO'SHISH: BUYRUQ (guruh ichida) ───────────────────────

@router.message(Command("reklama_guruh_qosh"))
async def ads_group_cmd(message: Message, is_admin: bool = False):
    if message.chat.type not in ("group", "supergroup", "channel"):
        return await message.answer("Bu buyruqni reklama GURUHIDA yuboring (botni admin qilib qoʻshib).")
    if not is_admin:
        return await message.answer("⛔ Faqat admin qoʻsha oladi.")
    added = ads_store.add_group(message.chat.id, message.chat.title or "")
    await message.answer(
        f"{'✅ Reklama guruhi ulandi!' if added else 'ℹ️ Bu guruh allaqachon roʻyxatda.'}\n"
        f"🆔 <code>{message.chat.id}</code>\n\n"
        "Bot shu yerda <b>admin</b> ekanini tekshiring. Postlarni /admin → 📣 Reklama dan qoʻshasiz."
    )


# ─── GURUHLAR RO'YXATI ───────────────────────────────────────────

@router.callback_query(F.data == "ads_groups")
async def ads_groups(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    groups = ads_store.get_groups()
    b = InlineKeyboardBuilder()
    for g in groups:
        b.button(text=f"🗑 {g['title'][:28]}", callback_data=f"ads_grpdel_{g['id']}")
    b.button(text="⬅️ Orqaga", callback_data="adm_ads")
    b.adjust(1)
    if groups:
        lines = "\n".join(f"• {g['title']} (<code>{g['id']}</code>)" for g in groups)
    else:
        lines = ("Hozircha guruh yoʻq.\n\nQoʻshish: reklama guruhida "
                 "<code>/reklama_guruh_qosh</code> yoki General'ga post forward qiling.")
    try:
        await callback.message.edit_text(f"👥 <b>Reklama guruhlari</b>\n\n{lines}",
                                          reply_markup=b.as_markup())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ads_grpdel_"))
async def ads_grpdel(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    try:
        cid = int(callback.data[len("ads_grpdel_"):])
    except ValueError:
        return await callback.answer("Xato.", show_alert=True)
    ads_store.remove_group(cid)
    await callback.answer("🗑 Oʻchirildi")
    await ads_groups(callback, is_admin=True)


# ─── POST QO'SHISH (tasdiq bilan) ────────────────────────────────

@router.callback_query(F.data == "ads_post_add")
async def ads_post_add(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdsState.adding_post)
    await callback.message.answer(
        "📝 <b>Reklama postini yuboring</b> — matn yoki rasm + matn (izoh).\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdsState.adding_post)
async def ads_post_receive(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    photo = message.photo[-1].file_id if message.photo else ""
    text = (message.caption or message.text or "").strip()
    if not text and not photo:
        return await message.answer("Boʻsh post. Matn yoki rasm yuboring.")
    await state.update_data(ads_pending_text=text, ads_pending_photo=photo)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data="ads_post_confirm")
    b.button(text="✖️ Bekor", callback_data="ads_post_discard")
    b.adjust(2)
    caption = "👀 <b>Post koʻrinishi:</b>\n\n" + (text or "<i>(matnsiz)</i>")
    if photo:
        await message.answer_photo(photo, caption=caption, reply_markup=b.as_markup())
    else:
        await message.answer(caption, reply_markup=b.as_markup())


@router.callback_query(F.data == "ads_post_confirm")
async def ads_post_confirm(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    data = await state.get_data()
    text = data.get("ads_pending_text", "")
    photo = data.get("ads_pending_photo", "")
    if not text and not photo:
        return await callback.answer("Post topilmadi, qaytadan yuboring.", show_alert=True)
    pid = ads_store.add_post(text, photo)
    await state.set_state(AdminState.main_menu)
    await state.update_data(ads_pending_text="", ads_pending_photo="")
    await callback.answer("✅ Tasdiqlandi va navbatga qoʻshildi.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"✅ <b>Reklama post #{pid}</b> qoʻshildi va navbatga tushdi.",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "ads_post_discard")
async def ads_post_discard(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdminState.main_menu)
    await state.update_data(ads_pending_text="", ads_pending_photo="")
    await callback.answer("Bekor qilindi.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ─── POSTLAR RO'YXATI ────────────────────────────────────────────

@router.callback_query(F.data == "ads_posts")
async def ads_posts(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    posts = ads_store.get_posts()
    b = InlineKeyboardBuilder()
    for p in posts:
        label = (p.get("text") or ("🖼 rasm" if p.get("photo") else "post")).replace("\n", " ")
        b.button(text=f"🗑 #{p['id']} {label[:24]}", callback_data=f"ads_postdel_{p['id']}")
    b.button(text="⬅️ Orqaga", callback_data="adm_ads")
    b.adjust(1)
    if posts:
        lines = []
        for p in posts:
            snippet = (p.get("text") or "").replace("\n", " ")
            tag = "🖼 " if p.get("photo") else ""
            lines.append(f"• #{p['id']} {tag}{snippet[:60] or '(matnsiz rasm)'}")
        body = "\n".join(lines)
    else:
        body = "Hozircha post yoʻq. «📝 Post qoʻshish» orqali qoʻshing."
    try:
        await callback.message.edit_text(
            f"🗂 <b>Reklama postlari</b> (navbat bilan yuboriladi)\n\n{body}",
            reply_markup=b.as_markup(),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ads_postdel_"))
async def ads_postdel(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    try:
        pid = int(callback.data[len("ads_postdel_"):])
    except ValueError:
        return await callback.answer("Xato.", show_alert=True)
    ads_store.remove_post(pid)
    await callback.answer("🗑 Oʻchirildi")
    await ads_posts(callback, is_admin=True)


# ─── VAQTLAR ─────────────────────────────────────────────────────

@router.callback_query(F.data == "ads_times")
async def ads_times(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    times = ads_store.get_times()
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Oʻzgartirish", callback_data="ads_times_edit")
    b.button(text="⬅️ Orqaga", callback_data="adm_ads")
    b.adjust(1)
    try:
        await callback.message.edit_text(
            "⏰ <b>Yuborish vaqtlari</b> (Toshkent)\n\n"
            f"Joriy: <b>{', '.join(times) if times else '—'}</b>\n\n"
            "Har kuni shu soatlarda reklama yuboriladi.",
            reply_markup=b.as_markup(),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "ads_times_edit")
async def ads_times_edit(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(AdsState.setting_times)
    await callback.message.answer(
        "⏰ Soatlarni vergul bilan kiriting (Toshkent vaqti).\n"
        "Masalan: <code>10:00, 15:00, 19:00</code>\n\n"
        "/admin — bekor qilish"
    )
    await callback.answer()


@router.message(AdsState.setting_times)
async def ads_times_set(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    times = []
    for part in (message.text or "").replace(" ", "").split(","):
        m = re.match(r"^(\d{1,2}):(\d{2})$", part)
        if not m:
            continue
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            times.append(f"{h:02d}:{mi:02d}")
    if not times:
        return await message.answer("❗ Format notoʻgʻri. Masalan: 10:00, 19:00")
    # takrorlarni olib tashlab, tartiblaymiz
    times = sorted(set(times))
    ads_store.set_times(times)
    await state.set_state(AdminState.main_menu)
    await message.answer(
        f"✅ Vaqtlar saqlandi: <b>{', '.join(times)}</b> (Toshkent)",
        reply_markup=admin_menu_keyboard(),
    )


# ─── YOQISH / O'CHIRISH ──────────────────────────────────────────

@router.callback_query(F.data == "ads_toggle")
async def ads_toggle(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    enabled = ads_store.is_enabled()
    if not enabled:
        if not ads_store.get_groups():
            return await callback.answer("Avval reklama guruhini qoʻshing.", show_alert=True)
        if not ads_store.get_posts():
            return await callback.answer("Avval reklama postini qoʻshing.", show_alert=True)
        if not ads_store.get_times():
            return await callback.answer("Avval yuborish vaqtini belgilang.", show_alert=True)
    ads_store.set_enabled(not enabled)
    await callback.answer("🟢 Yoqildi" if not enabled else "🔴 Oʻchirildi")
    await _show_ads_menu(callback)


# ─── HOZIR YUBORISH (test) ───────────────────────────────────────

@router.callback_query(F.data == "ads_send_now")
async def ads_send_now(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔", show_alert=True)
    if not ads_store.get_groups():
        return await callback.answer("Reklama guruhi yoʻq.", show_alert=True)
    if not ads_store.get_posts():
        return await callback.answer("Reklama posti yoʻq.", show_alert=True)
    n = await send_ads_round(callback.bot)
    await callback.answer(
        f"🚀 Yuborildi: {n} ta guruh" if n else "Yuborib boʻlmadi (botni guruhda admin qiling).",
        show_alert=True,
    )
