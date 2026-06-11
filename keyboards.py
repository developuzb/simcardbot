from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from data import OPERATORS, TARIFFS
from config import DELIVERY_TYPES, PROMO_1PLUS1_MIN_PRICE, PROMO_1PLUS1_BADGE
import numbers_db

# ─── MIJOZ KLAVIATURALARI ────────────────────────────────────────

def operators_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for op_id, op in OPERATORS.items():
        builder.button(text=f"{op['emoji']} {op['name']}", callback_data=f"op_{op_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def tariffs_keyboard(operator_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tariff in TARIFFS.get(operator_id, []):
        badge = f" {PROMO_1PLUS1_BADGE}" if tariff["price"] >= PROMO_1PLUS1_MIN_PRICE else ""
        builder.button(
            text=f"📦 {tariff['name']} — {tariff['price']:,} so'm{badge}",
            callback_data=f"tariff_{tariff['id']}",
        )
    builder.button(text="⬅️ Orqaga", callback_data="back_to_operators")
    builder.adjust(1)
    return builder.as_markup()


def numbers_keyboard(operator_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for num in numbers_db.get_available(operator_id):
        builder.button(text=f"📱 {num}", callback_data=f"num_{num.replace('-', '')}")
    builder.button(text="🎲 Tasodifiy raqam", callback_data="num_random")
    builder.button(text="⬅️ Orqaga", callback_data="back_to_tariffs")
    builder.adjust(1)
    return builder.as_markup()


def location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def delivery_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, dt in DELIVERY_TYPES.items():
        price_text = "Bepul" if dt["price"] == 0 else f"{dt['price']:,} so'm"
        builder.button(
            text=f"{dt['emoji']} {dt['desc']} — {price_text}",
            callback_data=f"dtype_{key}",
        )
    builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data="confirm_order")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(2)
    return builder.as_markup()


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 AI yordamchi bilan tanlash", callback_data="open_ai_chat")
    builder.button(text="🛒 Tezkor buyurtma", callback_data="new_order")
    builder.button(text="🎁 Aksiyalar", callback_data="show_promo")
    builder.button(text="📋 Tariflar", callback_data="show_tariffs")
    builder.button(text="📞 Aloqa", callback_data="contact")
    builder.button(text="ℹ️ Biz haqimizda", callback_data="show_about")
    builder.adjust(1, 1, 2, 2)
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 AI yordamchi", callback_data="open_ai_chat")
    builder.button(text="🛒 Buyurtma", callback_data="new_order")
    builder.button(text="⬅️ Bosh sahifa", callback_data="back_to_main")
    builder.adjust(2, 1)
    return builder.as_markup()


# ─── ADMIN KLAVIATURALARI ────────────────────────────────────────

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Buyurtmalar", callback_data="adm_orders")
    builder.button(text="📊 Statistika", callback_data="adm_stats")
    builder.button(text="🚴 Kuryerlar", callback_data="adm_couriers")
    builder.button(text="📢 Xabar yuborish", callback_data="adm_broadcast")
    builder.button(text="📈 AI Analitika", callback_data="adm_analytics")
    builder.button(text="📍 Ofis lokatsiyasi", callback_data="adm_office")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def analytics_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 AI Insight (tavsiya)", callback_data="adm_an_insight")
    builder.button(text="📊 AI Statistika", callback_data="adm_an_stats")
    builder.button(text="🔄 Yangilash", callback_data="adm_analytics")
    builder.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    builder.adjust(1)
    return builder.as_markup()


def office_location_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Ofis lokatsiyasini yuborish", request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def office_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 Lokatsiyani o'zgartirish", callback_data="adm_office_set")
    builder.button(text="📏 Radiusni o'zgartirish", callback_data="adm_office_radius")
    builder.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_orders_filter_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Yangi", callback_data="adm_filter_Yangi")
    builder.button(text="📢 Tasdiqlangan", callback_data="adm_filter_Tasdiqlangan")
    builder.button(text="🚴 Kuryerda", callback_data="adm_filter_Kuryerda")
    builder.button(text="🚗 Yo'lda", callback_data="adm_filter_Yo'lda")
    builder.button(text="✅ Yetkazildi", callback_data="adm_filter_Yetkazildi")
    builder.button(text="🚫 Mijoz yo'q", callback_data="adm_filter_Mijoz yo'q")
    builder.button(text="❌ Bekor", callback_data="adm_filter_Bekor")
    builder.button(text="📋 Barchasi", callback_data="adm_filter_all")
    builder.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def admin_order_detail_keyboard(order_num, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if status == "Yangi":
        builder.button(text="✅ Qabul qilish", callback_data=f"adm_accept_{order_num}")
        builder.button(text="🚴 Kuryer tayinlash", callback_data=f"adm_assign_{order_num}")
        builder.button(text="❌ Bekor qilish", callback_data=f"adm_cancel_{order_num}")
    elif status == "Tayinlandi":
        builder.button(text="🚴 Kuryer o'zgartirish", callback_data=f"adm_assign_{order_num}")
        builder.button(text="❌ Bekor qilish", callback_data=f"adm_cancel_{order_num}")
    elif status in ("Yo'lda",):
        builder.button(text="✔️ Yetkazildi deb belgilash", callback_data=f"adm_delivered_{order_num}")
        builder.button(text="❌ Bekor qilish", callback_data=f"adm_cancel_{order_num}")

    builder.button(text="⬅️ Ro'yxatga", callback_data="adm_orders")
    builder.adjust(1)
    return builder.as_markup()


def admin_couriers_keyboard(couriers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in couriers:
        icon = "🟢" if c.get("status") == "Faol" else "🔴"
        builder.button(
            text=f"{icon} {c['name']} ({c.get('completed', 0)} ta)",
            callback_data=f"adm_cur_{c['telegram_id']}",
        )
    builder.button(text="➕ Kuryer qo'shish", callback_data="adm_add_courier")
    builder.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_courier_detail_keyboard(courier_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 O'chirish", callback_data=f"adm_del_cur_{courier_id}")
    builder.button(text="⬅️ Orqaga", callback_data="adm_couriers")
    builder.adjust(2)
    return builder.as_markup()


def select_courier_keyboard(couriers: list, order_num) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in couriers:
        if c.get("status") == "Faol":
            builder.button(
                text=f"🚴 {c['name']} — {c.get('regions', 'Barcha')}",
                callback_data=f"adm_set_cur_{order_num}_{c['telegram_id']}",
            )
    builder.button(text="⬅️ Bekor", callback_data=f"adm_ord_{order_num}")
    builder.adjust(1)
    return builder.as_markup()


def orders_list_keyboard(orders: list, page: int = 0) -> InlineKeyboardMarkup:
    """Buyurtmalar ro'yxati, sahifalash bilan (5 tadan)."""
    builder = InlineKeyboardBuilder()
    page_size = 5
    start = page * page_size
    chunk = orders[start: start + page_size]

    status_icons = {
        "Yangi": "🆕", "Tasdiqlangan": "📢", "Kuryerda": "🚴",
        "Yo'lda": "🚗", "Yetkazildi": "✅", "Mijoz yo'q": "🚫", "Bekor": "❌",
    }

    for o in chunk:
        icon = status_icons.get(o["status"], "•")
        builder.button(
            text=f"{icon} #{o['num']} {o['name']} — {o['region']}",
            callback_data=f"adm_ord_{o['num']}",
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm_page_{page-1}"))
    if start + page_size < len(orders):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm_page_{page+1}"))

    builder.adjust(1)
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Filter", callback_data="adm_orders"))
    return builder.as_markup()


# ─── KURYER KLAVIATURALARI ───────────────────────────────────────

def courier_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Mening buyurtmalarim", callback_data="cur_my_orders")
    builder.button(text="👤 Profilim", callback_data="cur_profile")
    builder.adjust(1)
    return builder.as_markup()


def courier_order_list_keyboard(orders: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_icons = {"Tayinlandi": "🆕", "Yo'lda": "🚗", "Yetkazildi": "✔️"}
    for o in orders:
        if o["status"] in ("Tayinlandi", "Yo'lda"):
            icon = status_icons.get(o["status"], "•")
            builder.button(
                text=f"{icon} #{o['num']} — {o['region']} ({o['name']})",
                callback_data=f"cur_ord_{o['num']}",
            )
    builder.button(text="⬅️ Menyu", callback_data="cur_menu")
    builder.adjust(1)
    return builder.as_markup()


def courier_order_actions_keyboard(order_num, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "Tayinlandi":
        builder.button(text="🚗 Yo'lga chiqdim", callback_data=f"cur_onway_{order_num}")
    elif status == "Yo'lda":
        builder.button(text="✅ Yetkazib berdim", callback_data=f"cur_done_{order_num}")
    builder.button(text="⬅️ Orqaga", callback_data="cur_my_orders")
    builder.adjust(1)
    return builder.as_markup()
