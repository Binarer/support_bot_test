import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from App.Domain.Services.MessageService.message_service import MessageService
from App.Domain.Services.CallbackService.callback_service import CallbackService

logger = logging.getLogger(__name__)


class MessageProcessor:
    def __init__(self, message_service: MessageService, callback_service: CallbackService):
        self.router = Router()
        self.message_service = message_service
        self.callback_service = callback_service
        self._setup_handlers()

    def _setup_handlers(self):
        self.router.message.register(self._process_message, F.chat.type == ChatType.PRIVATE, F.text)
        self.router.callback_query.register(self._process_callback)

    async def _process_message(self, message: Message, state: FSMContext):
        try:
            text = message.text.strip()

            if text.startswith('/'):
                command = text.split()[0].lower()
                await self.message_service.process_command(message, command, state)
            else:
                await self.message_service.process_text_message(message, text, state)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            await message.answer("Произошла ошибка при обработке сообщения")

    async def _process_callback(self, callback: CallbackQuery, state: FSMContext):
        try:
            await self.callback_service.process_callback(callback, state)
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await callback.answer("Произошла ошибка")
