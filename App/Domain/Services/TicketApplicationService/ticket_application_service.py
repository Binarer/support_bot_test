import logging
from datetime import datetime

from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.RatingService.rating_service import RatingService
from App.Domain.Models.RatingRequest.RatingRequest import RatingRequest
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.UpdateResponse.UpdateResponse import UpdateResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse
from App.Domain.Models.RatingResponse.RatingResponse import RatingResponse
from App.Infrastructure.Components.Http.longpoll_manager import LongpollManager

logger = logging.getLogger(__name__)


class TicketApplicationService:
    def __init__(
        self,
        ticket_service: TicketService,
        rating_service: RatingService,
        longpoll_manager: LongpollManager
    ):
        self.ticket_service = ticket_service
        self.rating_service = rating_service
        self.longpoll_manager = longpoll_manager

    async def create_ticket(
        self,
        user_id: int,
        username: str,
        message: str,
        category: str = ""
    ) -> TicketResponse:
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        ticket = await self.ticket_service.create_ticket(
            user_id=user_id,
            username=username,
            user_message=message,
            category=category
        )

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket.db_id).first()
            status_str = db_ticket.status if db_ticket else "pending"
        finally:
            db.close()

        return TicketResponse(
            ticket_id=ticket.db_id,
            display_id=ticket.display_id,
            status=status_str,
            message="Тикет успешно создан"
        )

    async def get_ticket_updates(
        self,
        ticket_id: int,
        timeout: int = 30
    ) -> UpdateResponse:
        update = await self.longpoll_manager.wait_for_update(ticket_id, timeout=timeout)

        if update is None:
            return UpdateResponse(
                ticket_id=ticket_id,
                status="timeout",
                message="Таймаут ожидания обновлений",
                timestamp=datetime.now().isoformat()
            )

        return UpdateResponse(
            ticket_id=update.ticket_id,
            status=update.status,
            message=update.message,
            timestamp=update.timestamp.isoformat() if update.timestamp else None
        )

    async def submit_rating(
        self,
        ticket_id: int,
        rating_request: RatingRequest
    ) -> RatingResponse:
        if not (1 <= rating_request.rating <= 5):
            raise ValueError("Оценка должна быть от 1 до 5")

        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB, TicketRating

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket_id).first()
            if not db_ticket:
                raise ValueError("Тикет не найден")

            display_id = db_ticket.display_id
            user_id = db_ticket.user_id

            success = self.rating_service.save_ticket_rating(display_id, user_id, rating_request.rating)

            if not success:
                raise ValueError("Ошибка сохранения оценки")

            if rating_request.comment:
                self.rating_service.save_ticket_comment(display_id, user_id, rating_request.comment)

            rating_record = db.query(TicketRating).filter(
                TicketRating.ticket_id == db_ticket.id,
                TicketRating.user_id == user_id
            ).first()

            if rating_record:
                username = db_ticket.username or f"user_{user_id}"
                await self.ticket_service.channel_manager.send_rating_to_reviews_topic(
                    display_id,
                    username,
                    rating_record.rating,
                    rating_request.comment
                )

            return RatingResponse(
                success=True,
                message="Оценка успешно сохранена"
            )
        finally:
            db.close()

    def get_ticket_status(self, ticket_id: int) -> TicketStatusResponse:
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket_id).first()
            if not db_ticket:
                raise ValueError("Тикет не найден")

            return TicketStatusResponse(
                ticket_id=db_ticket.id,
                display_id=db_ticket.display_id,
                status=db_ticket.status,
                created_at=db_ticket.created_at.isoformat() if db_ticket.created_at else None,
                closed_at=db_ticket.closed_at.isoformat() if db_ticket.closed_at else None
            )
        finally:
            db.close()

