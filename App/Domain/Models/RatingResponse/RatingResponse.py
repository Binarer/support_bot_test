from pydantic import BaseModel


class RatingResponse(BaseModel):
    success: bool
    message: str

