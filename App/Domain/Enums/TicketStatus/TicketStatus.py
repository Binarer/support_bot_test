from enum import Enum

class TicketStatus(Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"