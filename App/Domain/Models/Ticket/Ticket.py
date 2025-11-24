from datetime import datetime
from typing import Optional

from App.Domain.Enums.TicketStatus.TicketStatus import TicketStatus


class Ticket:
    _next_id = 1

    def __init__(self, user_id: int, username: str, user_message: str):
        self.id_int: int = Ticket._next_id
        Ticket._next_id += 1
        self.id: str = f"ticket_{self.id_int}"
        self.display_id: int = self.id_int  # Для отображения

        self.user_id: int = user_id
        self.username: str = username
        self.user_message: str = user_message
        self.status: TicketStatus = TicketStatus.OPEN
        self.channel_message_id: Optional[int] = None
        self.topic_thread_id: Optional[int] = None
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.closed_by: Optional[str] = None

    def mark_answered(self):
        self.status = TicketStatus.ANSWERED
        self.updated_at = datetime.now()

    def close(self, closed_by: str):
        self.status = TicketStatus.CLOSED
        self.closed_by = closed_by
        self.updated_at = datetime.now()
