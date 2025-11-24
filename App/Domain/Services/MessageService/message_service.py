import logging
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from App.Domain.Models.TicketStates.ticket_states import TicketStates
from App.Domain.Services.TicketService.ticket_service import TicketService

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self, ticket_service: TicketService):
        self.ticket_service = ticket_service

    async def process_command(self, message: Message, command: str, state: FSMContext):
        if command == '/start':
            await self._handle_start(message, state)
        elif command == '/help':
            await self._handle_help(message)
        elif command == '/support':
            await self._handle_support(message, state)
        elif command == '/close':
            await self._handle_close(message, state)
        else:
            await self._handle_unknown_command(message)

    async def process_text_message(self, message: Message, text: str, state: FSMContext):
        current_state = await state.get_state()

        if current_state == TicketStates.waiting_for_problem.state:
            user_id = message.from_user.id
            username = message.from_user.username or f"user_{user_id}"

            try:
                ticket = await self.ticket_service.create_ticket(user_id, username, text)
                await message.answer(f"✅ Тикет #{ticket.display_id} создан!\nОжидайте ответа от команды поддержки!")
                await state.clear()
            except Exception as e:
                await message.answer("❌ Ошибка при создании тикета")
                logger.error(f"Ошибка создания тикета: {e}", exc_info=True)
        else:
            if await self.ticket_service.has_active_ticket(message.from_user.id):
                await self.ticket_service.forward_user_message(message.from_user.id, text)
            else:
                await message.answer("Напишите /support чтобы создать тикет")

    async def _handle_start(self, message: Message, state: FSMContext):
        await state.clear()
        welcome_text = (
            "👋 Привет, я бот поддержки наших сайтов. Через меня вы можете связаться с администрацией сайта и задать интересующие вас вопросы.\n\n"
            "Чтобы начать, выберите нужный вам вопрос в этом чате, тикет будет создан автоматически.\n\n"
            "⚠️ Иногда мы можем не сразу вам ответить, так как у нас много тикетов и мы стараемся ответить всем как можно быстрее,\n\n"
            "Если вы не нашли ответ на свой вопрос в документации на сайте, пожалуйста, после создания тикета подождите ответа от нашей службы поддержки и не пишите повторно в этот чат,\n\n"
            "⏰ Рабочее время службы поддержки: с 10:00 до 23:00 по MSK (UTC+3)"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="📝 Создать тикет",
                    callback_data="create_ticket"
                )
            ]]
        )

        await message.answer(welcome_text, reply_markup=keyboard)

    async def _handle_help(self, message: Message):
        help_text = (
            "📋 Доступные команды:\n\n"
            "/start - начать работу\n"
            "/support - создать тикет\n"
            "/help - справка\n\n"
            "Или используйте кнопку '📝 Создать тикет'"
        )
        await message.answer(help_text)

    async def _handle_support(self, message: Message, state: FSMContext):
        await self._start_ticket_creation(message, state)

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

    async def _start_ticket_creation(self, message: Message, state: FSMContext):
        user_id = message.from_user.id

        if await self.ticket_service.has_active_ticket(user_id):
            await message.answer("❌ У вас уже есть активный тикет")
            return

        await state.set_state(TicketStates.waiting_for_problem)
        await message.answer("📝 Опишите вашу проблему:")
