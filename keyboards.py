from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─── MIJOZ KLAVIATURALARI ────────────────────────────────────────

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Buyurtma berish", callback_data="new_order")
    builder.button(text="🤖 AI yordamchi bilan tanlash", callback_data="open_ai_chat")
    builder.button(text="🎁 Aksiyalar", callback_data="show_promo")
    builder.button(text="📋 Tariflar", callback_data="show_tariffs")
    builder.button(text="👥 Do'st taklif qil", callback_data="show_referral")
    builder.button(text="📞 Aloqa", callback_data="contact")
    builder.button(text="ℹ️ Biz haqimizda", callback_data="show_about")
    builder.adjust(1, 1, 2, 2, 1)
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
    builder.button(text="📈 AI Analitika", callback_data="adm_analytics")
    builder.button(text="📢 Xabar yuborish", callback_data="adm_broadcast")
    builder.button(text="📍 Ofis lokatsiyasi", callback_data="adm_office")
    builder.adjust(2, 2, 1)
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
    builder.button(text="🟠 Hudud tashqari", callback_data="adm_filter_Hudud tashqarisida")
    builder.button(text="❌ Bekor", callback_data="adm_filter_Bekor")
    builder.button(text="📋 Barchasi", callback_data="adm_filter_all")
    builder.button(text="⬅️ Orqaga", callback_data="adm_back_menu")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def orders_list_keyboard(orders: list, page: int = 0) -> InlineKeyboardMarkup:
    """Buyurtmalar ro'yxati, sahifalash bilan (5 tadan)."""
    builder = InlineKeyboardBuilder()
    page_size = 5
    start = page * page_size
    chunk = orders[start: start + page_size]

    status_icons = {
        "Yangi": "🆕", "Tasdiqlangan": "📢", "Kuryerda": "🚴", "Yo'lda": "🚗",
        "Yetkazildi": "✅", "Mijoz yo'q": "🚫", "Bekor": "❌", "Hudud tashqarisida": "🟠",
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
