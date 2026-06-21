from aiogram.fsm.state import State, StatesGroup


class ProfileCreation(StatesGroup):
    city = State()
    district = State()
    age = State()
    gender = State()
    seeking_gender = State()
    goal = State()
    interests = State()
    photo = State()
    confirm = State()


class VerificationFlow(StatesGroup):
    awaiting_media = State()


class DangerReport(StatesGroup):
    awaiting_reason = State()
