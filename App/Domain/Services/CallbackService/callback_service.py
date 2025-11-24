import logging
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from App.Domain.Models.TicketStates.ticket_states import TicketStates
from App.Domain.Services.TicketService.ticket_service import TicketService

logger = logging.getLogger(__name__)


class CallbackService:
    def __init__(self, ticket_service: TicketService):
        self.ticket_service = ticket_service

    async def process_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        callback_data = callback.data

        logger.info(f"Обработка callback от пользователя {user_id}: {callback_data}")

        if callback_data == "create_ticket":
            await self._handle_create_ticket_callback(callback, state)
        else:
            await callback.answer("Неизвестное действие")

    async def _handle_create_ticket_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id

        if await self.ticket_service.has_active_ticket(user_id):
            await callback.answer("У вас уже есть активный тикет", show_alert=True)
            return

        await state.set_state(TicketStates.waiting_for_problem)
        await callback.answer()
        await callback.message.answer("📝 Опишите вашу проблему:")