import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from App.Domain.Services.TicketService.ticket_service import TicketService

logger = logging.getLogger(__name__)


class SupportProcessor:
    def __init__(self, ticket_service: TicketService):
        self.router = Router()
        self.ticket_service = ticket_service
        self._setup_handlers()

    def _setup_handlers(self):
        self.router.message.register(
            self._process_support_message,
            F.chat.type.in_([ChatType.CHANNEL, ChatType.SUPERGROUP]),
            F.message_thread_id
        )

    async def _process_support_message(self, message: Message):
        try:
            thread_id = message.message_thread_id

            ticket = self.ticket_service.get_ticket_by_thread_id(thread_id)

            if not ticket:
                logger.warning(f"Тикет для thread_id {thread_id} не найден")
                return

            support_message = message.text
            if not support_message or support_message.strip() == "":
                logger.info(f"Пропускаем пустое сообщение от поддержки в тикете {ticket.id}")
                return

            support_name = message.from_user.username or message.from_user.first_name

            await self.ticket_service.process_support_message(
                ticket.channel_message_id,
                support_message,
                support_name
            )

            logger.info(f"Обработано сообщение поддержки для тикета {ticket.id}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения поддержки: {e}")
