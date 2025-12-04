from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from App.Domain.Enums.TicketStatus.TicketStatus import TicketStatus


@dataclass
class Ticket:
    """Доменная модель тикета"""

    
    user_id: int
    username: str
    user_message: str
    category: str
    
    db_id: Optional[int] = None
    display_id: Optional[int] = None

    channel_message_id: Optional[int] = None
    topic_thread_id: Optional[int] = None
    user_message_id: Optional[int] = None
    
    status: TicketStatus = TicketStatus.OPEN
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_by: Optional[str] = None

    def __post_init__(self):
        """Инициализация после создания датакласса."""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

        if self.db_id:
            self.id = str(self.db_id)

    @property
    def id(self) -> Optional[str]:
        """Получить ID тикета в коротком формате."""
        return str(self.db_id) if self.db_id else None

    @id.setter
    def id(self, value: str) -> None:
        """Установить ID тикета."""
        if value and value.isdigit():
            self.db_id = int(value)
        elif value is None:
            self.db_id = None
