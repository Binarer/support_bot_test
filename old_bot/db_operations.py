"""Функции для работы с базой данных PostgreSQL"""
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from database import SessionLocal
from models import Ticket, AdminBalance, Meta, TicketHistory, TicketRating
import logging

logger = logging.getLogger(__name__)

# ---------- Ticket Operations ----------

async def get_next_ticket_number() -> int:
    """Получить следующий номер тикета"""
    async with SessionLocal() as session:
        # Получаем текущий счетчик
        result = await session.execute(select(Meta).where(Meta.key == "ticket_counter"))
        meta = result.scalar_one_or_none()
        
        if not meta:
            # Создаем счетчик если его нет
            meta = Meta(key="ticket_counter", value="0")
            session.add(meta)
            await session.commit()
        
        # Увеличиваем счетчик
        current_value = int(meta.value)
        new_value = current_value + 1
        meta.value = str(new_value)
        await session.commit()
        return new_value

async def create_ticket_record(number: int, source: str, external_id: str, user_id: int, 
                               username: str, category: str, description: str) -> int:
    """Создать запись тикета"""
    async with SessionLocal() as session:
        ticket = Ticket(
            number=number,
            source=source,
            external_id=external_id,
            user_id=user_id,
            username=username,
            category=category,
            description=description,
            status="new"
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket.id

async def set_ticket_topic(ticket_id: int, topic_id: int, admin_id: int = None):
    """Установить тему для тикета и сохранить админа"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one()
        
        ticket.topic_id = topic_id
        ticket.status = "in_progress"
        if admin_id:
            ticket.admin_id = admin_id
        
        await session.commit()

async def get_ticket_by_number(number: int):
    """Получить тикет по номеру"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.number == number))
        return result.scalar_one_or_none()

async def get_ticket_by_topic(topic_id: int):
    """Получить тикет по topic_id"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.topic_id == topic_id))
        return result.scalar_one_or_none()

async def get_last_ticket_for_user(user_id: int):
    """Получить последний тикет пользователя"""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

async def close_ticket_by_topic(topic_id: int):
    """Закрыть тикет по topic_id"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.topic_id == topic_id))
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.status = "closed"
            ticket.closed_at = datetime.now(timezone.utc)
            await session.commit()

async def close_ticket_by_number(number: int):
    """Закрыть тикет по номеру"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.number == number))
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.status = "closed"
            ticket.closed_at = datetime.now(timezone.utc)
            await session.commit()

# ---------- Balance Operations ----------

async def get_admin_balance(admin_id: int) -> float:
    """Получить баланс администратора"""
    async with SessionLocal() as session:
        result = await session.execute(select(AdminBalance).where(AdminBalance.admin_id == admin_id))
        admin = result.scalar_one_or_none()
        return admin.balance if admin else 0.0

async def add_balance(admin_id: int, amount: float) -> float:
    """Начислить баланс администратору"""
    async with SessionLocal() as session:
        result = await session.execute(select(AdminBalance).where(AdminBalance.admin_id == admin_id))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = AdminBalance(admin_id=admin_id, balance=amount)
            session.add(admin)
        else:
            admin.balance += amount
        
        await session.commit()
        await session.refresh(admin)
        return admin.balance

# ---------- Statistics Operations ----------

async def get_active_tickets_count(admin_id: int = None) -> int:
    """Получить количество активных тикетов"""
    async with SessionLocal() as session:
        if admin_id:
            result = await session.execute(
                select(func.count(Ticket.id))
                .where(and_(Ticket.status == "in_progress", Ticket.admin_id == admin_id))
            )
        else:
            result = await session.execute(
                select(func.count(Ticket.id))
                .where(Ticket.status.in_(["new", "in_progress"]))
            )
        return result.scalar() or 0

async def get_closed_tickets_count(period: str = "today", admin_id: int = None) -> int:
    """Получить количество закрытых тикетов за период"""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = select(func.count(Ticket.id)).where(
            and_(
                Ticket.status == "closed",
                Ticket.closed_at >= start_date
            )
        )
        
        if admin_id:
            query = query.where(Ticket.admin_id == admin_id)
        
        result = await session.execute(query)
        return result.scalar() or 0

async def get_best_admin_by_stats():
    """Получить лучшего администратора по количеству закрытых тикетов за месяц"""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=30)
        
        result = await session.execute(
            select(Ticket.admin_id, func.count(Ticket.id).label("closed_count"))
            .where(
                and_(
                    Ticket.status == "closed",
                    Ticket.closed_at >= start_date,
                    Ticket.admin_id.isnot(None)
                )
            )
            .group_by(Ticket.admin_id)
            .order_by(func.count(Ticket.id).desc())
            .limit(1)
        )
        
        row = result.first()
        if row:
            return row[0], row[1]  # admin_id, closed_count
        return None, 0

async def log_ticket_closed(topic_id: int, admin_id: int):
    """Записать в историю закрытие тикета"""
    async with SessionLocal() as session:
        result = await session.execute(select(Ticket).where(Ticket.topic_id == topic_id))
        ticket = result.scalar_one_or_none()
        
        if ticket:
            ticket.status = "closed"
            ticket.closed_at = datetime.now(timezone.utc)
            ticket.admin_id = admin_id
            await session.commit()

# ---------- Rating Operations ----------

async def save_ticket_rating(ticket_number: int, user_id: int, rating: int) -> bool:
    """Сохранить рейтинг тикета в отдельную таблицу
    
    Returns:
        bool: True если успешно сохранено, False если ошибка
    """
    async with SessionLocal() as session:
        try:
            # Получаем ticket_id по номеру
            result = await session.execute(select(Ticket).where(Ticket.number == ticket_number))
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                logger.warning(f"Тикет с номером {ticket_number} не найден")
                return False
            
            # Проверяем, есть ли уже рейтинг от этого пользователя
            rating_result = await session.execute(
                select(TicketRating)
                .where(and_(TicketRating.ticket_id == ticket.id, TicketRating.user_id == user_id))
            )
            existing_rating = rating_result.scalar_one_or_none()
            
            if existing_rating:
                # Обновляем существующий рейтинг
                existing_rating.rating = rating
                logger.info(f"Обновлен рейтинг для тикета #{ticket_number} от пользователя {user_id}: {rating}")
            else:
                # Создаем новый рейтинг
                new_rating = TicketRating(
                    ticket_id=ticket.id,
                    user_id=user_id,
                    rating=rating
                )
                session.add(new_rating)
                logger.info(f"Создан новый рейтинг для тикета #{ticket_number} от пользователя {user_id}: {rating}")
            
            await session.commit()
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка сохранения оценки для тикета #{ticket_number}: {e}")
            return False

async def save_ticket_comment(ticket_number: int, user_id: int, comment: str):
    """Сохранить комментарий к рейтингу тикета"""
    async with SessionLocal() as session:
        # Получаем ticket_id по номеру
        result = await session.execute(select(Ticket).where(Ticket.number == ticket_number))
        ticket = result.scalar_one_or_none()
        
        if ticket:
            # Обновляем комментарий в существующем рейтинге
            rating_result = await session.execute(
                select(TicketRating)
                .where(and_(TicketRating.ticket_id == ticket.id, TicketRating.user_id == user_id))
            )
            existing_rating = rating_result.scalar_one_or_none()
            
            if existing_rating:
                existing_rating.comment = comment
                await session.commit()


