import logging
from typing import Optional

from App.Infrastructure.Models.database import get_db
from App.Infrastructure.Models import TicketRating

logger = logging.getLogger(__name__)


class RatingService:
    """Сервис для управления оценками тикетов"""

    def __init__(self):
        logger.info("RatingService инициализирован")

    def save_ticket_rating(self, ticket_display_id: int, user_id: int, rating: int) -> bool:
        """Сохранить оценку тикета в отдельную таблицу"""
        db = get_db()
        try:
            from App.Infrastructure.Models import Ticket
            ticket_record = db.query(Ticket).filter(Ticket.display_id == ticket_display_id).first()
            if not ticket_record:
                logger.warning(f"Тикет с display_id {ticket_display_id} не найден")
                return False

            existing_rating = db.query(TicketRating).filter(
                TicketRating.ticket_id == ticket_record.id,
                TicketRating.user_id == user_id
            ).first()

            if existing_rating:
                existing_rating.rating = rating
                logger.info(f"Обновлен рейтинг для тикета #{ticket_display_id} от пользователя {user_id}: {rating}")
            else:
                new_rating = TicketRating(
                    ticket_id=ticket_record.id,
                    user_id=user_id,
                    rating=rating
                )
                db.add(new_rating)
                logger.info(f"Создан новый рейтинг для тикета #{ticket_display_id} от пользователя {user_id}: {rating}")

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка сохранения оценки для тикета #{ticket_display_id}: {e}")
            return False
        finally:
            db.close()

    def save_ticket_comment(self, ticket_display_id: int, user_id: int, comment: str):
        """Сохранить комментарий к рейтингу тикета"""
        db = get_db()
        try:
            from App.Infrastructure.Models import Ticket
            ticket_record = db.query(Ticket).filter(Ticket.display_id == ticket_display_id).first()
            if not ticket_record:
                logger.warning(f"Тикет с display_id {ticket_display_id} не найден для комментария")
                return

            existing_rating = db.query(TicketRating).filter(
                TicketRating.ticket_id == ticket_record.id,
                TicketRating.user_id == user_id
            ).first()

            if existing_rating:
                existing_rating.comment = comment
                db.commit()
                logger.info(f"Добавлен комментарий к рейтингу тикета #{ticket_display_id}")
            else:
                logger.warning(f"Рейтинг не найден для комментария к тикету #{ticket_display_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка сохранения комментария для тикета #{ticket_display_id}: {e}")
        finally:
            db.close()
