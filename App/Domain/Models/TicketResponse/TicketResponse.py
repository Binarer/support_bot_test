from pydantic import BaseModel


class TicketResponse(BaseModel):
    ticket_id: int
    display_id: int
    status: str
    message: str

