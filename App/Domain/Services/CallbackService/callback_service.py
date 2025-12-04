import logging
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from App.Domain.Models.TicketStates.ticket_states import TicketStates
from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.BalanceService.balance_service import BalanceService
from App.Domain.Services.StatisticsService.statistics_service import StatisticsService
from App.Domain.Services.RatingService.rating_service import RatingService

logger = logging.getLogger(__name__)


class CallbackService:
    def __init__(self, ticket_service: TicketService, balance_service: BalanceService, statistics_service: StatisticsService, rating_service: RatingService):
        self.ticket_service = ticket_service
        self.balance_service = balance_service
        self.statistics_service = statistics_service
        self.rating_service = rating_service

    async def process_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        callback_data = callback.data

        logger.info(f"Обработка callback от пользователя {user_id}: {callback_data}")

        if callback_data == "create_ticket":
            await self._handle_create_ticket_callback(callback, state)
        elif callback_data == "create_support_request":
            await self._handle_create_support_request_callback(callback, state)
        elif callback_data.startswith("take:"):
            await self._handle_take_ticket_callback(callback)
        elif callback_data.startswith("cancel_ticket"):
            await self._handle_cancel_ticket_callback(callback)
        elif callback_data.startswith("close_"):
            await self._handle_close_ticket_callback(callback)
        elif callback_data.startswith("rename_"):
            await self._handle_rename_ticket_callback(callback, state)
        elif callback_data.startswith("cat:"):
            await self._handle_category_selection_callback(callback, state)
        elif callback_data == "show_stats":
            await self._handle_show_stats_callback(callback)
        elif callback_data == "show_balance":
            await self._handle_show_balance_callback(callback)
        elif callback_data == "show_help_memo":
            await self._handle_show_help_memo_callback(callback)
        elif callback_data == "show_top_stats":
            await self._handle_show_top_stats_callback(callback)
        elif callback_data == "back_menu":
            await self._handle_back_menu_callback(callback)
        elif callback_data.startswith("rate:"):
            await self._handle_rate_callback(callback)
        elif callback_data.startswith("rate_comment:"):
            await self._handle_rate_comment_callback(callback, state)
        elif callback_data == "skip_comment":
            await self._handle_skip_comment_callback(callback, state)
        else:
            await callback.answer("Неизвестное действие")

    async def _handle_take_ticket_callback(self, callback: CallbackQuery):
        user_id = callback.from_user.id
        admin_name = callback.from_user.full_name or callback.from_user.username or f"user_{user_id}"

        try:
            ticket_number = int(callback.data.split(":")[1])
        except (IndexError, ValueError):
            await callback.answer("Неверный формат номера тикета", show_alert=True)
            return

        ticket = await self.ticket_service.take_ticket(user_id, admin_name, ticket_number)
        if ticket:
            await callback.answer(f"Тикет #{ticket_number} принят в работу ✅")
        else:
            await callback.answer("Тикет не найден или уже взят", show_alert=True)

        try:
            status_text = "🔧 В работе" if ticket else "🔧 В работе"
            await self.ticket_service.channel_manager.update_general_message_by_display_id(ticket_number, status_text)
        except Exception as e:
            logger.warning(f"Не удалось обновить общее сообщение для тикета {ticket_number}: {e}")

    async def _handle_cancel_ticket_callback(self, callback: CallbackQuery):
        try:
            ticket_number = int(callback.data.split(":")[1])  
        except (IndexError, ValueError):
            await callback.answer("Неверный формат номера тикета", show_alert=True)
            return

        is_admin_cancel = callback.message.chat.type in ['group', 'supergroup']

        success = await self.ticket_service.cancel_ticket(ticket_number, cancelled_by_admin=is_admin_cancel)
        if success:
            await callback.answer(f"Тикет #{ticket_number} отменен ✅")
        else:
            await callback.answer("Тикет не найден", show_alert=True)

        try:
            status_text = "Отменен" if success else "Отменен"
            await self.ticket_service.channel_manager.update_general_message_by_display_id(ticket_number, status_text)
        except Exception as e:
            logger.warning(f"Не удалось обновить общее сообщение для тикета {ticket_number}: {e}")

    async def _ask_for_rating(self, user_id: int, ticket_number: int):
        """Запрос оценки от пользователя"""
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="1⭐", callback_data=f"rate:{ticket_number}:1"),
                        InlineKeyboardButton(text="2⭐", callback_data=f"rate:{ticket_number}:2"),
                        InlineKeyboardButton(text="3⭐", callback_data=f"rate:{ticket_number}:3"),
                        InlineKeyboardButton(text="4⭐", callback_data=f"rate:{ticket_number}:4"),
                        InlineKeyboardButton(text="5⭐", callback_data=f"rate:{ticket_number}:5"),
                    ]
                ]
            )

            await self.ticket_service.channel_manager.bot.send_message(
                user_id,
                "Пожалуйста, оцените работу поддержки:",
                reply_markup=keyboard
            )
            logger.info(f"Отправлен запрос оценки для тикета #{ticket_display_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса оценки: {e}")

    async def _handle_close_ticket_callback(self, callback: CallbackQuery):
        logger.info(f"Обработка закрытия тикета от пользователя {callback.from_user.id}: {callback.data}")
        admin_id = callback.from_user.id
        admin_name = callback.from_user.full_name or callback.from_user.username or f"user_{admin_id}"

        try:
            if callback.data.startswith("close_"):
                parts = callback.data.split("_")
                if len(parts) == 3 and parts[1] == "ticket":
                    ticket_db_id = int(parts[2])
                elif len(parts) == 2:
                    ticket_db_id = int(parts[1])
                else:
                    raise ValueError(f"Неожиданный формат: {callback.data}")
                logger.info(f"Распознан ticket_db_id: {ticket_db_id}")
            else:
                raise ValueError(f"Неверный формат callback данных: {callback.data}")
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка парсинга тикета из {callback.data}: {e}")
            await callback.answer("Неверный формат номера тикета", show_alert=True)
            return

        success = await self.ticket_service.close_ticket_by_internal_id(ticket_db_id, admin_id)
        if success:
            # Получаем категорию тикета для проверки
            from App.Infrastructure.Models.database import get_db
            from App.Infrastructure.Models import Ticket as TicketModelDB
            db = get_db()
            try:
                ticket_record = db.query(TicketModelDB).filter(TicketModelDB.id == ticket_db_id).first()
                ticket_category = ticket_record.category if ticket_record else None
            finally:
                db.close()

            # Баланс не начисляется за категории "Сбросить HWID" и "Получить ключ"
            excluded_categories = ["hwid", "key"]
            if ticket_category in excluded_categories:
                amount = 0.0
                new_balance = self.balance_service.get_admin_balance(admin_id)
                message_text = f"Тикет закрыт ✅\nБаланс не начисляется за данную категорию\nБаланс: {new_balance:.2f} ₽"
            else:
                amount = 50.0
                new_balance = self.balance_service.add_balance(admin_id, amount)
                message_text = f"Тикет закрыт ✅\nНачислено: {amount} ₽\nБаланс: {new_balance} ₽"

            await callback.answer(message_text)

            from App.Infrastructure.Models.database import get_db
            from App.Infrastructure.Models import Ticket as TicketModelDB
            from App.Domain.Models.Ticket.Ticket import Ticket
            db = get_db()
            try:
                ticket_record = db.query(TicketModelDB).filter(TicketModelDB.id == ticket_db_id).first()
                if ticket_record:
                    await self._ask_for_rating(ticket_record.user_id, ticket_record.display_id)

                    if ticket_record.channel_message_id:
                        status_text = "✅ Закрыт администратором"
                        try:
                            await self.ticket_service.channel_manager.bot.edit_message_text(
                                chat_id=self.ticket_service.channel_manager.support_channel_id,
                                message_id=ticket_record.channel_message_id,
                                text=self.ticket_service.channel_manager._get_ticket_closed_text(ticket_record),
                                reply_markup=None
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось обновить общее сообщение для закрытого тикета: {e}")
                else:
                    logger.warning(f"Не удалось найти тикет {ticket_db_id} для запроса оценки")
            finally:
                db.close()
        else:
            await callback.answer("Тикет не найден", show_alert=True)

    async def _handle_rename_ticket_callback(self, callback: CallbackQuery, state: FSMContext):
        try:
            ticket_number = int(callback.data.split("_")[1])
        except (IndexError, ValueError):
            await callback.answer("Неверный формат номера тикета", show_alert=True)
            return

        # Найдем тикет (ticket_number может быть как display_id так и db_id)
        ticket = self.ticket_service.get_ticket_by_display_id(ticket_number)
        if not ticket:
            # Попробуем найти по db_id если не нашли по display_id
            ticket = self.ticket_service.get_ticket_by_db_id(ticket_number)
            if not ticket:
                await callback.answer("Тикет не найден", show_alert=True)
                return

        ticket_db_id = ticket.db_id

        await state.update_data(rename_ticket_id=ticket_db_id, rename_admin_id=callback.from_user.id)
        await callback.answer()
        await callback.message.answer("✏️ Напишите новое название для темы тикета:")

    async def _handle_category_selection_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        category_code = callback.data.split(":")[1]

        if await self.ticket_service.has_active_ticket(user_id):
            await callback.answer("У вас уже есть активный тикет", show_alert=True)
            return

        category_display = self._get_category_display_name(category_code)
        username = callback.from_user.username or f"user_{user_id}"
        user_message = f"Категория: {category_display}"

        try:
            ticket = await self.ticket_service.create_ticket(user_id, username, user_message, category_code)
            await callback.answer()
            user_message_id = await self.ticket_service.channel_manager.send_user_ticket_message(ticket)
            if user_message_id:
                from App.Infrastructure.Models.database import get_db
                from App.Infrastructure.Models import Ticket as TicketModelDB
                db = get_db()
                try:
                    db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == ticket.display_id).first()
                    if db_ticket:
                        db_ticket.user_message_id = user_message_id
                        db.commit()
                finally:
                    db.close()
        except Exception as e:
            await callback.answer("Ошибка при создании тикета", show_alert=True)
            logger.error(f"Ошибка создания тикета: {e}")

    def _get_category_display_name(self, category_callback: str) -> str:
        """Преобразует callback категории в отображаемое имя из bot.json"""
        from App.Infrastructure.Config import config
        user_categories = config.bot_keyboards.get('user_categories', [])
        for category in user_categories:
            callback_data = category.get('callback_data', '')
            if callback_data == f"cat:{category_callback}" or callback_data.endswith(f":{category_callback}"):
                return category.get('text', category_callback)
        return category_callback

    async def _handle_show_stats_callback(self, callback: CallbackQuery):
        await callback.answer()
        admin_id = callback.from_user.id

        try:
            stats_text = await self.statistics_service.generate_stats_text(admin_id)

            await callback.message.edit_text(
                text=stats_text,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back_menu"}]]}
            )
        except Exception as e:
            logger.warning(f"Не удалось сгенерировать статистику: {e}")
            await callback.message.edit_text(
                text="❌ Ошибка загрузки статистики",
                reply_markup={"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back_menu"}]]}
            )

    async def _handle_show_balance_callback(self, callback: CallbackQuery):
        await callback.answer()
        admin_id = callback.from_user.id

        balance = self.balance_service.get_admin_balance(admin_id)
        text = f"💰 Ваш баланс: <b>{balance:.2f}</b> ₽"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup={"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back_menu"}]]}
        )

    async def _handle_show_help_memo_callback(self, callback: CallbackQuery):
        await callback.answer()
        help_text = "📖 <b>Памятка по работе с ботом поддержки</b>\n\n"
        help_text += "🤖 <b>Основные команды:</b>\n"
        help_text += "• /start - начать работу с ботом\n"
        help_text += "• /menu - открыть меню (только для админов)\n"
        help_text += "• /stat @username - статистика пользователя\n"
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

        await callback.message.edit_text(help_text, parse_mode="HTML", reply_markup={"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back_menu"}]]})



    async def _handle_back_menu_callback(self, callback: CallbackQuery):
        await callback.answer()

        from datetime import datetime
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = "Доброе утро ☀️"
        elif 12 <= hour < 18:
            greeting = "Добрый день 🌤"
        else:
            greeting = "Добрый вечер 🌙"

        active_tickets = self.statistics_service.get_active_tickets_count(admin_id=callback.from_user.id)
        balance = self.balance_service.get_admin_balance(callback.from_user.id) if self.balance_service else 0.0

        text = f"{greeting}, {callback.from_user.full_name}!\n\n"
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

        if callback.message.photo:
            try:
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить фото-сообщение: {e}")
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    async def _handle_show_top_stats_callback(self, callback: CallbackQuery):
        await callback.answer()

        image_data = await self.statistics_service.generate_top_stats_image()
        image_file = BufferedInputFile(image_data, filename="top_stats.png")
        await callback.message.answer_photo(
            photo=image_file,
            caption="📊 Топ статистика поддержки",
            reply_markup={"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "back_menu"}]]}
        )

    async def _handle_rate_callback(self, callback: CallbackQuery):
        await callback.answer()
        parts = callback.data.split(':')
        if len(parts) == 3:
            try:
                ticket_number = int(parts[1])
                rating = int(parts[2])
            except ValueError:
                await callback.answer("Ошибка обработки оценки", show_alert=True)
                return

            user_id = callback.from_user.id

            success = self.rating_service.save_ticket_rating(ticket_number, user_id, rating)

            if success:
                await callback.message.edit_text(f"✅ Спасибо за вашу оценку: {rating} ⭐\nВаш отзыв поможет нам стать лучше!")
                reply_markup = {
                    "inline_keyboard": [[
                        {"text": "Добавить комментарий", "callback_data": f"rate_comment:{ticket_number}"},
                        {"text": "Пропустить", "callback_data": "skip_comment"}
                    ]]
                }
                await callback.message.answer("Хотите добавить комментарий к оценке?", reply_markup=reply_markup)
            else:
                await callback.answer("Ошибка сохранения оценки", show_alert=True)
        else:
            await callback.answer("Ошибка обработки оценки", show_alert=True)

    async def _handle_rate_comment_callback(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer()
        parts = callback.data.split(":")
        if len(parts) == 2:
            ticket_number = int(parts[1])
        else:
            await callback.answer("Ошибка", show_alert=True)
            return

        await state.update_data(rating_ticket=ticket_number)
        await state.set_state(TicketStates.waiting_for_rating_comment)

        await callback.message.answer("Пожалуйста, напишите ваш комментарий к оценке или /skip чтобы пропустить.")

    async def _handle_skip_comment_callback(self, callback: CallbackQuery, state: FSMContext):
        try:
            state_data = await state.get_data()
            ticket_number = state_data.get("rating_ticket")
            user_id = callback.from_user.id
            
            if ticket_number:
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
                        
                        if rating_record:
                            username = callback.from_user.username or callback.from_user.first_name or f"user_{user_id}"
                            await self.ticket_service.channel_manager.send_rating_to_reviews_topic(
                                ticket_number,
                                username,
                                rating_record.rating,
                                None
                            )
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"Не удалось отправить отзыв в топик при пропуске комментария: {e}")
        
        await callback.answer("Комментарий пропущен. Спасибо!")
        await state.clear()

    async def _handle_create_support_request_callback(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer()
        from App.Infrastructure.Config import config

        welcome_text = config.bot_messages.get('user_start', 'Welcome message')
        user_categories_keyboard = config.bot_keyboards.get('user_categories', [])

        try:
            if welcome_text:
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=welcome_text,
                    parse_mode="HTML"
                )

            if user_categories_keyboard:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[user_categories_keyboard])
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text="Выберите категорию:",
                    reply_markup=keyboard
                )
            else:
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text="Категории не доступны"
                )
        except Exception as e:
            await callback.message.answer("❌ Ошибка при создании обращения")
            logger.error(f"Ошибка создания обращения администратора: {e}")

    async def _handle_create_ticket_callback(self, callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id

        if await self.ticket_service.has_active_ticket(user_id):
            await callback.answer("У вас уже есть активный тикет", show_alert=True)
            return

        await state.set_state(TicketStates.waiting_for_problem)
        await callback.answer()
        await callback.message.answer("📝 Опишите вашу проблему:")
