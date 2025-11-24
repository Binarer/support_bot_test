import logging
from typing import Optional

from App.Domain.Models.Ticket.Ticket import Ticket
from App.Infrastructure.Components.TelegramBot.ChannelManager.channel_manager import ChannelManager

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, channel_manager: ChannelManager):
        self.channel_manager = channel_manager
        self.active_tickets: dict[int, Ticket] = {}
        self.ticket_by_message_id: dict[int, Ticket] = {}
        self.ticket_by_thread_id: dict[int, Ticket] = {}
        logger.info("TicketService инициализирован")

    async def create_ticket(self, user_id: int, username: str, user_message: str) -> Ticket:
        logger.info(f"Создание тикета для пользователя {user_id}")
        ticket = Ticket(user_id, username, user_message)
        try:
            channel_message_id = await self.channel_manager.create_ticket_topic(ticket)
            ticket.channel_message_id = channel_message_id
            self.active_tickets[user_id] = ticket
            self.ticket_by_message_id[channel_message_id] = ticket
            if ticket.topic_thread_id:
                self.ticket_by_thread_id[ticket.topic_thread_id] = ticket
            logger.info(f"Тикет создан: {ticket.id}")
        except Exception as e:
            logger.error(f"Ошибка создания топика в канале: {e}")
            raise

        return ticket

    async def has_active_ticket(self, user_id: int) -> bool:
        return user_id in self.active_tickets

    async def forward_user_message(self, user_id: int, message_text: str):
        if user_id not in self.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = self.active_tickets[user_id]
        await self.channel_manager.send_user_message(ticket, message_text)

        await self.channel_manager.update_topic_icon(ticket, "❓")
        logger.info(f"Сообщение от пользователя {user_id}: {message_text}")

    async def process_support_message(self, message_id: int, support_message: str, support_name: str):
        """Обработка сообщения от поддержки"""
        if message_id not in self.ticket_by_message_id:
            logger.warning(f"Сообщение {message_id} не принадлежит ни одному тикету")
            return

        ticket = self.ticket_by_message_id[message_id]

        # Отправляем ответ пользователю
        await self.channel_manager.send_support_reply(
            ticket.user_id,
            support_message,
            support_name
        )

        # Обновляем иконку на "☑️" (отвечено)
        ticket.mark_answered()
        await self.channel_manager.update_topic_icon(ticket, "☑️")
        logger.info(f"Ответ поддержки для тикета {ticket.id}")

    def get_ticket_by_message_id(self, message_id: int) -> Optional[Ticket]:
        return self.ticket_by_message_id.get(message_id)

    def get_ticket_by_thread_id(self, thread_id: int) -> Optional[Ticket]:
        return self.ticket_by_thread_id.get(thread_id)

    async def close_ticket_by_user(self, user_id: int):
        if user_id not in self.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = self.active_tickets[user_id]
        username = ticket.username
        ticket.close(f"user_{username}")
        del self.active_tickets[user_id]

        # Очистить соответствия
        if ticket.channel_message_id in self.ticket_by_message_id:
            del self.ticket_by_message_id[ticket.channel_message_id]
        if ticket.topic_thread_id in self.ticket_by_thread_id:
            del self.ticket_by_thread_id[ticket.topic_thread_id]

        # Обновить топик и закрыть
        await self.channel_manager.close_ticket_by_user(ticket)
        logger.info(f"Тикет {ticket.id} закрыт пользователем {username}")
