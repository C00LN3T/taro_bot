from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_birthdate = State()
    waiting_for_second_birthdate = State()
    waiting_for_language = State()
    waiting_for_gender = State()
    confirming_delete = State()


class TarotStates(StatesGroup):
    choosing_spread = State()
    awaiting_question = State()


class NumerologyStates(StatesGroup):
    choosing_calculation = State()
    waiting_for_birthdate = State()
    waiting_for_second_birthdate = State()
    waiting_for_name = State()


class AstroStates(StatesGroup):
    waiting_for_birthdate = State()


class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
