import logging
from fastapi import HTTPException, Query

from App.Domain.Services.TicketApplicationService.ticket_application_service import TicketApplicationService
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.UpdateResponse.UpdateResponse import UpdateResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse

logger = logging.getLogger(__name__)


class TicketController:
    def __init__(self, ticket_application_service: TicketApplicationService):
        self.ticket_application_service = ticket_application_service

    async def create_ticket(
        self,
        user_id: int = Query(..., description="ID пользователя"),
        username: str = Query(..., description="Имя пользователя"),
        message: str = Query(..., description="Сообщение пользователя"),
        category: str = Query("", description="Категория тикета")
    ) -> TicketResponse:
        try:
            return await self.ticket_application_service.create_ticket(
                user_id=user_id,
                username=username,
                message=message,
                category=category
            )
        except Exception as e:
            logger.error(f"Ошибка создания тикета через API: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка создания тикета: {str(e)}")

    async def get_ticket_updates(
        self,
        ticket_id: int,
        timeout: int = Query(30, ge=1, le=120, description="Таймаут ожидания в секундах")
    ) -> UpdateResponse:
        try:
            return await self.ticket_application_service.get_ticket_updates(ticket_id, timeout)
        except Exception as e:
            logger.error(f"Ошибка получения обновлений тикета {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения обновлений: {str(e)}")

    async def get_ticket_status(self, ticket_id: int) -> TicketStatusResponse:
        try:
            return self.ticket_application_service.get_ticket_status(ticket_id)
        except ValueError as e:
            logger.error(f"Тикет {ticket_id} не найден: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Ошибка получения статуса тикета {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")

