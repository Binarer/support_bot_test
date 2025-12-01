import logging
from fastapi import HTTPException, Query

from App.Domain.Services.TicketApplicationService.ticket_application_service import TicketApplicationService
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse
from App.Domain.Models.MessageRequest.MessageRequest import MessageRequest
from App.Domain.Models.MessageResponse.MessageResponse import MessageResponse

logger = logging.getLogger(__name__)


class TicketController:
    def __init__(self, ticket_application_service: TicketApplicationService):
        self.ticket_application_service = ticket_application_service

    async def create_ticket(
        self,
        user_id: int,
        username: str,
        message: str,
        category: str = ""
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

    async def get_ticket_status(self, ticket_id: int) -> TicketStatusResponse:
        try:
            return self.ticket_application_service.get_ticket_status(ticket_id)
        except ValueError as e:
            logger.error(f"Тикет {ticket_id} не найден: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Ошибка получения статуса тикета {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")

    async def send_message_to_ticket(
        self,
        ticket_id: int,
        message_request: MessageRequest
    ) -> MessageResponse:
        try:
            return await self.ticket_application_service.send_message_to_ticket(ticket_id, message_request)
        except ValueError as e:
            logger.error(f"Ошибка отправки сообщения в тикет {ticket_id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в тикет {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка отправки сообщения: {str(e)}")

    async def close_ticket(self, ticket_id: int):
        try:
            return await self.ticket_application_service.close_ticket(ticket_id)
        except ValueError as e:
            logger.error(f"Ошибка закрытия тикета {ticket_id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Ошибка закрытия тикета {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка закрытия тикета: {str(e)}")
