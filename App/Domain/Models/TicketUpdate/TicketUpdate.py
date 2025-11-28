from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class TicketUpdate:
    ticket_id: int
    status: str
    message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

