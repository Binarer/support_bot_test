import logging
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from App.Domain.Models.TicketStates.ticket_states import TicketStates
from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.StatisticsService.statistics_service import StatisticsService
from App.Domain.Services.RatingService.rating_service import RatingService
from App.Domain.Services.BalanceService.balance_service import BalanceService
from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self, ticket_service: TicketService, statistics_service: StatisticsService, rating_service: RatingService = None, balance_service: BalanceService = None, bot=None):
        self.ticket_service = ticket_service
        self.statistics_service = statistics_service
        self.rating_service = rating_service
        self.balance_service = balance_service
        self.bot = bot

    async def process_command(self, message: Message, command: str, state: FSMContext):
        if command == '/start':
            await self._handle_start(message, state)
        elif command == '/menu':
            await self._handle_menu(message)
        elif command.startswith('/stat'):
            await self._handle_stat(message, command)
        elif command == '/help':
            await self._handle_help(message)
        elif command == '/close':
            await self._handle_close(message, state)
        elif command == '/balance':
            await self._handle_balance(message)
        else:
            await self._handle_unknown_command(message)

    async def process_text_message(self, message: Message, text: str, state: FSMContext):
        current_state = await state.get_state()
        user_id = message.from_user.id

        state_data = await state.get_data()
        rename_ticket_id = state_data.get('rename_ticket_id')

        if rename_ticket_id is not None:
            try:
                if text.strip() == "":
                    await message.answer("❌ Название не может быть пустым")
                    return

                success = await self.ticket_service.rename_ticket(rename_ticket_id, text.strip())
                if success:
                    await message.answer(f"✅ Тикет 
                else:
                    await message.answer("❌ Не удалось переименовать тикет")

                await state.clear()
            except Exception as e:
                await message.answer("❌ Ошибка при переименовании тикета")
                logger.error(f"Ошибка переименования тикета {rename_ticket_id}: {e}")
        elif current_state == TicketStates.waiting_for_rating_comment:
            state_data = await state.get_data()
            ticket_number = state_data.get("rating_ticket")
            if ticket_number and self.rating_service:
                self.rating_service.save_ticket_comment(ticket_number, user_id, text)
                
                try:
                    from App.Infrastructure.Models.database import get_db
                    from App.Infrastructure.Models import Ticket as TicketModelDB, TicketRating
                    db = get_db()
                    try:
                        db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == ticket_number).first()
                        if db_ticket:
                            rating_record = db.query(TicketRating).filter(
                                TicketRating.ticket_id == db_ticket.id,
                                TicketRating.user_id == user_id
                            ).first()
                            
                            if rating_record and self.ticket_service:
                                username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
                                await self.ticket_service.channel_manager.send_rating_to_reviews_topic(
                                    ticket_number,
                                    username,
                                    rating_record.rating,
                                    text
                                )
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"Не удалось отправить отзыв в топик: {e}")
            
            await message.answer("Комментарий добавлен. Спасибо!")
            await state.clear()
        else:
            if await self.ticket_service.has_active_ticket(user_id):
                success = await self.ticket_service.forward_user_message(user_id, text)
                if not success:
                    await self.ticket_service.forward_user_pre_take_message(user_id, text)
            else:
                await message.answer("Ожидайте принятия вашего запроса администрацией. После того, как заявка будет принята, вы сможете описать вашу проблему.")

    async def process_media_message(self, message: Message, state: FSMContext):
        user_id = message.from_user.id

        if await self.ticket_service.has_active_ticket(user_id):
            try:
                await self.ticket_service.forward_user_media(user_id, message)
            except Exception as e:
                await message.answer("❌ Ошибка при отправке медиа-сообщения")
                logger.error(f"Ошибка отправки медиа пользователя {user_id}: {e}")
        else:
            await message.answer("Можно отправлять медиа только после того, как тикет возьмут в работу.")

    async def _handle_start(self, message: Message, state: FSMContext):
        await state.clear()

        is_admin = self._is_admin(message.from_user.id)
        is_in_group = message.chat.type in ("group", "supergroup")

        if is_admin:
            if message.chat.type == "private":
                text = "Привет! 👋\n\n"
                text += "Как администратор поддержки, вы можете:\n\n"
                text += "📊 Посмотреть свою статистику работы\n"
                text += "🎫 Создать обращение в поддержку (если нужна помощь)\n\n"
                text += "Выберите действие:"

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
                        InlineKeyboardButton(text="🎫 Создать обращение", callback_data="create_support_request")
                    ]
                ])

                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                from datetime import datetime
                hour = datetime.now().hour
                if 5 <= hour < 12:
                    greeting = "Доброе утро ☀️"
                elif 12 <= hour < 18:
                    greeting = "Добрый день 🌤"
                else:
                    greeting = "Добрый вечер 🌙"

                active_tickets = self.statistics_service.get_active_tickets_count(admin_id=message.from_user.id)

                text = f"{greeting}, {message.from_user.full_name}!\n\nУ вас <b>{active_tickets}</b> тикета(ов) в работе."

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
                        InlineKeyboardButton(text="💰 Баланс", callback_data="show_balance")
                    ]
                ])

                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
                logger.info(f"Отправлено меню админа пользователю {message.from_user.id}")
        else:
            welcome_text = config.bot_messages.get('user_start', 'Welcome message')

            user_categories = config.bot_keyboards.get('user_categories', [])
            keyboard_rows = [user_categories[i:i+2] for i in range(0, len(user_categories), 2)]
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

    def _is_admin(self, user_id: int) -> bool:
        from App.Infrastructure.Config import config
        return user_id in config.TELEGRAM_ADMIN_IDS

    async def _handle_menu(self, message: Message):
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ Только администраторы могут использовать эту команду.")
            return

        is_general_topic = message.chat.type in ("group", "supergroup") and (
            getattr(message, 'message_thread_id', None) is None or
            message.message_thread_id == message.chat.id
        )

        from datetime import datetime
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = "Доброе утро ☀️"
        elif 12 <= hour < 18:
            greeting = "Добрый день 🌤"
        else:
            greeting = "Добрый вечер 🌙"

        active_tickets = self.statistics_service.get_active_tickets_count(admin_id=message.from_user.id)
        balance = self.balance_service.get_admin_balance(message.from_user.id) if self.balance_service else 0.0

        text = f"{greeting}, {message.from_user.full_name}!\n\n"
        text += f"🎫 Активных тикетов: <b>{active_tickets}</b>\n"
        text += f"💰 Баланс: <b>{balance:.2f} ₽</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
                InlineKeyboardButton(text="💰 Подробный баланс", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton(text="📖 Памятка", callback_data="show_help_memo"),
                InlineKeyboardButton(text="🏆 Топ статистика", callback_data="show_top_stats")
            ]
        ])

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    async def _handle_help(self, message: Message):
        if self._is_admin(message.from_user.id):
            help_text = "📖 <b>Памятка по работе с ботом поддержки</b>\n\n"
            help_text += "🤖 <b>Основные команды:</b>\n"
            help_text += "• /start - начать работу с ботом\n"
            help_text += "• /menu - открыть меню (только для админов)\n"
            help_text += "• /stat - посмотреть свою статистику\n"
            help_text += "• /stat @username - статистика другого администратора\n"
            help_text += "• /help - показать эту справку\n\n"
            help_text += "👥 <b>Для пользователей:</b>\n"
            help_text += "• Выберите категорию проблемы\n"
            help_text += "• Опишите проблему подробно\n"
            help_text += "• Прикрепите скриншоты/видео при необходимости\n"
            help_text += "• Оцените работу поддержки после закрытия тикета\n\n"
            help_text += "👨‍💼 <b>Для администраторов:</b>\n"
            help_text += "• Используйте /menu в общем топике для доступа к функциям\n"
            help_text += "• Просматривайте статистику работы\n"
            help_text += "• Управляйте балансом и активными тикетами\n\n"
            help_text += "⚡ <b>Правила работы:</b>\n"
            help_text += "• Отвечайте на сообщения пользователей вежливо\n"
            help_text += "• Закрывайте тикеты после решения проблемы\n"
            help_text += "• Запрашивайте обратную связь от пользователей"
        else:
            help_text = config.bot_messages.get('help', 'Help message not available')
        await message.answer(help_text, parse_mode="HTML")

    async def _handle_stat(self, message: Message, command: str):
        """Обработчик команды /stat [ @username ]"""
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ Только администраторы могут использовать эту команду.")
            return

        parts = command.split()
        target_admin_id = message.from_user.id

        if len(parts) >= 2:
            username = parts[1].strip('@')
            if not username:
                await message.answer("❌ Укажите имя пользователя: /stat @username")
                return

            try:
                from App.Infrastructure.Config import config
                admins = await self.bot.get_chat_administrators(config.SUPPORT_CHANNEL_ID)
                for admin in admins:
                    admin_username = admin.user.username
                    if admin_username and admin_username.lower() == username.lower():
                        target_admin_id = admin.user.id
                        break
                else:
                    await message.answer(f"❌ Администратор @{username} не найден в канале поддержки")
                    return
            except Exception as e:
                await message.answer("❌ Ошибка получения списка администраторов")
                logger.error(f"Ошибка получения администраторов канала: {e}")
                return

        try:
            stats_text = await self.statistics_service.generate_stats_text(target_admin_id)
            await message.answer(stats_text, parse_mode="HTML")
        except Exception as e:
            await message.answer("❌ Ошибка при получении статистики")
            logger.error(f"Ошибка генерации статистики для admin_id {target_admin_id}: {e}")

    async def _handle_balance(self, message: Message):
        """Обработчик команды /balance"""
        if not self._is_admin(message.from_user.id):
            await message.answer("❌ Только администраторы могут использовать эту команду.")
            return

        if not self.balance_service:
            await message.answer("❌ Сервис баланса недоступен")
            return

        admin_id = message.from_user.id
        balance = self.balance_service.get_admin_balance(admin_id)
        await message.answer(f"💰 Ваш баланс: <b>{balance:.2f}</b> ₽", parse_mode="HTML")

    async def _handle_close(self, message: Message, state: FSMContext):
        user_id = message.from_user.id

        if not await self.ticket_service.has_active_ticket(user_id):
            await message.answer("❌ У вас нет активных тикетов")
            return

        try:
            await self.ticket_service.close_ticket_by_user(user_id)
            await message.answer("✅ Ваш тикет закрыт!")
        except Exception as e:
            await message.answer("❌ Ошибка при закрытии тикета")
            logger.error(f"Ошибка закрытия тикета пользователем {user_id}: {e}")

    async def _handle_unknown_command(self, message: Message):
        await message.answer("Неизвестная команда. Используйте /help")
