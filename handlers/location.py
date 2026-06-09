from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import OrderState
from keyboards import confirm_keyboard, remove_keyboard
from utils import detect_region, get_delivery_price, build_order_summary
from sheets_handler import save_order

router = Router()


@router.message(OrderState.sharing_location, F.location)
async def receive_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude

    region = detect_region(lat, lon)
    delivery_price = get_delivery_price(region)

    await state.update_data(
        region=region,
        delivery_price=delivery_price,
        latitude=lat,
        longitude=lon,
    )
    await state.set_state(OrderState.confirming_order)

    user_data = await state.get_data()
    summary = build_order_summary(user_data)

    await message.answer(
        f"📍 <b>Hudud aniqlandi:</b> {region}\n\n"
        f"{summary}\n\n"
        f"Buyurtmani tasdiqlaysizmi?",
        reply_markup=confirm_keyboard(),
    )
    await message.answer("Klaviatura o'chirildi.", reply_markup=remove_keyboard())


@router.callback_query(OrderState.confirming_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    from config import ADMIN_IDS

    user_data = await state.get_data()
    user_data["user_id"] = callback.from_user.id

    saved = await save_order(user_data)

    await callback.message.edit_text(
        "🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"📍 Hudud: <b>{user_data.get('region')}</b>\n"
        f"📱 Raqam: <code>{user_data.get('sim_number')}</code>\n\n"
        "⏱ Kuryer siz bilan tez orada bog'lanadi.\n"
        "📞 Savollar uchun: /start → Aloqa\n\n"
        "✅ Yetkazib berish vaqti: <b>1-3 ish kuni</b>"
    )

    try:
        bot = callback.bot
        summary = build_order_summary(user_data)
        username = callback.from_user.username or "Noma'lum"
        admin_text = (
            f"🔔 <b>YANGI BUYURTMA!</b>\n\n"
            f"👤 Foydalanuvchi: @{username} "
            f"(ID: {callback.from_user.id})\n\n"
            f"{summary}"
        )
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, admin_text)
    except Exception:
        pass

    await state.clear()
    await callback.answer("✅ Buyurtma qabul qilindi!")


@router.callback_query(OrderState.confirming_order, F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Buyurtma bekor qilindi.\n\n"
        "Qaytadan boshlash uchun /start bosing."
    )
    await callback.answer("Bekor qilindi")
