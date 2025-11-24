"""Модели SQLAlchemy для базы данных"""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.sql import func
from database import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    number = Column(Integer, unique=True, nullable=False, index=True)
    source = Column(String, nullable=True)
    external_id = Column(String, nullable=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="new", index=True)
    topic_id = Column(Integer, nullable=True, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    admin_id = Column(BigInteger, nullable=True, index=True)
    rating = Column(Integer, nullable=True)
    rating_comment = Column(Text, nullable=True)

class AdminBalance(Base):
    __tablename__ = "admin_balances"

    admin_id = Column(BigInteger, primary_key=True, index=True)
    balance = Column(Float, default=0.0)

class Meta(Base):
    __tablename__ = "meta"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)

class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    sender_id = Column(BigInteger, nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TicketRating(Base):
    __tablename__ = "ticket_ratings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


