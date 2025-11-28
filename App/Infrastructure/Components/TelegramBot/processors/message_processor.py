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
        self.router.message.register(self._process_text_message, F.chat.type == ChatType.PRIVATE, F.text)
        self.router.message.register(self._process_group_text_message, F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text)
        self.router.message.register(self._process_media_message, F.chat.type == ChatType.PRIVATE, F.photo | F.video | F.sticker | F.document | F.animation | F.voice | F.audio | F.video_note)
        self.router.callback_query.register(self._process_callback)

    async def _process_text_message(self, message: Message, state: FSMContext):
        try:
            text = message.text.strip()

            if text.startswith('/'):
                command = text.split()[0].lower()
                await self.message_service.process_command(message, command, state)
            else:
                await self.message_service.process_text_message(message, text, state)

        except Exception as e:
            logger.error(f"Ошибка обработки текста: {e}")
            await message.answer("Произошла ошибка при обработке сообщения")

    async def _process_media_message(self, message: Message, state: FSMContext):
        try:
            await self.message_service.process_media_message(message, state)
        except Exception as e:
            logger.error(f"Ошибка обработки медиа: {e}")
            await message.answer("Произошла ошибка при обработке медиа-сообщения")

    async def _process_group_text_message(self, message: Message, state: FSMContext):
        try:
            text = message.text.strip()

            if text.startswith('/'):
                command = text.split()[0].lower()
                if command in ['/menu', '/help', '/stat', '/start']:
                    await self.message_service.process_command(message, command, state)
        except Exception as e:
            logger.error(f"Ошибка обработки группового сообщения: {e}")

    async def _process_callback(self, callback: CallbackQuery, state: FSMContext):
        try:
            await self.callback_service.process_callback(callback, state)
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await callback.answer("Произошла ошибка")
