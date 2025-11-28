import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager

sys.path.append(os.path.join(os.path.dirname(__file__), 'App'))

from App.Infrastructure.Config import config
from App.Infrastructure.Components.TelegramBot.telegram_bot import TelegramBotClient
from App.Infrastructure.Components.TelegramBot.ChannelManager.channel_manager import ChannelManager
from App.Infrastructure.Components.TelegramBot.processors.message_processor import MessageProcessor
from App.Infrastructure.Components.TelegramBot.processors.support_processor import SupportProcessor
from App.Domain.Services.BalanceService.balance_service import BalanceService
from App.Domain.Services.StatisticsService.statistics_service import StatisticsService
from App.Domain.Services.RatingService.rating_service import RatingService
from App.Domain.Services.MessageService.message_service import MessageService
from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.CallbackService.callback_service import CallbackService
from App.Infrastructure.Components.Http.longpoll_manager import LongpollManager
from App.Domain.Services.TicketApplicationService.ticket_application_service import TicketApplicationService
from App.Infrastructure.Components.Http.controllers.ticket_controller import TicketController
from App.Infrastructure.Components.Http.controllers.rating_controller import RatingController
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.UpdateResponse.UpdateResponse import UpdateResponse
from App.Domain.Models.RatingRequest.RatingRequest import RatingRequest
from App.Domain.Models.RatingResponse.RatingResponse import RatingResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse
from fastapi import Query
from App.Infrastructure.Models.database import init_db
from fastapi import FastAPI
import uvicorn

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Глобальные переменные для сервисов
telegram_bot = None
ticket_service = None
rating_service = None
longpoll_manager = None
bot_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global telegram_bot, ticket_service, rating_service, longpoll_manager, bot_task
    
    try:
        logger.info("Инициализация сервисов...")
        
        init_db()
        
        longpoll_manager = LongpollManager()
        logger.info("LongpollManager создан")
        
        telegram_bot = TelegramBotClient()
        logger.info("Бот создан")
        
        channel_manager = ChannelManager(telegram_bot.bot)
        logger.info("ChannelManager создан")
        
        balance_service = BalanceService()
        statistics_service = StatisticsService(telegram_bot.bot)
        rating_service = RatingService()
        ticket_service = TicketService(channel_manager, longpoll_manager)
        logger.info("TicketService создан")
        
        message_service = MessageService(ticket_service, statistics_service, rating_service, balance_service, telegram_bot.bot)
        callback_service = CallbackService(ticket_service, balance_service, statistics_service, rating_service)
        message_processor = MessageProcessor(message_service, callback_service)
        support_processor = SupportProcessor(ticket_service)
        
        telegram_bot.register_router(support_processor.router)
        telegram_bot.register_router(message_processor.router)
        
        ticket_application_service = TicketApplicationService(ticket_service, rating_service, longpoll_manager)
        ticket_controller = TicketController(ticket_application_service)
        rating_controller = RatingController(ticket_application_service)
        
        @app.get(
            "/api/ticket/create",
            response_model=TicketResponse,
            tags=["Тикеты"],
            summary="Создать новый тикет",
            description="Создает новый тикет поддержки для пользователя"
        )
        async def create_ticket(
            user_id: int = Query(..., description="ID пользователя", examples=[{"value": 123456789}]),
            username: str = Query(..., description="Имя пользователя", examples=[{"value": "user123"}]),
            message: str = Query(..., description="Сообщение пользователя", examples=[{"value": "Помогите с проблемой"}]),
            category: str = Query("", description="Категория тикета", examples=[{"value": "technical"}])
        ):
            return await ticket_controller.create_ticket(
                user_id=user_id,
                username=username,
                message=message,
                category=category
            )
        
        @app.get(
            "/api/ticket/{ticket_id}/updates",
            response_model=UpdateResponse,
            tags=["Тикеты"],
            summary="Получить обновления тикета",
            description="Longpoll endpoint для получения обновлений статуса тикета. Ожидает обновление статуса в течение указанного таймаута."
        )
        async def get_ticket_updates(
            ticket_id: int,
            timeout: int = Query(30, ge=1, le=120, description="Таймаут ожидания в секундах", examples=[{"value": 30}])
        ):
            return await ticket_controller.get_ticket_updates(ticket_id, timeout)
        
        @app.post(
            "/api/ticket/{ticket_id}/rating",
            response_model=RatingResponse,
            tags=["Оценки"],
            summary="Отправить оценку тикета",
            description="Отправляет оценку и опциональный комментарий для закрытого тикета"
        )
        async def submit_rating(
            ticket_id: int,
            rating_request: RatingRequest
        ):
            return await rating_controller.submit_rating(ticket_id, rating_request)
        
        @app.get(
            "/api/ticket/{ticket_id}/status",
            response_model=TicketStatusResponse,
            tags=["Тикеты"],
            summary="Получить статус тикета",
            description="Возвращает текущий статус и информацию о тикете"
        )
        async def get_ticket_status(ticket_id: int):
            return await ticket_controller.get_ticket_status(ticket_id)
        
        logger.info("HTTP API endpoints настроены")
        
        bot_task = asyncio.create_task(telegram_bot.start())
        logger.info("Бот запущен в фоновом режиме")
        
        logger.info("Инициализация завершена")
        yield
        
        logger.info("Остановка сервисов...")
        if bot_task:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}", exc_info=True)
        raise


async def main():
    """Основная функция запуска"""
    try:
        logger.info("Запуск Support Bot с REST API...")
        
        api_app = FastAPI(
            lifespan=lifespan,
            title="Support Bot API",
            version="1.0.0",
            description="API для управления тикетами поддержки",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        config_obj = uvicorn.Config(
            api_app,
            host="0.0.0.0",
            port=8000,
            log_level=config.LOG_LEVEL.lower()
        )
        server = uvicorn.Server(config_obj)
        
        logger.info("=" * 60)
        logger.info("API сервер запущен!")
        logger.info("Swagger UI: http://localhost:8000/docs")
        logger.info("ReDoc: http://localhost:8000/redoc")
        logger.info("OpenAPI JSON: http://localhost:8000/openapi.json")
        logger.info("=" * 60)
        
        await server.serve()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}", exc_info=True)
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
