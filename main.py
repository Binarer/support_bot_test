import asyncio
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'App'))

from App.Infrastructure.Config import config
from App.Infrastructure.Components.TelegramBot.telegram_bot import TelegramBotClient
from App.Infrastructure.Components.TelegramBot.ChannelManager.channel_manager import ChannelManager
from App.Infrastructure.Components.TelegramBot.processors.message_processor import MessageProcessor
from App.Infrastructure.Components.TelegramBot.processors.support_processor import SupportProcessor
from App.Domain.Services.MessageService.message_service import MessageService
from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.CallbackService.callback_service import CallbackService

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    try:
        logger.info("Запуск Support Bot...")

        # Инициализация бота
        telegram_bot = TelegramBotClient()
        logger.info("Бот создан")

        # Инициализация менеджера каналов
        channel_manager = ChannelManager(telegram_bot.bot)
        logger.info("ChannelManager создан")

        # Инициализация сервисов
        ticket_service = TicketService(channel_manager)
        logger.info("TicketService создан")

        message_service = MessageService(ticket_service)
        logger.info("MessageService создан")

        callback_service = CallbackService(ticket_service)
        logger.info("CallbackService создан")

        # Создание процессоров
        message_processor = MessageProcessor(message_service, callback_service)
        support_processor = SupportProcessor(ticket_service)

        # Регистрация процессоров
        telegram_bot.register_router(message_processor.router)
        telegram_bot.register_router(support_processor.router)

        logger.info("Все компоненты инициализированы. Запускаем бота...")
        await telegram_bot.start()

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)


async def shutdown():
    logger.info("Завершение работы бота...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
    finally:
        asyncio.run(shutdown())