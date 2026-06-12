from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    main_menu = State()
    viewing_orders = State()
    broadcasting = State()
    setting_office_location = State()
    setting_office_radius = State()


class AIState(StatesGroup):
    chatting = State()
