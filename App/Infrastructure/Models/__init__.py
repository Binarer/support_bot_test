from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.sql import func

Base = declarative_base()

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    display_id = Column(Integer, unique=True, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String, nullable=True)
    user_message = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    taken_by = Column(BigInteger, nullable=True, index=True)
    taken_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    channel_message_id = Column(BigInteger, nullable=True)
    topic_thread_id = Column(BigInteger, nullable=True)
    user_message_id = Column(BigInteger, nullable=True)

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
