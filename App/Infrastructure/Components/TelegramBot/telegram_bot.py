import logging
from typing import Optional
from aiogram import Bot, Dispatcher

from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)


class TelegramBotClient:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._initialize_bot()

    def _initialize_bot(self):
        try:
            self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            self.dp = Dispatcher()
            logger.info("Telegram бот инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Telegram бота: {e}")
            raise

    def register_router(self, router):
        self.dp.include_router(router)
        logger.info(f"Роутер зарегистрирован")

    async def start(self):
        try:
            logger.info("Запуск поллинга Telegram бота...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Ошибка в работе Telegram бота: {e}")
            raise

    async def stop(self):
        try:
            if self.bot:
                await self.bot.session.close()
            logger.info("Telegram бот остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке Telegram бота: {e}")