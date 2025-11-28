from pydantic import BaseModel
from typing import Optional


class UpdateResponse(BaseModel):
    ticket_id: int
    status: str
    message: Optional[str] = None
    timestamp: str

