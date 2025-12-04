import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType
from App.Infrastructure.Config import config
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

            
            await self.ticket_service.process_support_topic_message(thread_id, message)

            logger.info(f"Обработано сообщение поддержки для тикета {ticket.id}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения поддержки: {e}")
