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
from App.Infrastructure.Components.Http.websocket_manager import WebSocketManager
from App.Domain.Services.TicketApplicationService.ticket_application_service import TicketApplicationService
from App.Infrastructure.Components.Http.controllers.ticket_controller import TicketController
from App.Infrastructure.Components.Http.controllers.rating_controller import RatingController
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.RatingRequest.RatingRequest import RatingRequest
from App.Domain.Models.RatingResponse.RatingResponse import RatingResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse
from App.Domain.Models.MessageRequest.MessageRequest import MessageRequest
from App.Domain.Models.MessageResponse.MessageResponse import MessageResponse
from App.Domain.Models.CreateTicketRequest.CreateTicketRequest import CreateTicketRequest
from App.Domain.Models.UpdateResponse.UpdateResponse import UpdateResponse
from fastapi import Query, Path, WebSocket
from App.Infrastructure.Models.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('./logs/bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


telegram_bot = None
ticket_service = None
rating_service = None
longpoll_manager = None
bot_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global telegram_bot, ticket_service, rating_service, websocket_manager, bot_task
    
    try:
        logger.info("Инициализация сервисов...")
        
        init_db()
        
        telegram_bot = TelegramBotClient()
        logger.info("Бот создан")

        channel_manager = ChannelManager(telegram_bot.bot)
        logger.info("ChannelManager создан")

        websocket_manager = WebSocketManager(channel_manager)
        logger.info("WebSocketManager создан")
        
        balance_service = BalanceService()
        statistics_service = StatisticsService(telegram_bot.bot)
        rating_service = RatingService()
        ticket_service = TicketService(channel_manager, websocket_manager)
        logger.info("TicketService создан")
        
        message_service = MessageService(ticket_service, statistics_service, rating_service, balance_service, telegram_bot.bot)
        callback_service = CallbackService(ticket_service, balance_service, statistics_service, rating_service)
        message_processor = MessageProcessor(message_service, callback_service)
        support_processor = SupportProcessor(ticket_service)
        
        telegram_bot.register_router(support_processor.router)
        telegram_bot.register_router(message_processor.router)
        
        ticket_application_service = TicketApplicationService(ticket_service, rating_service)
        ticket_controller = TicketController(ticket_application_service)
        rating_controller = RatingController(ticket_application_service)
        
        @app.post(
            "/api/ticket/create",
            response_model=TicketResponse,
            tags=["Тикеты"],
            summary="Создать новый тикет",
            description="Создает новый тикет поддержки для пользователя"
        )
        async def create_ticket(
            ticket_request: CreateTicketRequest
        ):
            return await ticket_controller.create_ticket(
                user_id=ticket_request.user_id,
                username=ticket_request.username,
                message=ticket_request.message,
                category=ticket_request.category
            )
        
        @app.post(
            "/api/ticket/{ticket_id}/message",
            response_model=MessageResponse,
            tags=["Тикеты"],
            summary="Отправить сообщение в тикет",
            description="""
            Отправляет сообщение от пользователя в существующий тикет поддержки.

            **Поддерживаемые типы:**
            - Текстовые сообщения
            - Медиа файлы (фото, видео, документы)

            **Способы отправки медиа:**
            1. **По URL:** Укажите media_url с прямой ссылкой на файл
            2. **Прямая загрузка:** Используйте media_data с base64 encoded данными

            **Для медиа файлов:**
            - Обязательно укажите media_type: "photo", "video", или "document"
            - Для base64: добавьте media_data и filename
            - Для URL: добавьте media_url (filename опционально)
            - Опционально: media_caption для подписи

            **Примеры использования:**
            ```json
            // Текстовое сообщение
            {
              "message": "У меня проблема с..."
            }

            // Медиа по URL
            {
              "message": "Вот скриншот проблемы",
              "media_type": "photo",
              "media_url": "https://example.com/screenshot.jpg",
              "media_caption": "Скриншот ошибки"
            }

            // Прямая загрузка фото (base64)
            {
              "message": "Скриншот прикреплен",
              "media_type": "photo",
              "media_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
              "filename": "error_screenshot.jpg",
              "media_caption": "Главная страница с ошибкой"
            }

            // Прямая загрузка видео
            {
              "message": "Видео с демонстрацией ошибки",
              "media_type": "video",
              "media_data": "AAAFB...base64_encoded_video_data...",
              "filename": "error_demo.mp4",
              "media_caption": "Видео не запускается"
            }
            ```
            """
        )
        async def send_message_to_ticket(
            ticket_id: int = Path(..., description="ID тикета", examples=[1]),
            message_request: MessageRequest = ...
        ):
            return await ticket_controller.send_message_to_ticket(ticket_id, message_request)
        
        @app.websocket("/ws/ticket/{ticket_id}")
        async def websocket_ticket_updates(
            websocket: WebSocket,
            ticket_id: int = Path(..., description="ID тикета для подключения", examples=[1])
        ):
            """
            WebSocket endpoint для общения в реальном времени с тикетом поддержки.

            **Подключение:**
            1. Подключитесь к ws://localhost:8000/ws/ticket/{ticket_id}
            2. Отправьте сообщение типа 'subscribe' с user_id и ticket_id
            3. После подтверждения можно отправлять сообщения

            **Исходящие сообщения (вы получаете):**
            - `{"type": "connected", "message": "Подключение установлено"}` - Подтверждение подключения
            - `{"type": "support_message", "message": "...", "support_name": "..."}` - Сообщения от поддержки
            - `{"type": "support_media", "media_type": "...", "media_url": "..."}` - Медиа от поддержки
            - `{"type": "update", "status": "..."}` - Обновления статуса тикета
            - `{"type": "message_sent"}` - Подтверждение отправки вашего сообщения

            **Входящие сообщения (вы отправляете):**
            ```json
            // Подписка
            {
              "type": "subscribe",
              "ticket_id": 123,
              "user_id": 456
            }

            // Текстовое сообщение
            {
              "type": "message",
              "message": "Привет, нужна помощь"
            }

            // Медиа по URL
            {
              "type": "media",
              "media_type": "photo",
              "media_url": "https://example.com/image.jpg",
              "media_caption": "Скриншот проблемы"
            }

            // Прямая загрузка фото (base64)
            {
              "type": "media",
              "media_type": "photo",
              "media_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
              "filename": "screenshot.jpg",
              "media_caption": "Скриншот с ошибкой"
            }

            // Прямая загрузка видео
            {
              "type": "media",
              "media_type": "video",
              "media_data": "AAAFB...ваши_base64_данные_видео...",
              "filename": "error_demo.mp4",
              "media_caption": "Видео не работает"
            }
            ```
            """
            await websocket_manager.handle_websocket(websocket, ticket_id)
        
        @app.post(
            "/api/ticket/{ticket_id}/rating",
            response_model=RatingResponse,
            tags=["Оценки"],
            summary="Отправить оценку тикета",
            description="Отправляет оценку и опциональный комментарий для закрытого тикета"
        )
        async def submit_rating(
            ticket_id: int = Path(..., description="ID тикета", examples=[1]),
            rating_request: RatingRequest = ...
        ):
            return await rating_controller.submit_rating(ticket_id, rating_request)
        
        @app.get(
            "/api/ticket/{ticket_id}/status",
            response_model=TicketStatusResponse,
            tags=["Тикеты"],
            summary="Получить статус тикета",
            description="Возвращает текущий статус и информацию о тикете"
        )
        async def get_ticket_status(
            ticket_id: int = Path(..., description="ID тикета", examples=[1])
        ):
            return await ticket_controller.get_ticket_status(ticket_id)

        @app.post(
            "/api/ticket/{ticket_id}/close",
            response_model=UpdateResponse,
            tags=["Тикеты"],
            summary="Закрыть тикет",
            description="Закрывает существующий тикет поддержки"
        )
        async def close_ticket(
            ticket_id: int = Path(..., description="ID тикета", examples=[1])
        ):
            return await ticket_controller.close_ticket(ticket_id)

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
        logger.info("Запуск Support Bot с API...")
        
        api_app = FastAPI(
            lifespan=lifespan,
            title="Support Bot API",
            version="1.2.0",
            description="""
            API для управления тикетами поддержки с расширенной медиа поддержкой.

            
            - **Прямая загрузка файлов**: Base64 encoded фото, видео и документы
            - **Медиа загрузка**: Поддержка фото, видео и документов через API и WebSocket
            - **Реальное время**: Двунаправленное общение через WebSocket
            - **Интеграция**: Полная интеграция с Telegram ботом поддержки

            
            1. Создайте тикет через `/api/ticket/create`
            2. Подключитесь к WebSocket `/ws/ticket/{ticket_id}`
            3. Отправляйте сообщения с прикрепленными файлами
            4. Общайтесь в реальном времени с поддержкой
            """,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )

        api_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
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
