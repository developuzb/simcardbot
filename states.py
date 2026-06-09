from aiogram.fsm.state import State, StatesGroup


class OrderState(StatesGroup):
    choosing_operator = State()
    choosing_tariff = State()
    choosing_number = State()
    entering_name = State()
    entering_phone = State()
    sharing_location = State()
    choosing_delivery_type = State()
    confirming_order = State()


class AdminState(StatesGroup):
    main_menu = State()
    viewing_orders = State()
    viewing_order_detail = State()
    assigning_courier = State()
    managing_couriers = State()
    adding_courier_id = State()
    adding_courier_name = State()
    adding_courier_phone = State()
    adding_courier_region = State()
    broadcasting = State()


class CourierState(StatesGroup):
    main_menu = State()
    viewing_my_orders = State()
    updating_status = State()


class AIState(StatesGroup):
    chatting = State()
