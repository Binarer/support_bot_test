from aiogram.fsm.state import State, StatesGroup

class TicketStates(StatesGroup):
    waiting_for_problem = State()