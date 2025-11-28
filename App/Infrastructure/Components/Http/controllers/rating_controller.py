import logging
from fastapi import HTTPException

from App.Domain.Services.TicketApplicationService.ticket_application_service import TicketApplicationService
from App.Domain.Models.RatingRequest.RatingRequest import RatingRequest
from App.Domain.Models.RatingResponse.RatingResponse import RatingResponse

logger = logging.getLogger(__name__)


class RatingController:
    def __init__(self, ticket_application_service: TicketApplicationService):
        self.ticket_application_service = ticket_application_service

    async def submit_rating(
        self,
        ticket_id: int,
        rating_request: RatingRequest
    ) -> RatingResponse:
        try:
            return await self.ticket_application_service.submit_rating(ticket_id, rating_request)
        except ValueError as e:
            error_message = str(e)
            if "не найден" in error_message:
                raise HTTPException(status_code=404, detail=error_message)
            elif "Оценка должна быть" in error_message:
                raise HTTPException(status_code=400, detail=error_message)
            else:
                raise HTTPException(status_code=400, detail=error_message)
        except Exception as e:
            logger.error(f"Ошибка сохранения оценки для тикета {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения оценки: {str(e)}")

