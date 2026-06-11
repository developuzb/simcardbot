"""Buyurtma dispetcherligi:

Mijoz buyurtma beradi → admin tasdiqlaydi → yopiq kuryerlar guruhiga
e'lon → bo'sh kuryer «Qabul qilish»ni bosadi → statuslarni belgilab
boradi (Yo'lga chiqdim / Bajardim / Mijoz yo'q / Voz kechish) →
bajarilganda mijozga xabar + ixtiyoriy 1-5 yulduz baho.
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import orders_db
import numbers_db
import settings_store
from config import ADMIN_IDS, ADMIN_CONTACT

logger = logging.getLogger(__name__)
router = Router()

_STATUS_ICONS = {
    "Yangi": "🆕", "Tasdiqlangan": "📢", "Kuryerda": "🚴",
    "Yo'lda": "🚗", "Yetkazildi": "✅", "Mijoz yo'q": "🚫", "Bekor": "❌",
}


# ─── KARTOCHKA VA KLAVIATURALAR ─────────────────────────────────

def order_card(o: dict, title: str = "") -> str:
    icon = _STATUS_ICONS.get(o["status"], "📦")
    promo_line = "🎁 <b>1+1 AKSIYA — 2 ta SIM olib boring!</b>\n" if o.get("promo") else ""
    courier_line = ""
    if o.get("courier_name"):
        courier_line = f"🚴 <b>Kuryer:</b> {o['courier_name']}\n"
    head = title or f"{icon} <b>BUYURTMA #{o['num']}</b>"
    return (
        f"{head}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 <b>Mijoz:</b> {o['name']}\n"
        f"📞 <b>Tel:</b> <code>{o['phone']}</code>\n"
        f"📡 <b>Tarif:</b> {o['operator']} — {o['tariff']} ({o['tariff_price']:,} so'm/oy)\n"
        f"{promo_line}"
        f"🚀 <b>Yetkazish:</b> {o['delivery_type']} — {o['delivery_price']:,} so'm\n"
        f"📍 <b>Hudud:</b> {o['region']}\n"
        f"💰 <b>Jami:</b> {o['total']:,} so'm\n"
        f"{courier_line}"
        f"🔖 <b>Holat:</b> {o['status']}"
    )


def kb_admin_confirm(num) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"disp_ok_{num}")
    b.button(text="❌ Bekor qilish", callback_data=f"disp_rej_{num}")
    b.adjust(2)
    return b.as_markup()


def kb_claim(num) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚴 Qabul qilish", callback_data=f"disp_claim_{num}")
    b.adjust(1)
    return b.as_markup()


def kb_claimed(num) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚗 Yo'lga chiqdim", callback_data=f"disp_onway_{num}")
    b.button(text="✅ Bajardim", callback_data=f"disp_done_{num}")
    b.button(text="🚫 Mijoz yo'q", callback_data=f"disp_noshow_{num}")
    b.button(text="↩️ Voz kechish", callback_data=f"disp_drop_{num}")
    b.adjust(1, 1, 2)
    return b.as_markup()


def kb_onway(num) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Bajardim", callback_data=f"disp_done_{num}")
    b.button(text="🚫 Mijoz yo'q", callback_data=f"disp_noshow_{num}")
    b.adjust(2)
    return b.as_markup()


def kb_rating(num) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text=f"{i}⭐", callback_data=f"rate_{num}_{i}")
    b.adjust(5)
    return b.as_markup()


async def _notify_customer(bot, order: dict, text: str, reply_markup=None) -> bool:
    if not order.get("user_id"):
        return False
    try:
        await bot.send_message(int(order["user_id"]), text, reply_markup=reply_markup)
        return True
    except Exception:
        return False


# ─── GURUHNI ULASH ───────────────────────────────────────────────

@router.message(Command("setgroup"))
async def set_group(message: Message, is_admin: bool = False):
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer(
            "Bu buyruqni kuryerlar GURUHIDA yuboring (botni guruhga qo'shib)."
        )
    if not is_admin:
        return await message.answer("⛔ Faqat admin guruhni ulashi mumkin.")
    settings_store.set_courier_group(message.chat.id)
    logger.info("KURYER_GURUHI_SET chat_id=%s", message.chat.id)
    await message.answer(
        "✅ <b>Kuryerlar guruhi ulandi!</b>\n"
        f"Guruh ID: <code>{message.chat.id}</code>\n\n"
        "Endi admin tasdiqlagan buyurtmalar shu guruhga tushadi."
    )


# ─── ADMIN: TASDIQLASH / BEKOR ──────────────────────────────────

@router.callback_query(F.data.startswith("disp_ok_"))
async def admin_confirm(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    num = callback.data.replace("disp_ok_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)
    if order["status"] != "Yangi":
        return await callback.answer(f"Allaqachon ko'rib chiqilgan ({order['status']}).", show_alert=True)

    gid = settings_store.get_courier_group()
    if not gid:
        return await callback.answer(
            "⚠️ Kuryerlar guruhi ulanmagan!\n"
            "Botni guruhga qo'shib, guruhda /setgroup yuboring.",
            show_alert=True,
        )

    await orders_db.update_order(num, {"status": "Tasdiqlangan"})
    order["status"] = "Tasdiqlangan"

    # Guruhga e'lon
    try:
        gmsg = await callback.bot.send_message(
            gid, order_card(order), reply_markup=kb_claim(num),
        )
        if order.get("lat") and order.get("lon"):
            await callback.bot.send_location(
                gid, latitude=order["lat"], longitude=order["lon"],
                reply_to_message_id=gmsg.message_id,
            )
    except Exception as e:
        logger.error(f"Guruhga yuborish xatolik: {e}")
        await orders_db.update_order(num, {"status": "Yangi"})
        return await callback.answer(
            "⚠️ Guruhga yuborib bo'lmadi. Bot guruhda ekanini tekshiring.",
            show_alert=True,
        )

    await callback.answer("✅ Tasdiqlandi, guruhga yuborildi!")
    try:
        await callback.message.edit_text(
            order_card(order, f"✅ <b>#{num} TASDIQLANDI</b> — guruhga yuborildi"),
        )
    except Exception:
        pass
    await _notify_customer(
        callback.bot, order,
        f"✅ Buyurtmangiz #{num} tasdiqlandi!\n"
        "🚴 Kuryer izlanmoqda — tez orada yo'lga chiqadi.",
    )


@router.callback_query(F.data.startswith("disp_rej_"))
async def admin_reject(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        return await callback.answer("⛔ Faqat admin.", show_alert=True)
    num = callback.data.replace("disp_rej_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)
    if order["status"] != "Yangi":
        return await callback.answer(f"Allaqachon ko'rib chiqilgan ({order['status']}).", show_alert=True)

    await orders_db.update_order(num, {"status": "Bekor"})
    order["status"] = "Bekor"
    await callback.answer("❌ Bekor qilindi.")
    try:
        await callback.message.edit_text(
            order_card(order, f"❌ <b>#{num} BEKOR QILINDI</b> (admin)"),
        )
    except Exception:
        pass
    await _notify_customer(
        callback.bot, order,
        f"😔 Afsuski, buyurtmangiz #{num} bekor qilindi.\n"
        f"Savollar uchun: {ADMIN_CONTACT}",
    )


# ─── KURYER: QABUL QILISH ───────────────────────────────────────

@router.callback_query(F.data.startswith("disp_claim_"))
async def courier_claim(callback: CallbackQuery):
    num = callback.data.replace("disp_claim_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)
    if order["status"] != "Tasdiqlangan":
        return await callback.answer("⚠️ Bu buyurtma allaqachon band!", show_alert=True)

    courier = callback.from_user
    courier_name = courier.full_name
    await orders_db.update_order(num, {
        "status": "Kuryerda",
        "courier_id": str(courier.id),
        "courier_name": courier_name,
    })
    order.update(status="Kuryerda", courier_id=str(courier.id), courier_name=courier_name)

    await callback.answer(f"🚴 Buyurtma #{num} sizniki!")
    try:
        await callback.message.edit_text(
            order_card(order), reply_markup=kb_claimed(num),
        )
    except Exception:
        pass

    # Kuryerga shaxsiy xabar (pin bilan) — start bosmagan bo'lsa, guruhda eslatamiz
    dm_ok = True
    try:
        await callback.bot.send_message(
            courier.id,
            order_card(order, f"🚴 <b>SIZNING BUYURTMANGIZ #{num}</b>") +
            "\n\nStatuslarni guruhdagi tugmalar orqali belgilang.",
        )
        if order.get("lat") and order.get("lon"):
            await callback.bot.send_location(
                courier.id, latitude=order["lat"], longitude=order["lon"],
            )
    except Exception:
        dm_ok = False
    if not dm_ok:
        try:
            await callback.message.reply(
                f"ℹ️ {courier_name}, lokatsiya va tafsilotlarni shaxsiy xabarda "
                "olish uchun botga /start yozing."
            )
        except Exception:
            pass

    await _notify_customer(
        callback.bot, order,
        f"🚴 Buyurtmangiz #{num} uchun kuryer topildi: <b>{courier_name}</b>\n"
        "Tez orada yo'lga chiqadi!",
    )


# ─── KURYER: STATUSLAR ──────────────────────────────────────────

def _is_claimer(callback: CallbackQuery, order: dict) -> bool:
    return str(callback.from_user.id) == str(order.get("courier_id"))


@router.callback_query(F.data.startswith("disp_onway_"))
async def courier_onway(callback: CallbackQuery):
    num = callback.data.replace("disp_onway_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Topilmadi.", show_alert=True)
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    if order["status"] != "Kuryerda":
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)

    await orders_db.update_order(num, {"status": "Yo'lda"})
    order["status"] = "Yo'lda"
    await callback.answer("🚗 Yo'lda!")
    try:
        await callback.message.edit_text(order_card(order), reply_markup=kb_onway(num))
    except Exception:
        pass

    # Mijozga xabar + SIM raqam tanlash
    op_id = order.get("op_id", "")
    available = numbers_db.get_available(op_id) if op_id else []
    if available and order.get("user_id"):
        b = InlineKeyboardBuilder()
        for n in available[:10]:
            b.button(text=f"📱 {n}", callback_data=f"pick_num_{num}_{op_id}_{n.replace('-', '')}")
        b.adjust(2)
        await _notify_customer(
            callback.bot, order,
            f"🚗 <b>Kuryer yo'lga chiqdi!</b> Buyurtma #{num}\n"
            f"🚴 {order['courier_name']}\n\n"
            "📱 Vaqtni tejash uchun SIM raqamingizni hozir tanlab qo'yishingiz mumkin "
            "(yoki kuryer kelganda tanlaysiz):",
            reply_markup=b.as_markup(),
        )
    else:
        await _notify_customer(
            callback.bot, order,
            f"🚗 <b>Kuryer yo'lga chiqdi!</b> Buyurtma #{num}\n"
            f"🚴 {order['courier_name']}\n\n"
            "📱 SIM raqamni kuryer kelganda tanlaysiz.",
        )


@router.callback_query(F.data.startswith("disp_done_"))
async def courier_done(callback: CallbackQuery):
    num = callback.data.replace("disp_done_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Topilmadi.", show_alert=True)
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    if order["status"] not in ("Kuryerda", "Yo'lda"):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)

    await orders_db.update_order(num, {"status": "Yetkazildi"})
    order["status"] = "Yetkazildi"
    await callback.answer("🎉 Ajoyib ish!")
    try:
        await callback.message.edit_text(
            order_card(order, f"✅ <b>#{num} YETKAZILDI</b> — {order['courier_name']}"),
        )
    except Exception:
        pass

    # Mijozga: yetkazildi + ixtiyoriy baho
    await _notify_customer(
        callback.bot, order,
        f"🎉 <b>Buyurtmangiz #{num} yetkazib berildi!</b>\n\n"
        "Xaridingiz uchun rahmat! 🙏\n\n"
        "⭐ Xizmat sifatini baholang (ixtiyoriy):",
        reply_markup=kb_rating(num),
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"✅ #{num} yetkazildi — 🚴 {order['courier_name']}",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("disp_noshow_"))
async def courier_noshow(callback: CallbackQuery):
    num = callback.data.replace("disp_noshow_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Topilmadi.", show_alert=True)
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    if order["status"] not in ("Kuryerda", "Yo'lda"):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)

    await orders_db.update_order(num, {"status": "Mijoz yo'q"})
    order["status"] = "Mijoz yo'q"
    await callback.answer("Qayd etildi.")
    try:
        await callback.message.edit_text(
            order_card(order, f"🚫 <b>#{num} — MIJOZ TOPILMADI</b>"),
        )
    except Exception:
        pass
    await _notify_customer(
        callback.bot, order,
        f"😕 Kuryer sizga yetib bora olmadi (buyurtma #{num}).\n"
        f"Buyurtmani qayta faollashtirish uchun bog'laning: {ADMIN_CONTACT}",
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🚫 #{num} — mijoz topilmadi (🚴 {order['courier_name']}).\n"
                f"📞 Mijoz: <code>{order['phone']}</code> — bog'lanib ko'ring.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("disp_drop_"))
async def courier_drop(callback: CallbackQuery):
    num = callback.data.replace("disp_drop_", "")
    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Topilmadi.", show_alert=True)
    if not _is_claimer(callback, order):
        return await callback.answer("⛔ Bu buyurtma sizniki emas.", show_alert=True)
    if order["status"] not in ("Kuryerda", "Yo'lda"):
        return await callback.answer(f"Holat mos emas ({order['status']}).", show_alert=True)

    await orders_db.update_order(num, {
        "status": "Tasdiqlangan", "courier_id": "", "courier_name": "",
    })
    order.update(status="Tasdiqlangan", courier_id="", courier_name="")
    await callback.answer("↩️ Buyurtma qayta ochildi.")
    try:
        await callback.message.edit_text(
            order_card(order, f"🔁 <b>#{num} QAYTA OCHILDI</b> — kuryer kutilmoqda"),
            reply_markup=kb_claim(num),
        )
    except Exception:
        pass


# ─── MIJOZ: BAHO ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate_"))
async def customer_rate(callback: CallbackQuery):
    parts = callback.data.replace("rate_", "").split("_")
    if len(parts) != 2:
        return await callback.answer()
    num, score_s = parts
    try:
        score = int(score_s)
    except ValueError:
        return await callback.answer()

    order = await orders_db.get_order_by_num(num)
    if not order:
        return await callback.answer("Buyurtma topilmadi.", show_alert=True)
    if str(callback.from_user.id) != str(order.get("user_id")):
        return await callback.answer("⛔", show_alert=True)
    if order.get("rating"):
        return await callback.answer("Siz allaqachon baholagansiz. Rahmat! 😊", show_alert=True)

    await orders_db.update_order(num, {"rating": score})
    await callback.answer("Rahmat! 🙏")
    try:
        await callback.message.edit_text(
            f"🎉 <b>Buyurtmangiz #{num} yetkazib berildi!</b>\n\n"
            f"Bahoyingiz: {'⭐' * score}\n"
            "Fikringiz uchun katta rahmat! Yana murojaat eting 😊"
        )
    except Exception:
        pass

    if score <= 3:
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"⚠️ <b>Past baho:</b> #{num} — {'⭐' * score} ({score}/5)\n"
                    f"🚴 Kuryer: {order.get('courier_name', '—')}\n"
                    f"👤 Mijoz: {order.get('name', '—')} — <code>{order.get('phone', '—')}</code>",
                )
            except Exception:
                pass
