import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
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

    async def _process_support_message(self, message: Message, state: FSMContext):
        try:
            user_id = message.from_user.id

            # Проверяем, находится ли пользователь в состоянии переименования
            state_data = await state.get_data()
            rename_ticket_id = state_data.get('rename_ticket_id')
            rename_admin_id = state_data.get('rename_admin_id')

            if rename_ticket_id is not None:
                # Проверяем, что пользователь администратор
                if not self._is_admin(user_id):
                    await message.answer("❌ Только администраторы могут переименовывать тикеты")
                    return

                # Проверяем, что это тот же администратор, который запросил переименование
                if rename_admin_id is not None and user_id != rename_admin_id:
                    await message.answer("❌ Вы не можете переименовать этот тикет, так как запросили это не вы")
                    return

                # Если пользователь в состоянии переименования, обрабатываем как ответ на переименование
                if not message.text or message.text.strip() == "":
                    await message.answer("❌ Название не может быть пустым")
                    return

                success = await self.ticket_service.rename_ticket(rename_ticket_id, message.text.strip())
                if success:
                    await message.answer(f"✅ Тикет #{rename_ticket_id} переименован на: {message.text.strip()}")
                else:
                    await message.answer("❌ Не удалось переименовать тикет")

                await state.clear()
                return

            thread_id = message.message_thread_id

            ticket = self.ticket_service.get_ticket_by_thread_id(thread_id)

            if not ticket:
                logger.warning(f"Тикет для thread_id {thread_id} не найден")
                return

            await self.ticket_service.process_support_topic_message(thread_id, message)

            logger.info(f"Обработано сообщение поддержки для тикета {ticket.id}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения поддержки: {e}")

    def _is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        from App.Infrastructure.Config import config
        return user_id in config.TELEGRAM_ADMIN_IDS
