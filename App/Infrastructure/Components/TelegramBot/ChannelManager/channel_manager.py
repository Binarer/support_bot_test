import logging
from aiogram import Bot
from aiogram.types import Message as TgMessage

from App.Domain.Models.Ticket.Ticket import Ticket
from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.support_channel_id = config.SUPPORT_CHANNEL_ID
        logger.info(f"ChannelManager инициализирован для канала: {self.support_channel_id}")

    async def create_ticket_topic(self, ticket: Ticket) -> int:
        logger.info(f"Создание топика форума для тикета {ticket.id}")

        message_text = (
            f"🎫 Тикет #{ticket.display_id}\n\n"
            f"👤 Пользователь: @{ticket.username}\n"
            f"📝 Сообщение: {ticket.user_message}\n\n"
            f"⏰ Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: 🔓 Открыт\n\n"
            f"💬 Ответьте на это сообщение чтобы написать пользователю"
        )

        try:
            topic = await self.bot.create_forum_topic(
                chat_id=self.support_channel_id,
                name=f"Ticket #{ticket.display_id}"
            )

            logger.info(f"Топик форума создан для тикета {ticket.id}, thread_id: {topic.message_thread_id}")

            ticket.topic_thread_id = topic.message_thread_id

            await self.bot.edit_forum_topic(
                chat_id=self.support_channel_id,
                message_thread_id=ticket.topic_thread_id,
                icon_custom_emoji_id="5377316857231450742"
            )
            logger.info(f"Иконка топика установлена на ❓ для тикета {ticket.id}")

            message = await self.bot.send_message(
                chat_id=self.support_channel_id,
                message_thread_id=topic.message_thread_id,
                text=message_text
            )

            logger.info(f"Начальное сообщение тикета {ticket.id} отправлено, message_id: {message.message_id}")
            return message.message_id

        except Exception as e:
            logger.error(f"Ошибка создания топика форума для тикета: {e}")
            raise

    async def send_user_message(self, ticket: Ticket, message_text: str):
        try:
            await self.bot.send_message(
                chat_id=self.support_channel_id,
                message_thread_id=ticket.topic_thread_id,
                text=message_text
            )
            logger.info(f"Сообщение пользователя добавлено в тикет {ticket.id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователя: {e}")

    async def send_support_reply(self, user_id: int, support_message: str, support_name: str):
        """Отправка ответа от поддержки пользователю"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=support_message
            )
            logger.info(f"Ответ поддержки отправлен пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки ответа пользователю: {e}")

    async def update_topic_icon(self, ticket: Ticket, icon: str):
        status_text = {
            "❓": "Ждет ответа",
            "☑️": "Отвечен",
            "💼": "Закрыт"
        }
        status_name = status_text.get(icon, 'Неизвестен')

        emoji_to_id = {
            "❓": "5377316857231450742",
            "☑️": "5237699328843200968",
            "💼": "5348227245599105972"
        }
        custom_emoji_id = emoji_to_id.get(icon)

        new_text = (
            f"🎫 Тикет #{ticket.display_id}\n\n"
            f"👤 Пользователь: @{ticket.username}\n"
            f"📝 Сообщение: {ticket.user_message}\n\n"
            f"⏰ Обновлен: {ticket.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: {status_name} {icon}\n\n"
            f"💬 Отправьте сообщение в этот топик чтобы ответить пользователю"
        )

        try:
            # иконка топика
            if custom_emoji_id and ticket.topic_thread_id:
                await self.bot.edit_forum_topic(
                    chat_id=self.support_channel_id,
                    message_thread_id=ticket.topic_thread_id,
                    icon_custom_emoji_id=custom_emoji_id
                )
                logger.info(f"Иконка топика для тикета {ticket.id} обновлена на {icon}")

            await self.bot.edit_message_text(
                chat_id=self.support_channel_id,
                message_id=ticket.channel_message_id,
                text=new_text
            )
            logger.info(f"Топик тикета {ticket.id} обновлен")
        except Exception as e:
            logger.error(f"Ошибка обновления топика тикета: {e}")
