from pydantic import BaseModel
from typing import Optional


class TicketStatusResponse(BaseModel):
    ticket_id: int
    display_id: int
    status: str
    created_at: Optional[str] = None
    closed_at: Optional[str] = None

