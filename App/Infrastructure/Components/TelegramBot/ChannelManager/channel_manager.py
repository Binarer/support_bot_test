import logging
from aiogram import Bot
from aiogram.types import Message as TgMessage, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

from App.Domain.Models.Ticket.Ticket import Ticket
from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.support_channel_id = config.SUPPORT_CHANNEL_ID
        self.general_topic_id = config.GENERAL_TOPIC_ID
        self._reviews_topic_id: Optional[int] = config.REVIEWS_TOPIC_ID  
        logger.info(f"ChannelManager инициализирован для канала: {self.support_channel_id}, general_topic_id: {self.general_topic_id}, reviews_topic_id: {self._reviews_topic_id}")

    async def send_ticket_to_general(self, ticket: Ticket) -> int:
        logger.info(f"Отправка тикета {ticket.id} в общий топик")
        thread_id = self.general_topic_id if self.general_topic_id > 0 else None

        category_display = self._get_category_display_name(ticket.category)
        message_text = (
            f"🎫 Тикет #{ticket.display_id}\n"
            f"👤 Пользователь: @{ticket.username}\n"
            f"📋 {ticket.user_message}\n\n"
            f"⏰ Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: ⏳ Ожидает принятия\n\n"
        )

        admin_take_keyboard = config.bot_keyboards.get('admin_take', [])
        processed_take_buttons = []

        for row in admin_take_keyboard:
            if isinstance(row, list):
                button_row = []
                for btn in row:
                    if isinstance(btn, dict):
                        new_btn = InlineKeyboardButton(
                            text=btn.get('text', 'Взять в работу'),
                            callback_data=btn.get('callback_data', 'take:').replace('{number}', str(ticket.display_id))
                        )
                        button_row.append(new_btn)
                processed_take_buttons.append(button_row)

        cancel_keyboard = config.bot_keyboards.get('cancel', [])
        processed_cancel_buttons = []

        for row in cancel_keyboard:
            if isinstance(row, list):
                button_row = []
                for btn in row:
                    if isinstance(btn, dict):
                        new_btn = InlineKeyboardButton(
                            text=btn.get('text', 'Отменить'),
                            callback_data=f"cancel_ticket:{ticket.display_id}"
                        )
                        button_row.append(new_btn)
                processed_cancel_buttons.append(button_row)
            elif isinstance(row, dict):
                new_btn = InlineKeyboardButton(
                    text=row.get('text', 'Отменить'),
                    callback_data=f"cancel_ticket:{ticket.display_id}"
                )
                processed_cancel_buttons.append([new_btn])

        keyboard = InlineKeyboardMarkup(inline_keyboard=processed_take_buttons + processed_cancel_buttons)

        try:
            message = await self.bot.send_message(
                chat_id=self.support_channel_id,
                message_thread_id=thread_id,
                text=message_text,
                reply_markup=keyboard
            )
            logger.info(f"Тикет {ticket.id} отправлен в общий топик, message_id: {message.message_id}")
            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка отправки тикета в общий топик: {e}")
            raise

    async def update_general_message(self, ticket: Ticket, status: str):
        cancelled_text = (
            f"🎫 Тикет #{ticket.display_id}\n"
            f"👤 Пользователь: @{ticket.username}\n"
            f"📝 {ticket.user_message}\n\n"
            f"⏰ Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: {status}\n\n"
        )

        try:
            await self.bot.edit_message_text(
                chat_id=self.support_channel_id,
                message_id=ticket.channel_message_id,
                text=cancelled_text,
                reply_markup=None
            )
            logger.info(f"Сообщение тикета {ticket.id} обновлено в общем топике")
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения в общем топике: {e}")

    def _get_ticket_closed_text(self, db_ticket):
        """Генерирует текст для закрытого тикета из записи базы данных"""
        closed_text = (
            f"🎫 Тикет #{db_ticket.display_id}\n"
            f"👤 Пользователь: @{db_ticket.username}\n"
            f"📝 {db_ticket.user_message}\n\n"
            f"⏰ Создан: {db_ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: ✅ Закрыт\n\n"
        )
        return closed_text

    def _get_category_display_name(self, category_callback: str) -> str:
        """Преобразует callback категории в отображаемое имя из bot.json"""
        user_categories = config.bot_keyboards.get('user_categories', [])
        for category in user_categories:
            if category.get('callback_data') == f"cat:{category_callback}":
                return category.get('text', category_callback)
        return category_callback

    async def send_user_start_and_categories(self, ticket: Ticket):
        user_start = config.bot_messages.get('user_start', 'Welcome message')
        user_categories_keyboard = config.bot_keyboards.get('user_categories', [])

        try:
            await self.bot.send_message(
                chat_id=ticket.user_id,
                text=user_start,
                parse_mode="HTML"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=user_categories_keyboard)
            await self.bot.send_message(
                chat_id=ticket.user_id,
                text="Выберите категорию:",
                reply_markup=keyboard
            )

            logger.info(f"Отправлено приветствие и категории пользователю {ticket.user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки приветствия пользователю: {e}")

    async def send_user_ticket_message(self, ticket: Ticket) -> int:
        user_ticket_text = config.bot_messages.get('user_ticket', 'Ticket created message')
        cancel_button = [
            {"text": "❌ Отменить тикет", "callback_data": f"cancel_ticket:{ticket.display_id}"}
        ]
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[cancel_button])

        try:
            category_display = self._get_category_display_name(ticket.category) if ticket.category else 'Не указана'
            message = await self.bot.send_message(
                chat_id=ticket.user_id,
                text=user_ticket_text.format(
                    number=ticket.display_id,
                    category=category_display,
                    created=ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ),
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
            ticket.user_message_id = message.message_id
            logger.info(f"Отправлено сообщение о создании тикета пользователю {ticket.user_id}, message_id: {message.message_id}")
            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о тикете пользователю: {e}")
            return None

    async def edit_user_ticket_message_cancelled(self, ticket: Ticket):
        """Обновляет сообщение пользователя при отмене тикета"""
        try:
            user_ticket_text = config.bot_messages.get('user_ticket', 'Ticket created message')
            category_display = self._get_category_display_name(ticket.category) if ticket.category else 'Не указана'
            original_text = user_ticket_text.format(
                number=ticket.display_id,
                category=category_display,
                created=ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')
            )

            from datetime import datetime
            current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
            bot_name = self.bot.username or "test_helper_bot"
            cancellation_info = f"\n{bot_name}, [{current_time}]\n❌ Ваш тикет отменен\n"

            new_text = original_text + cancellation_info

            await self.bot.edit_message_text(
                chat_id=ticket.user_id,
                message_id=ticket.user_message_id,
                text=new_text,
                parse_mode="HTML",
                reply_markup=None
            )
            logger.info(f"Сообщение тикета пользователя {ticket.user_id} обновлено с отменой")
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения пользователя при отмене: {e}")

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

    async def send_user_media(self, ticket: Ticket, message):
        """Отправка медиа от пользователя в топик тикета"""
        try:
            await self.bot.copy_message(
                chat_id=self.support_channel_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=ticket.topic_thread_id
            )
            logger.info(f"Медиа пользователя добавлено в тикет {ticket.id}")
        except Exception as e:
            logger.error(f"Ошибка отправки медиа пользователя: {e}")

    async def send_support_reply(self, user_id: int, support_message: str, support_name: str):
        try:
            
            if not self._is_valid_telegram_chat_id(user_id):
                logger.info(f"Пользователь {user_id} не имеет Telegram аккаунта, пропускаем отправку сообщения")
                return

            await self.bot.send_message(
                chat_id=user_id,
                text=support_message,
                parse_mode='HTML'
            )
            logger.info(f"Ответ поддержки отправлен пользователю {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить ответ пользователю {user_id} (возможно веб-пользователь): {e}")
            
            

    def _is_valid_telegram_chat_id(self, user_id: int) -> bool:
        """Проверяет, является ли user_id валидным Telegram chat_id"""
        
        
        
        
        
        if user_id <= 0:
            return True  
        if 1 <= user_id <= 999999999:
            return True  
        return False  

    async def send_support_media_reply(self, user_id: int, message):
        """Отправка медиа от поддержки пользователю"""
        try:
            
            if not self._is_valid_telegram_chat_id(user_id):
                logger.info(f"Пользователь {user_id} не имеет Telegram аккаунта, пропускаем отправку медиа")
                return

            await self.bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            logger.info(f"Медиа поддержки отправлено пользователю {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить медиа пользователю {user_id} (возможно веб-пользователь): {e}")
            
            

    async def rename_topic(self, ticket: Ticket, new_name: str) -> bool:
        try:
            await self.bot.edit_forum_topic(
                chat_id=self.support_channel_id,
                message_thread_id=ticket.topic_thread_id,
                name=new_name
            )
            logger.info(f"Топик тикета {ticket.id} переименован в: {new_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка переименования топика для тикета {ticket.id}: {e}")
            return False

    async def update_topic_icon(self, ticket: Ticket, icon: str):
        status_text = {
            "❓": "Ждет ответа",
            "☑️": "Отвечен",
            "✅": "Закрыт",
            "🔧": "В работе"
        }
        status_name = status_text.get(icon, 'Неизвестен')

        emoji_to_id = {
            "❓": "5377316857231450742",
            "☑️": None,
            "✅": "5237699328843200968",
            "🔧": "5238156910363950406"
        }
        custom_emoji_id = emoji_to_id.get(icon)

        new_text = (
            f"🎫 Тикет #{ticket.display_id}\n"
            f"👤 Пользователь: @{ticket.username}\n"
            f"📝 {ticket.user_message}\n\n"
            f"⏰ Обновлен: {ticket.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📌 Статус: {status_name} {icon}\n\n"
        )

        try:
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
    
    async def take_ticket_and_create_topic(self, ticket: Ticket, admin_id: int, admin_name: str) -> int:
        logger.info(f"Взятие тикета {ticket.id} администратором {admin_name}")
        topic_name = f"Тикет #{ticket.display_id}"
        message_text = config.bot_messages.get('menu_message', 'Menu message')

        try:
            topic = await self.bot.create_forum_topic(
                chat_id=self.support_channel_id,
                name=topic_name
            )

            ticket.topic_thread_id = topic.message_thread_id

            await self.bot.edit_forum_topic(
                chat_id=self.support_channel_id,
                message_thread_id=ticket.topic_thread_id,
                icon_custom_emoji_id="5238156910363950406"
            )

            keyboard_data = config.bot_keyboards.get('ticket_admin', [])

            processed_keyboard = []
            for row in keyboard_data:
                processed_row = []
                for button in row:
                    button_data = button.copy()
                    if 'callback_data' in button_data:
                        button_data['callback_data'] = button_data['callback_data'].replace('{id}', str(ticket.db_id)).replace('{number}', str(ticket.display_id))
                    inline_button = InlineKeyboardButton(**button_data)
                    processed_row.append(inline_button)
                processed_keyboard.append(processed_row)

            menu_keyboard = InlineKeyboardMarkup(inline_keyboard=processed_keyboard) if processed_keyboard else None

            menu_message = await self.bot.send_message(
                chat_id=self.support_channel_id,
                message_thread_id=ticket.topic_thread_id,
                text=message_text.format(number=ticket.display_id, admin_name=admin_name),
                reply_markup=menu_keyboard,
                parse_mode="HTML"
            )

            taken_text = (
                f"🎫 Тикет #{ticket.display_id}\n"
                f"👤 Пользователь: @{ticket.username}\n"
                f"📝 {ticket.user_message}\n\n"
                f"⏰ Взят: администратором {admin_name}\n"
                f"📌 Статус: 🔧 В работе\n\n"
            )

            try:
                await self.bot.edit_message_text(
                    chat_id=self.support_channel_id,
                    message_id=ticket.channel_message_id,
                    text=taken_text,
                    reply_markup=None
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение тикета в общем канале: {e}")

            user_instruction = config.bot_messages.get('user_instruction', '')
            if user_instruction:
                try:
                    await self.bot.send_message(
                        chat_id=ticket.user_id,
                        text=user_instruction,
                        parse_mode="HTML"
                    )
                    logger.info(f"Инструкции отправлены пользователю {ticket.user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки инструкций пользователю {ticket.user_id}: {e}")

            logger.info(f"Тикет {ticket.id} взят, топик создан, message_id: {menu_message.message_id}")
            return menu_message.message_id
        except Exception as e:
            logger.error(f"Ошибка взятия тикета и создания топика: {e}")
            raise

    async def close_ticket_by_user(self, ticket: Ticket):
        """Обрабатывает обновления UI при закрытии тикета пользователем"""
        try:
            await self._notify_ticket_closed_by_user(ticket)
        except Exception as e:
            logger.warning(f"Не удалось уведомить о закрытии тикета #{ticket.display_id}: {e}")

        try:
            await self.update_general_message(ticket, "✅ Закрыт пользователем")
        except Exception as e:
            logger.warning(f"Не удалось обновить общее сообщение для тикета #{ticket.display_id}: {e}")

        try:
            if ticket.topic_thread_id:
                try:
                    await self.bot.close_forum_topic(
                        chat_id=self.support_channel_id,
                        message_thread_id=ticket.topic_thread_id
                    )
                except Exception as e:
                    logger.warning(f"Не удалось закрыть топик форума: {e}")

        except Exception as e:
            logger.warning(f"Ошибка в close_ticket_by_user: {e}")

    async def close_ticket_by_admin(self, ticket: Ticket):
        """Обрабатывает обновления UI при закрытии тикета администратором"""
        try:
            await self._notify_ticket_closed_by_admin(ticket)
        except Exception as e:
            logger.warning(f"Не удалось уведомить о закрытии тикета #{ticket.display_id}: {e}")

        try:
            await self.update_general_message(ticket, "✅ Закрыт администратором")
        except Exception as e:
            logger.warning(f"Не удалось обновить общее сообщение для тикета #{ticket.display_id}: {e}")

        try:
            # Установить иконку закрытого тикета перед закрытием топика
            if ticket.topic_thread_id:
                try:
                    await self.bot.edit_forum_topic(
                        chat_id=self.support_channel_id,
                        message_thread_id=ticket.topic_thread_id,
                        icon_custom_emoji_id="5237699328843200968"
                    )
                    logger.info(f"Установлена иконка закрытого тикета для топика {ticket.topic_thread_id}")
                except Exception as e:
                    logger.warning(f"Не удалось установить иконку закрытого тикета: {e}")

                try:
                    await self.bot.close_forum_topic(
                        chat_id=self.support_channel_id,
                        message_thread_id=ticket.topic_thread_id
                    )
                except Exception as e:
                    logger.warning(f"Не удалось закрыть топик форума: {e}")

        except Exception as e:
            logger.warning(f"Ошибка в close_ticket_by_admin: {e}")

    async def notify_ticket_cancelled(self, ticket: Ticket, cancelled_by_admin: bool):
        """Уведомляет команду поддержки об отмене тикета"""
        if cancelled_by_admin:
            notification_text = (
                f"⚠️ Администратор отменил тикет #{ticket.display_id}\n"
            )
        else:
            notification_text = (
                f"ℹ️ Пользователь @{ticket.username} отменил тикет #{ticket.display_id}\n"
            )

        target_threads = []
        if ticket.topic_thread_id:
            target_threads.append(ticket.topic_thread_id)

        general_thread_id = self.general_topic_id if self.general_topic_id and self.general_topic_id > 0 else None
        if general_thread_id not in target_threads:
            target_threads.append(general_thread_id)

        await self._send_notification_to_threads(notification_text, target_threads)

    async def _notify_ticket_closed_by_user(self, ticket: Ticket):
        """Информирует сотрудников поддержки о закрытии тикета пользователем"""
        notification_text = (
            f"ℹ️ Пользователь @{ticket.username} закрыл тикет #{ticket.display_id}\n"
        )

        target_threads = []
        if ticket.topic_thread_id:
            target_threads.append(ticket.topic_thread_id)

        general_thread_id = self.general_topic_id if self.general_topic_id and self.general_topic_id > 0 else None
        if general_thread_id not in target_threads:
            target_threads.append(general_thread_id)

        await self._send_notification_to_threads(notification_text, target_threads)

    async def _notify_ticket_closed_by_admin(self, ticket: Ticket):
        """Информирует сотрудников поддержки о закрытии тикета администратором"""
        notification_text = (
            f"✅ Администратор закрыл тикет #{ticket.display_id}\n"
        )

        target_threads = []
        if ticket.topic_thread_id:
            target_threads.append(ticket.topic_thread_id)

        general_thread_id = self.general_topic_id if self.general_topic_id and self.general_topic_id > 0 else None
        if general_thread_id not in target_threads:
            target_threads.append(general_thread_id)

        await self._send_notification_to_threads(notification_text, target_threads)

    async def _send_notification_to_threads(self, text: str, thread_ids: list[int | None]):
        """Отправляет уведомление в несколько топиков (топик или общий чат)"""
        unique_thread_ids = []
        for thread_id in thread_ids:
            if thread_id not in unique_thread_ids:
                unique_thread_ids.append(thread_id)

        for thread_id in unique_thread_ids:
            try:
                await self.bot.send_message(
                    chat_id=self.support_channel_id,
                    message_thread_id=thread_id,
                    text=text
                )
                thread_label = thread_id if thread_id is not None else "общий чат"
                logger.info(f"Уведомление отправлено в {thread_label}: {text}")
            except Exception as e:
                thread_label = thread_id if thread_id is not None else "общий чат"
                logger.warning(f"Не удалось отправить уведомление в {thread_label}: {e}")

    def _get_topic_link(self, topic_thread_id: int) -> str:
        """Формирует ссылку на топик"""
        chat_id_str = str(self.support_channel_id)
        if chat_id_str.startswith('-100'):
            chat_id_for_link = chat_id_str[4:]
        elif chat_id_str.startswith('-'):
            chat_id_for_link = chat_id_str[1:]
        else:
            chat_id_for_link = chat_id_str

        return f"https://t.me/c/{chat_id_for_link}/{topic_thread_id}"
    
    async def _send_topic_link_to_admin(self, admin_id: int, topic_thread_id: int):
        """Отправляет админу ссылку на созданный топик тикета"""
        try:
            topic_link = self._get_topic_link(topic_thread_id)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔗 Перейти в топик", url=topic_link)
            ]])
            
            await self.bot.send_message(
                chat_id=admin_id,
                text="✅ Тикет взят в работу!",
                reply_markup=keyboard
            )
            logger.info(f"Ссылка на топик отправлена админу {admin_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить ссылку на топик админу {admin_id}: {e}")

    async def update_general_message_by_display_id(self, display_id: int, status: str):
        """Обновляет общее сообщение для тикета по display_id"""
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == display_id).first()
            if not db_ticket or not db_ticket.channel_message_id:
                logger.warning(f"Сообщение канала для тикета {display_id} не найдено")
                return

            cancelled_text = (
                f"🎫 Тикет #{db_ticket.display_id}\n"
                f"👤 Пользователь: @{db_ticket.username}\n"
                f"📝 {db_ticket.user_message}\n\n"
                f"⏰ Создан: {db_ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"📌 Статус: {status}\n\n"
            )

            try:
                await self.bot.edit_message_text(
                    chat_id=self.support_channel_id,
                    message_id=db_ticket.channel_message_id,
                    text=cancelled_text,
                    reply_markup=None
                )
                logger.info(f"Общее сообщение для тикета {display_id} обновлено")
            except Exception as e:
                logger.error(f"Не удалось обновить общее сообщение для тикета {display_id}: {e}")
        finally:
            db.close()

    async def create_ticket_topic_and_thread(self, ticket: Ticket) -> tuple[int, Optional[int]]:
        """Создает только общее сообщение тикета, топик будет создан при взятии тикета админом"""
        channel_message_id = await self.send_ticket_to_general(ticket)
        logger.info(f"Тикет {ticket.id} создан с общим сообщением, ожидание админа")
        return channel_message_id, None

    async def _get_or_create_reviews_topic(self) -> Optional[int]:
        """Получить или создать топик 'отзывы' и вернуть его message_thread_id"""
        if self._reviews_topic_id:
            return self._reviews_topic_id

        
        if not config.REVIEWS_TOPIC_ID:
            try:
                topic = await self.bot.create_forum_topic(
                    chat_id=self.support_channel_id,
                    name="отзывы"
                )
                self._reviews_topic_id = topic.message_thread_id
                logger.info(f"Создан топик 'отзывы' с ID: {self._reviews_topic_id}. Рекомендуется установить REVIEWS_TOPIC_ID={self._reviews_topic_id} в .env")
                return self._reviews_topic_id
            except Exception as e:
                logger.warning(f"Не удалось создать топик 'отзывы': {e}. Используем общий топик.")
                return self.general_topic_id if self.general_topic_id else None
        else:
            logger.info(f"Используем заданный REVIEWS_TOPIC_ID: {config.REVIEWS_TOPIC_ID}")
            self._reviews_topic_id = config.REVIEWS_TOPIC_ID
            return config.REVIEWS_TOPIC_ID

    async def send_rating_to_reviews_topic(self, ticket_display_id: int, username: str, rating: int, comment: Optional[str] = None):
        """Отправить отзыв в топик 'отзывы'"""
        try:
            reviews_topic_id = await self._get_or_create_reviews_topic()
            if not reviews_topic_id:
                logger.warning("Не удалось получить ID топика 'отзывы'")
                return

            from App.Infrastructure.Models.database import get_db
            from App.Infrastructure.Models import Ticket as TicketModelDB
            db = get_db()
            try:
                db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == ticket_display_id).first()
                if not db_ticket:
                    logger.warning(f"Тикет #{ticket_display_id} не найден")
                    return

                stars = "⭐" * rating
                review_text = (
                    f"⭐ <b>Отзыв о тикете #{ticket_display_id}</b>\n"
                    f"👤 <b>Пользователь:</b> @{username}\n"
                    f"⭐ <b>Оценка:</b> {rating}/5 {stars}\n"
                )

                if comment:
                    review_text += f"\n💬 <b>Комментарий:</b>\n{comment}\n"

                category_display = self._get_category_display_name(db_ticket.category) if db_ticket.category else 'Не указана'
                
                review_text += (
                    f"\n📅 <b>Дата:</b> {db_ticket.closed_at.strftime('%d.%m.%Y %H:%M') if db_ticket.closed_at else 'Не указана'}\n"
                    f"📋 <b>Категория:</b> {category_display}"
                )

                await self.bot.send_message(
                    chat_id=self.support_channel_id,
                    message_thread_id=reviews_topic_id,
                    text=review_text,
                    parse_mode="HTML"
                )
                logger.info(f"Отзыв о тикете #{ticket_display_id} отправлен в топик 'отзывы'")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Ошибка отправки отзыва в топик 'отзывы': {e}")
