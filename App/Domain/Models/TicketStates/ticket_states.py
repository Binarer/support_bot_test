from aiogram.fsm.state import State, StatesGroup

class TicketStates(StatesGroup):
    waiting_for_problem = State()
    waiting_for_rating_comment = State()
    renaming_ticket = State()
