"""Buyurtma dispetcherligi.

Mijoz buyurtma beradi → admin tasdiqlaydi → yopiq kuryerlar guruhiga
e'lon (telefonsiz, faqat lokatsiya) → guruh a'zosi kuryer «Qabul
qilish»ni bosadi → to'liq ma'lumot + status tugmalari kuryer DM'iga
boradi → statuslar botda belgilanadi → bajarilganda mijozga xabar +
ixtiyoriy 1-5 yulduz baho.

Xavfsizlik: har callback'da buyurtmaning noyob `token`'i tekshiriladi
(eski/forward qilingan tugma boshqa buyurtmaga ta'sir qilmaydi);
«Qabul qilish» faqat kuryerlar guruhi a'zolariga ruxsat.
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import orders_db
import settings_store
import lead_topics_store
from config import ADMIN_IDS, ADMIN_CONTACT
from data import operator_number_hint

logger = logging.getLogger(__name__)
router = Router()

_STATUS_ICONS = {
    "Yangi": "🆕", "Tasdiqlangan": "📢", "Kuryerda": "🚴", "Yo'lda": "🚗",
    "Yetkazildi": "✅", "Mijoz yo'q": "🚫", "Bekor": "❌", "Hudud tashqarisida": "🟠",
}


# ─── KARTOCHKA VA KLAVIATURALAR ─────────────────────────────────

def order_card(o: dict, title: str = "", public: bool = False) -> str:
    """Buyurtma kartochkasi. public=True — guruh uchun, telefon YO'Q."""
    icon = _STATUS_ICONS.get(o["status"], "📦")
    promo_line = "🎁 <b>1+1 AKSIYA — 2 ta SIM olib boring!</b>\n" if o.get("promo") else ""
    courier_line = f"🚴 <b>Kuryer:</b> {o['courier_name']}\n" if o.get("courier_name") else ""
    phone_line = "" if public else f"📞 <b>Tel:</b> <code>{o['phone']}</code>\n"
    head = title or f"{icon} <b>BUYURTMA #{o['num']}</b>"
    return (
        f"{head}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 <b>Mijoz:</b> {o['name']}\n"
        f"{phone_line}"
        f"📡 <b>Tarif:</b> {o['operator']} — {o['tariff']} ({o['tariff_price']:,} so'm/oy)\n"
        f"{promo_line}"
        f"🚀 <b>Yetkazish:</b> {o['delivery_type']} — {o['delivery_price']:,} so'm\n"
        f"📍 <b>Hudud:</b> {o['region']}\n"
        f"💰 <b>Jami:</b> {o['total']:,} so'm\n"
        f"{courier_line}"
        f"🔖 <b>Holat:</b> {o['status']}"
    )


def _cb(prefix: str, o: dict) -> str:
    return f"{prefix}{o['num']}_{o.get('token', '')}"


def kb_admin_confirm(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=_cb("disp_ok_", o))
    b.button(text="❌ Bekor qilish", callback_data=_cb("disp_rej_", o))
    b.adjust(2)
    return b.as_markup()


def kb_claim(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚴 Qabul qilish", callback_data=_cb("disp_claim_", o))
    b.adjust(1)
    return b.as_markup()


def kb_claimed(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚗 Yo'lga chiqdim", callback_data=_cb("disp_onway_", o))
    b.button(text="✅ Bajardim", callback_data=_cb("disp_done_", o))
    b.button(text="🚫 Mijoz yo'q", callback_data=_cb("disp_noshow_", o))
    b.button(text="↩️ Voz kechish", callback_data=_cb("disp_drop_", o))
    b.adjust(1, 1, 2)
    return b.as_markup()


def kb_onway(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Bajardim", callback_data=_cb("disp_done_", o))
    b.button(text="🚫 Mijoz yo'q", callback_data=_cb("disp_noshow_", o))
    b.adjust(2)
    return b.as_markup()


def kb_customer_cancel(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Buyurtmani bekor qilish", callback_data=_cb("cust_cancel_", o))
    b.adjust(1)
    return b.as_markup()


def kb_rating(o) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text=f"{i}⭐", callback_data=f"rate_{o['num']}_{o.get('token', '')}_{i}")
    b.adjust(5)
    return b.as_markup()


async def _notify_customer(bot, order: dict, text: str, reply_markup=None) -> bool:
    if not order.get("user_id"):
        return False
    try:
        await bot.send_message(int(order["user_id"]), text, reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.warning("Mijozga (#%s, %s) xabar yuborilmadi: %s",
                       order.get("num"), order.get("user_id"), e)
        return False


async def _notify_admins(bot, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, e)


async def _update_group_card(bot, order: dict, title: str = "", kb=None):
    gid = settings_store.get_courier_group()
    mid = order.get("group_msg_id")
    if not gid or not mid:
        return
    try:
        await bot.edit_message_text(
            order_card(order, title, public=True),
            chat_id=gid, message_id=mid, reply_markup=kb,
        )
    except Exception:
        pass


# ─── BUYURTMALAR GURUHI (FORUM TOPIC) ───────────────────────────
# Har buyurtma alohida forum guruhda o'z topic'ida ochiladi (kuryer
# guruhidan TASHQARI, qo'shimcha). Topic ichida TO'LIQ kartochka
# (telefon bilan) va holatga mos admin status tugmalari turadi.

def kb_topic(o: dict) -> InlineKeyboardMarkup | None:
    """Topic ichidagi tugmalar. FAQAT 'Yangi' holatda admin uchun
    Tasdiqlash/Bekor. Admin tasdiqlagandan keyin topic'da tugma chiqmaydi
    (yetkazish kuryer guruhida boshqariladi) — topic faqat kuzatuv/yozuv."""
    if o.get("status") == "Yangi":
        return kb_admin_confirm(o)  # disp_ok_ / disp_rej_ (mavjud handlerlar)
    return None


async def _update_topic_card(bot, order: dict, title: str = ""):
    """Buyurtmalar guruhidagi topic kartochkasini holatga mos yangilaydi."""
    gid = settings_store.get_orders_group()
    mid = order.get("topic_msg_id")
    if not gid or not mid:
        return
    try:
        await bot.edit_message_text(
            order_card(order, title),  # to'liq (telefon bilan)
            chat_id=gid, message_id=mid, reply_markup=kb_topic(order),
        )
    except Exception:
        pass


async def post_to_orders_group(bot, text: str, user_id=None, reply_markup=None) -> bool:
    """Buyurtmalar guruhiga xabar yuboradi.
    user_id berilsa — o'sha mijozning topic'iga; bo'lmasa yoki topic yo'q
    bo'lsa — guruhning UMUMIY (General) qismiga. Guruh ulanmagan yoki
    yuborib bo'lmasa — False (chaqiruvchi admin DM'ga qaytishi mumkin)."""
    gid = settings_store.get_orders_group()
    if not gid:
        return False
    thread_id = lead_topics_store.get_topic(user_id) if user_id else None
    try:
        await bot.send_message(gid, text, message_thread_id=thread_id, reply_markup=reply_markup)
        return True
    except Exception as e:
        # Topic eskirgan/o'chgan bo'lishi mumkin — General'ga urinib ko'ramiz
        if thread_id is not None:
            try:
                await bot.send_message(gid, text, reply_markup=reply_markup)
                return True
            except Exception:
                pass
        logger.warning("Buyurtmalar guruhiga yuborilmadi: %s", e)
        return False


async def ensure_lead_topic(bot, user) -> int | None:
    """Mijoz /start bosganda unга forum topic ochadi (BITTA mijozga bitta).
    Mavjud bo'lsa qayta ochmaydi. Guruh ulanmagan/forum bo'lmasa — None."""
    gid = settings_store.get_orders_group()
    if not gid:
        return None
    existing = lead_topics_store.get_topic(user.id)
    if existing:
        return existing
    uname = f" @{user.username}" if getattr(user, "username", None) else ""
    name = f"👤 {user.full_name}{uname}".strip() or f"👤 {user.id}"
    try:
        topic = await bot.create_forum_topic(chat_id=gid, name=name[:128])
        thread_id = topic.message_thread_id
        await bot.send_message(
            gid,
            f"🆕 <b>Yangi mijoz keldi</b>\n"
            f"👤 {user.full_name}\n"
            f"🔗 {('@' + user.username) if getattr(user, 'username', None) else 'username yo`q'}\n"
            f"🆔 <code>{user.id}</code>\n\n"
            "<i>Hali buyurtma bermagan. Buyurtma bersa — shu topic ichida ko'rinadi.</i>",
            message_thread_id=thread_id,
        )
        lead_topics_store.set_topic(user.id, thread_id)
        logger.info("Lead topic ochildi user=%s thread=%s", user.id, thread_id)
        return thread_id
    except Exception as e:
        logger.warning("Lead topic ochilmadi (user %s): %s — guruh forum bo'lib, "
                       "bot 'Manage Topics' huquqiga ega ekanini tekshiring.", user.id, e)
        return None


async def open_order_topic(bot, order: dict) -> bool:
    """Buyurtma kartochkasini (Tasdiqlash/Bekor tugmalari bilan) buyurtmalar
    GURUHIga joylaydi. Mijozning lead topic'i bo'lsa — o'shanda; bo'lmasa
    yangi topic ochadi; topic ochib bo'lmasa (Manage Topics yo'q) — guruhning
    UMUMIY (General) qismiga tushiradi. Guruh ulanmagan bo'lsa — False.
    Muvaffaqiyatli joylasa True qaytaradi (admin DM'ni o'tkazib yuborish uchun)."""
    gid = settings_store.get_orders_group()
    if not gid:
        return False
    num = order["num"]
    uid = order.get("user_id")
    thread_id = lead_topics_store.get_topic(uid) if uid else None

    # Topic ochishga harakat (bo'lmasa General'ga tushamiz — fallback)
    if not thread_id:
        name = f"#{num} · {order.get('name', '—')} · {order.get('operator', '')} {order.get('tariff', '')}".strip()
        try:
            topic = await bot.create_forum_topic(chat_id=gid, name=name[:128])
            thread_id = topic.message_thread_id
            if uid:
                lead_topics_store.set_topic(uid, thread_id)
        except Exception as e:
            logger.warning("Topic ochilmadi (#%s): %s — guruh UMUMIY qismiga tushiramiz "
                           "(doimiy topic uchun botga 'Manage Topics' huquqini bering).", num, e)
            thread_id = None  # General'ga

    try:
        msg = await bot.send_message(
            gid,
            order_card(order, f"🛒 <b>BUYURTMA BERDI — #{num}</b>"),
            message_thread_id=thread_id,   # None => umumiy (General)
            reply_markup=kb_topic(order),
        )
        await orders_db.update_order(num, {"topic_id": thread_id, "topic_msg_id": msg.message_id})
        order["topic_id"] = thread_id
        order["topic_msg_id"] = msg.message_id
        if order.get("lat") and order.get("lon"):
            try:
                await bot.send_location(gid, latitude=order["lat"], longitude=order["lon"],
                                        message_thread_id=thread_id)
            except Exception:
                pass
        logger.info("Buyurtma guruhga joylandi #%s (thread=%s)", num, thread_id)
        return True
    except Exception as e:
        logger.warning("Buyurtma guruhga joylanmadi (#%s): %s", num, e)
        return False


# ─── BUYURTMALAR GURUHINI ULASH ──────────────────────────────────

@router.message(Command("setordersgroup"))
async def set_orders_group_cmd(message: Message, is_admin: bool = False):
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("Bu buyruqni buyurtmalar GURUHIDA yuboring (botni guruhga qo'shib).")
    if not is_admin:
        return await message.answer("⛔ Faqat admin guruhni ulashi mumkin.")
    if not getattr(message.chat, "is_forum", False):
        return await message.answer(
            "⚠️ Bu guruhda <b>Mavzular (Topics)</b> yoqilmagan.\n"
            "Guruh sozlamalari → <b>Topics</b> ni yoqing, so'ng qayta /setordersgroup yuboring."
        )
    settings_store.set_orders_group(message.chat.id)
    logger.info("BUYURTMALAR_GURUHI_SET chat_id=%s", message.chat.id)
    await message.answer(
        "✅ <b>Buyurtmalar guruhi ulandi!</b>\n"
        f"Guruh ID: <code>{message.chat.id}</code>\n\n"
        "Endi har yangi buyurtma shu guruhda alohida <b>topic</b>da ochiladi — "
        "to'liq ma'lumot va status tugmalari bilan.\n\n"
        "⚠️ <b>Muhim:</b> bot guruhda admin bo'lib, <b>Manage Topics</b> (mavzularni "
        "boshqarish) huquqiga ega bo'lishi shart.\n"
        "⚠️ <i>Doimiy bo'lishi uchun bu ID ni ORDERS_GROUP_ID env'ga yozing.</i>"
    )


async def _verify(callback: CallbackQuery, prefix: str):
    """callback_data 'prefix{num}_{token}' dan buyurtmani topadi va
    token mosligini tekshiradi. Eskirgan tugma → None."""
    raw = callback.data[len(prefix):]
    parts = raw.rsplit("_", 1)
    if len(parts) != 2:
        await callback.answer("Tugma eskirgan.", show_alert=True)
        return None
    num, token = parts
    order = await orders_db.get_order_by_num(num)
    if not order:
        await callback.answer("⚠️ Buyurtma topilmadi (eskirgan).", show_alert=True)
        return None
    if str(order.get("token", "")) != token:
        await callback.answer(
            "⚠️ Bu tugma eski buyurtmaga tegishli (bot yangilangan). Yangi buyurtma bering.",
            show_alert=True,
        )
        return None
    return order


# ─── GURUHNI ULASH ───────────────────────────────────────────────

@router.message(Command("setgroup"))
async def set_group(message: Message, is_admin: bool = False):
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("Bu buyruqni kuryerlar GURUHIDA yuboring (botni guruhga qo'shib).")
    if not is_admin:
        return await message.answer("⛔ Faqat admin guruhni ulashi mumkin.")
    settings_store.set_courier_group(message.chat.id)
    logger.info("KURYER_GURUHI_SET chat_id=%s", message.chat.id)
    await message.answer(
        "✅ <b>Kuryerlar guruhi ulandi!</b>\n"
        f"Guruh ID: <code>{message.chat.id}</code>\n\n"
        "Endi admin tasdiqlagan buyurtmalar shu yerga tushadi.\n\n"
        "⚠️ <b>Muhim:</b> har bir kuryer buyurtma olishdan oldin botni shaxsiy "
        "chatda bir marta <b>/start</b> qilishi shart — aks holda buyurtma "
        "tafsilotlari unga yetib bormaydi.\n\n"
        "⚠️ <i>Doimiy bo'lishi uchun bu ID ni COURIER_GROUP_ID env'ga yozing.</i>"
    )


# ─── ADMIN: TASDIQLASH / BEKOR ──────────────────────────────────

@router.callback_query(F.data.startswith("disp_ok_"))
async def admin_confirm(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    order = await _verify(callback, "disp_ok_")
    if not order:
        return
    num = order["num"]

    gid = settings_store.get_courier_group()
    if not gid:
        return await callback.answer(
            "⚠️ Kuryerlar guruhi ulanmagan! Botni guruhga qo'shib /setgroup yuboring.",
            show_alert=True,
        )

    if not await orders_db.update_order_if(num, "Yangi", {"status": "Tasdiqlangan"}):
        return await callback.answer(f"Allaqachon ko'rib chiqilgan ({order['status']}).", show_alert=True)
    order["status"] = "Tasdiqlangan"

    # Guruhga e'lon — TELEFONSIZ
    try:
        gmsg = await callback.bot.send_message(gid, order_card(order, public=True), reply_markup=kb_claim(order))
        await orders_db.update_order(num, {"group_msg_id": gmsg.message_id})
        order["group_msg_id"] = gmsg.message_id
    except Exception as e:
        logger.error("Guruhga yuborish xatolik (#%s): %s", num, e)
        await orders_db.update_order_if(num, "Tasdiqlangan", {"status": "Yangi"})
        return await callback.answer("⚠️ Guruhga yuborib bo'lmadi. Bot guruhda ekanini tekshiring.", show_alert=True)

    # Lokatsiya pin — alohida (best-effort, asosiy oqimni buzmaydi)
    if order.get("lat") and order.get("lon"):
        try:
            await callback.bot.send_location(
                gid, latitude=order["lat"], longitude=order["lon"],
                reply_to_message_id=order["group_msg_id"],
            )
        except Exception:
            pass

    await callback.answer("✅ Tasdiqlandi, guruhga yuborildi!")
    try:
        await callback.message.edit_text(order_card(order, f"✅ <b>#{num} TASDIQLANDI</b> — guruhga yuborildi"))
    except Exception:
        pass

    # Mijozga: operator/kuryer bog'lanadi + raqam formati
    hint = operator_number_hint(order.get("op_id", ""))
    hint_line = f"\n📱 Raqamingiz <b>{hint}</b> ko'rinishida bo'ladi." if hint else ""
    await _notify_customer(
        callback.bot, order,
        f"✅ <b>Buyurtmangiz #{num} qabul qilindi!</b>\n\n"
        "🤝 Operatorimiz tez orada siz bilan bog'lanib, <b>SIM raqamni tanlash</b> "
        "va <b>yetkazib berish vaqtini</b> kelishib oladi."
        f"{hint_line}",
        reply_markup=kb_customer_cancel(order),
    )
    await _update_topic_card(callback.bot, order, f"📢 <b>#{num} TASDIQLANDI</b>")


@router.callback_query(F.data.startswith("disp_rej_"))
async def admin_reject(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    order = await _verify(callback, "disp_rej_")
    if not order:
        return
    num = order["num"]
    if not await orders_db.update_order_if(num, "Yangi", {"status": "Bekor"}):
        return await callback.answer(f"Allaqachon ko'rib chiqilgan ({order['status']}).", show_alert=True)
    order["status"] = "Bekor"
    await callback.answer("❌ Bekor qilindi.")
    try:
        await callback.message.edit_text(order_card(order, f"❌ <b>#{num} BEKOR QILINDI</b> (admin)"))
    except Exception:
        pass
    await _notify_customer(
        callback.bot, order,
        f"😔 Afsuski, buyurtmangiz #{num} bekor qilindi.\nSavollar uchun: {ADMIN_CONTACT}",
    )
    await _update_topic_card(callback.bot, order, f"❌ <b>#{num} BEKOR QILINDI</b> (admin)")


# ─── KURYER: QABUL QILISH (guruhda) ─────────────────────────────

@router.callback_query(F.data.startswith("disp_claim_"))
async def courier_claim(callback: CallbackQuery):
    order = await _verify(callback, "disp_claim_")
    if not order:
        return
    num = order["num"]

    # Avtorizatsiya — faqat kuryerlar guruhi a'zosi
    gid = settings_store.get_courier_group()
    if gid:
        try:
            member = await callback.bot.get_chat_member(gid, callback.from_user.id)
            if member.status in ("left", "kicked"):
                return await callback.answer("⛔ Siz kuryerlar guruhi a'zosi emassiz.", show_alert=True)
        except Exception:
            pass  # tekshiruv imkonsiz bo'lsa — guruh tugmasi baribir a'zolarga ko'rinadi

    courier = callback.from_user
    courier_name = courier.full_name
    if not await orders_db.update_order_if(num, "Tasdiqlangan", {
        "status": "Kuryerda", "courier_id": str(courier.id), "courier_name": courier_name,
    }):
        return await callback.answer("⚠️ Bu buyurtma allaqachon band!", show_alert=True)
    order.update(status="Kuryerda", courier_id=str(courier.id), courier_name=courier_name)

    # To'liq ma'lumot (telefon bilan) + status tugmalari — SHAXSIY CHATDA
    try:
        await callback.bot.send_message(
            courier.id,
            order_card(order, f"🚴 <b>SIZNING BUYURTMANGIZ #{num}</b>") +
            "\n\n📞 Mijoz bilan bog'lanib, SIM raqam va yetkazib berishni kelishing.\n"
            "Holatni quyidagi tugmalar bilan belgilab boring 👇",
            reply_markup=kb_claimed(order),
        )
        if order.get("lat") and order.get("lon"):
            await callback.bot.send_location(courier.id, latitude=order["lat"], longitude=order["lon"])
    except Exception:
        # DM yopiq — band qilishni qaytaramiz
        await orders_db.update_order_if(num, "Kuryerda", {
            "status": "Tasdiqlangan", "courier_id": "", "courier_name": "",
        })
        me = await callback.bot.get_me()
        return await callback.answer(
            f"⚠️ Avval botga kirib /start bosing (@{me.username}), keyin qayta urinib ko'ring.",
            show_alert=True,
        )

    await callback.answer(f"🚴 Buyurtma #{num} sizniki! Botga qarang.")
    try:
        await callback.message.edit_text(order_card(order, public=True))
    except Exception:
        pass
    await _notify_customer(
        callback.bot, order,
        f"🚴 Buyurtmangiz #{num} uchun kuryer biriktirildi: <b>{courier_name}</b>\n"
        "Tez orada siz bilan bog'lanadi!",
    )
    await _update_topic_card(callback.bot, order, f"🚴 <b>#{num} — KURYER OLDI:</b> {courier_name}")


# ─── KURYER: STATUSLAR ──────────────────────────────────────────

def _is_claimer(callback: CallbackQuery, order: dict) -> bool:
    return str(callback.from_user.id) == str(order.get("courier_id"))


@router.callback_query(F.data.startswith("disp_onway_"))
async def courier_onway(callback: CallbackQuery):
    order = await _verify(callback, "disp_onway_")
    if not order:
        return
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    num = order["num"]
    if not await orders_db.update_order_if(num, "Kuryerda", {"status": "Yo'lda"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Yo'lda"

    await callback.answer("🚗 Yo'lda!")
    try:
        await callback.message.edit_text(order_card(order, f"🚗 <b>BUYURTMA #{num} — YO'LDA</b>"),
                                         reply_markup=kb_onway(order))
    except Exception:
        pass
    await _update_group_card(callback.bot, order)
    await _notify_customer(
        callback.bot, order,
        f"🚗 <b>Kuryer yo'lga chiqdi!</b> Buyurtma #{num}\n🚴 {order['courier_name']}\n\n"
        "Tez orada eshigingizda bo'ladi 🙌",
    )
    await _update_topic_card(callback.bot, order, f"🚗 <b>#{num} — YO'LDA</b>")


@router.callback_query(F.data.startswith("disp_done_"))
async def courier_done(callback: CallbackQuery):
    order = await _verify(callback, "disp_done_")
    if not order:
        return
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Kuryerda", "Yo'lda"), {"status": "Yetkazildi"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Yetkazildi"

    await callback.answer("🎉 Ajoyib ish!")
    try:
        await callback.message.edit_text(order_card(order, f"✅ <b>BUYURTMA #{num} — YETKAZILDI</b>"))
    except Exception:
        pass
    await _update_group_card(callback.bot, order, f"✅ <b>#{num} YETKAZILDI</b> — {order['courier_name']}")
    await _notify_customer(
        callback.bot, order,
        f"🎉 <b>Buyurtmangiz #{num} yetkazib berildi!</b>\n\nXaridingiz uchun rahmat! 🙏\n\n"
        "⭐ Xizmat sifatini baholang (ixtiyoriy):",
        reply_markup=kb_rating(order),
    )
    await _notify_admins(callback.bot, f"✅ #{num} yetkazildi — 🚴 {order['courier_name']}")
    await _update_topic_card(callback.bot, order, f"✅ <b>#{num} YETKAZILDI</b> — {order['courier_name']}")


@router.callback_query(F.data.startswith("disp_noshow_"))
async def courier_noshow(callback: CallbackQuery):
    order = await _verify(callback, "disp_noshow_")
    if not order:
        return
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Kuryerda", "Yo'lda"), {"status": "Mijoz yo'q"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Mijoz yo'q"

    await callback.answer("Qayd etildi.")
    try:
        await callback.message.edit_text(order_card(order, f"🚫 <b>BUYURTMA #{num} — MIJOZ TOPILMADI</b>"))
    except Exception:
        pass
    await _update_group_card(callback.bot, order, f"🚫 <b>#{num} — MIJOZ TOPILMADI</b>")
    await _notify_customer(
        callback.bot, order,
        f"😕 Kuryer sizga yetib bora olmadi (buyurtma #{num}).\n"
        f"Qayta faollashtirish uchun bog'laning: {ADMIN_CONTACT}",
    )
    await _notify_admins(
        callback.bot,
        f"🚫 #{num} — mijoz topilmadi (🚴 {order['courier_name']}).\n"
        f"📞 Mijoz: <code>{order['phone']}</code>",
    )
    await _update_topic_card(callback.bot, order, f"🚫 <b>#{num} — MIJOZ TOPILMADI</b>")


@router.callback_query(F.data.startswith("disp_drop_"))
async def courier_drop(callback: CallbackQuery):
    order = await _verify(callback, "disp_drop_")
    if not order:
        return
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Kuryerda", "Yo'lda"), {
        "status": "Tasdiqlangan", "courier_id": "", "courier_name": "",
    }):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order.update(status="Tasdiqlangan", courier_id="", courier_name="")

    await callback.answer("↩️ Buyurtmadan voz kechdingiz.")
    try:
        await callback.message.edit_text(order_card(order, f"↩️ <b>#{num} — VOZ KECHDINGIZ</b>"))
    except Exception:
        pass
    # Guruhda qayta ochamiz — boshqa kuryer olishi mumkin
    await _update_group_card(
        callback.bot, order, f"🔁 <b>#{num} QAYTA OCHILDI</b> — kuryer kutilmoqda", kb=kb_claim(order),
    )
    await _update_topic_card(callback.bot, order, f"🔁 <b>#{num} QAYTA OCHILDI</b> — kuryer kutilmoqda")


# ─── MIJOZ: O'Z BUYURTMASINI BEKOR QILISH ───────────────────────

@router.callback_query(F.data.startswith("cust_cancel_"))
async def customer_cancel(callback: CallbackQuery):
    order = await _verify(callback, "cust_cancel_")
    if not order:
        return
    if str(callback.from_user.id) != str(order.get("user_id")):
        return await callback.answer("⛔", show_alert=True)
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Yangi", "Tasdiqlangan"), {"status": "Bekor"}):
        return await callback.answer(
            "Buyurtmani bekor qilib bo'lmaydi — kuryer allaqachon ish boshlagan. "
            f"Iltimos bog'laning: {ADMIN_CONTACT}",
            show_alert=True,
        )
    order["status"] = "Bekor"
    await callback.answer("Buyurtma bekor qilindi.")
    try:
        await callback.message.edit_text(f"❌ Buyurtmangiz #{num} bekor qilindi.\n\nYana kerak bo'lsa /start bosing.")
    except Exception:
        pass
    # Guruhdagi e'lonni yopamiz (agar bo'lsa)
    await _update_group_card(callback.bot, order, f"❌ <b>#{num} — MIJOZ BEKOR QILDI</b>")
    await _update_topic_card(callback.bot, order, f"❌ <b>#{num} — MIJOZ BEKOR QILDI</b>")
    await _notify_admins(callback.bot, f"❌ #{num} — mijoz o'zi bekor qildi.")


# ─── MIJOZ: BAHO ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate_"))
async def customer_rate(callback: CallbackQuery):
    parts = callback.data[len("rate_"):].rsplit("_", 2)
    if len(parts) != 3:
        return await callback.answer()
    num, token, score_s = parts
    try:
        score = int(score_s)
    except ValueError:
        return await callback.answer()

    order = await orders_db.get_order_by_num(num)
    if not order or str(order.get("token", "")) != token:
        return await callback.answer("Eskirgan.", show_alert=True)
    if str(callback.from_user.id) != str(order.get("user_id")):
        return await callback.answer("⛔", show_alert=True)

    if not await orders_db.rate_order(num, score):
        return await callback.answer("Siz allaqachon baholagansiz. Rahmat! 😊", show_alert=True)

    await callback.answer("Rahmat! 🙏")
    try:
        await callback.message.edit_text(
            f"🎉 <b>Buyurtmangiz #{num} yetkazib berildi!</b>\n\n"
            f"Bahoyingiz: {'⭐' * score}\nFikringiz uchun rahmat! Yana murojaat eting 😊"
        )
    except Exception:
        pass

    await _update_topic_card(callback.bot, order, f"⭐ <b>#{num}</b> — mijoz bahosi: {'⭐' * score}")
    if score <= 3:
        await _notify_admins(
            callback.bot,
            f"⚠️ <b>Past baho:</b> #{num} — {'⭐' * score} ({score}/5)\n"
            f"🚴 Kuryer: {order.get('courier_name', '—')}\n"
            f"👤 Mijoz: {order.get('name', '—')} — <code>{order.get('phone', '—')}</code>",
        )


# ─── TOPIC: ADMIN STATUS BOSHQARUVI ─────────────────────────────
# Buyurtmalar guruhidagi topic ichidan admin holatni boshqaradi
# (kuryer guruhi oqimidan mustaqil — kuryersiz ham yetkazishni
# belgilash mumkin). Mijozga xabar + kuryer guruhi kartochkasi sinxron.

@router.callback_query(F.data.startswith("tdone_"))
async def topic_done(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    order = await _verify(callback, "tdone_")
    if not order:
        return
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Tasdiqlangan", "Kuryerda", "Yo'lda"), {"status": "Yetkazildi"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Yetkazildi"
    await callback.answer("✅ Yetkazildi deb belgilandi.")
    await _update_topic_card(callback.bot, order, f"✅ <b>#{num} YETKAZILDI</b>")
    await _update_group_card(callback.bot, order, f"✅ <b>#{num} YETKAZILDI</b>")
    await _notify_customer(
        callback.bot, order,
        f"🎉 <b>Buyurtmangiz #{num} yetkazib berildi!</b>\n\nXaridingiz uchun rahmat! 🙏\n\n"
        "⭐ Xizmat sifatini baholang (ixtiyoriy):",
        reply_markup=kb_rating(order),
    )


@router.callback_query(F.data.startswith("tnoshow_"))
async def topic_noshow(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    order = await _verify(callback, "tnoshow_")
    if not order:
        return
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Tasdiqlangan", "Kuryerda", "Yo'lda"), {"status": "Mijoz yo'q"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Mijoz yo'q"
    await callback.answer("🚫 Qayd etildi.")
    await _update_topic_card(callback.bot, order, f"🚫 <b>#{num} — MIJOZ TOPILMADI</b>")
    await _update_group_card(callback.bot, order, f"🚫 <b>#{num} — MIJOZ TOPILMADI</b>")
    await _notify_customer(
        callback.bot, order,
        f"😕 Kuryer sizga yetib bora olmadi (buyurtma #{num}).\n"
        f"Qayta faollashtirish uchun bog'laning: {ADMIN_CONTACT}",
    )


@router.callback_query(F.data.startswith("tcancel_"))
async def topic_cancel(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    order = await _verify(callback, "tcancel_")
    if not order:
        return
    num = order["num"]
    if not await orders_db.update_order_if(num, ("Yangi", "Tasdiqlangan", "Kuryerda", "Yo'lda"), {"status": "Bekor"}):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)
    order["status"] = "Bekor"
    await callback.answer("❌ Bekor qilindi.")
    await _update_topic_card(callback.bot, order, f"❌ <b>#{num} BEKOR QILINDI</b> (admin)")
    await _update_group_card(callback.bot, order, f"❌ <b>#{num} BEKOR QILINDI</b> (admin)")
    await _notify_customer(
        callback.bot, order,
        f"😔 Afsuski, buyurtmangiz #{num} bekor qilindi.\nSavollar uchun: {ADMIN_CONTACT}",
    )


# ─── TOPIC: ARXIV (General) + /sleep + /stop ────────────────────

def full_order_detail(o: dict) -> str:
    """Buyurtma haqida TO'LIQ tafsilot — General'ga arxivlash uchun."""
    maps = f"\n🗺 https://maps.google.com/?q={o['lat']},{o['lon']}" if o.get("lat") and o.get("lon") else ""
    courier = f"\n🚴 Kuryer: {o['courier_name']}" if o.get("courier_name") else ""
    rating = f"\n⭐ Baho: {'⭐' * int(o['rating'])}" if o.get("rating") else ""
    note = f"\n📝 Izoh: {o['note']}" if o.get("note") else ""
    return (
        f"🗂 <b>BUYURTMA ARXIVI — #{o.get('num')}</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"🕐 {o.get('date', '')} {o.get('time', '')}\n"
        f"👤 {o.get('name', '—')}\n"
        f"📞 <code>{o.get('phone', '—')}</code>\n"
        f"🆔 TG: {o.get('user_id', '—')}\n"
        f"📡 {o.get('operator', '')} — {o.get('tariff', '')} ({int(o.get('tariff_price', 0)):,} so'm/oy)\n"
        f"🚀 {o.get('delivery_type', '—')} — {int(o.get('delivery_price', 0)):,} so'm\n"
        f"📍 {o.get('region', '—')}{maps}\n"
        f"💳 Jami: {int(o.get('total', 0)):,} so'm{courier}{rating}{note}\n"
        f"🔖 Holat: {o.get('status', '—')}"
    )


async def _archive_topic_to_general(bot, gid: int, thread_id: int) -> int:
    """Topic'dagi buyurtma(lar)ning to'liq tafsilotini General'ga yuboradi.
    Arxivlangan buyurtmalar sonini qaytaradi."""
    orders = await orders_db.get_orders_by_topic(thread_id)
    for o in orders:
        try:
            await bot.send_message(gid, full_order_detail(o))  # thread_id yo'q => General
        except Exception as e:
            logger.warning("Arxiv General'ga yuborilmadi (#%s): %s", o.get("num"), e)
    return len(orders)


def _topic_cmd_ok(message: Message, is_admin: bool):
    """Buyruq buyurtmalar guruhi topic'i ichida, admin tomonidan ekanini tekshiradi.
    OK bo'lsa (gid, thread_id) qaytaradi, aks holda (None, sabab-matn)."""
    if not is_admin:
        return None, None  # jim
    gid = settings_store.get_orders_group()
    if not gid or message.chat.id != gid:
        return None, None  # boshqa joy — jim
    thread = message.message_thread_id
    if not thread:
        return None, "Bu buyruq buyurtma <b>topic</b>'i ichida ishlaydi (General'da emas)."
    return (gid, thread), ""


@router.message(Command("sleep"))
async def topic_sleep(message: Message, is_admin: bool = False):
    res, err = _topic_cmd_ok(message, is_admin)
    if res is None:
        if err:
            await message.reply(err)
        return
    gid, thread = res
    n = await _archive_topic_to_general(message.bot, gid, thread)
    await message.reply(
        f"😴 <b>Topic 1 soatdan keyin o'chiriladi.</b>\n"
        f"To'liq tafsilot General'ga saqlandi ({n} ta buyurtma)."
    )
    asyncio.create_task(_delete_topic_later(message.bot, gid, thread, 3600))


async def _delete_topic_later(bot, gid: int, thread_id: int, delay: float):
    await asyncio.sleep(delay)
    # O'chirishdan oldin shu topic mijozining xaritasini tozalaymiz (qayta /start yangi topic ochsin)
    try:
        for o in await orders_db.get_orders_by_topic(thread_id):
            if o.get("user_id"):
                lead_topics_store.clear_topic(o["user_id"])
    except Exception:
        pass
    try:
        await bot.delete_forum_topic(chat_id=gid, message_thread_id=thread_id)
        logger.info("Topic o'chirildi (thread=%s)", thread_id)
    except Exception as e:
        logger.warning("Topic o'chirilmadi (thread=%s): %s — bot 'Manage Topics' "
                       "huquqiga ega ekanini tekshiring.", thread_id, e)


@router.message(Command("stop"))
async def topic_stop(message: Message, is_admin: bool = False):
    res, err = _topic_cmd_ok(message, is_admin)
    if res is None:
        if err:
            await message.reply(err)
        return
    gid, thread = res
    n = await _archive_topic_to_general(message.bot, gid, thread)
    # General'ga qisqa yozuv (topic o'chgach reply yo'qoladi — bu saqlanib qoladi)
    try:
        await message.bot.send_message(gid, f"🗑 <b>Topic o'chirildi (/stop)</b> — {n} ta buyurtma arxivlandi (yuqorida).")
    except Exception:
        pass
    # Mijoz xaritasini tozalaymiz (qaytib kelsa yangi topic ochilsin)
    try:
        for o in await orders_db.get_orders_by_topic(thread):
            if o.get("user_id"):
                lead_topics_store.clear_topic(o["user_id"])
    except Exception:
        pass
    try:
        await message.bot.delete_forum_topic(chat_id=gid, message_thread_id=thread)
        logger.info("Topic /stop bilan o'chirildi (thread=%s)", thread)
    except Exception as e:
        # O'chirib bo'lmasa topic hali turibdi — reply ishlaydi
        await message.reply(f"⚠️ Topic o'chirilmadi: {e}\nBot 'Manage Topics' huquqiga ega ekanini tekshiring.")
