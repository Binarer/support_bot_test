import logging
from datetime import datetime

from App.Domain.Services.TicketService.ticket_service import TicketService
from App.Domain.Services.RatingService.rating_service import RatingService
from App.Domain.Models.RatingRequest.RatingRequest import RatingRequest
from App.Domain.Models.TicketResponse.TicketResponse import TicketResponse
from App.Domain.Models.TicketStatusResponse.TicketStatusResponse import TicketStatusResponse
from App.Domain.Models.RatingResponse.RatingResponse import RatingResponse
from App.Domain.Models.MessageRequest.MessageRequest import MessageRequest
from App.Domain.Models.MessageResponse.MessageResponse import MessageResponse
from App.Domain.Models.UpdateResponse.UpdateResponse import UpdateResponse

logger = logging.getLogger(__name__)


class TicketApplicationService:
    def __init__(
        self,
        ticket_service: TicketService,
        rating_service: RatingService
    ):
        self.ticket_service = ticket_service
        self.rating_service = rating_service

    async def create_ticket(
        self,
        user_id: int,
        username: str,
        message: str,
        category: str = ""
    ) -> TicketResponse:
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB
        from App.Domain.Services.TicketService.ticket_service import TicketService

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

    async def send_message_to_ticket(self, ticket_id: int, message_request: MessageRequest) -> MessageResponse:
        """Отправить сообщение в тикет"""
        try:
            success = await self.ticket_service.send_message_to_ticket(ticket_id, message_request.message)
            if success:
                return MessageResponse(
                    success=True,
                    message="Сообщение успешно отправлено"
                )
            else:
                return MessageResponse(
                    success=False,
                    message="Не удалось отправить сообщение"
                )
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в тикет {ticket_id}: {e}")
            raise

    async def close_ticket(self, ticket_id: int) -> UpdateResponse:
        """Закрыть тикет по ID"""
        try:
            ticket = self.ticket_service.get_ticket_by_db_id(ticket_id)
            if not ticket:
                raise ValueError("Тикет не найден")

            if ticket.status == "closed":
                raise ValueError("Тикет уже закрыт")

            if ticket.status == "cancelled":
                raise ValueError("Тикет отменен")

            success = await self.ticket_service.close_ticket_by_internal_id(ticket_id)
            if success:
                return UpdateResponse(
                    success=True,
                    message="Тикет успешно закрыт"
                )
            else:
                return UpdateResponse(
                    success=False,
                    message="Не удалось закрыть тикет"
                )
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"Ошибка закрытия тикета {ticket_id}: {e}")
            raise Exception("Ошибка закрытия тикета")
