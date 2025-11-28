from pydantic import BaseModel, Field
from typing import Optional


class RatingRequest(BaseModel):
    rating: int = Field(..., description="Оценка от 1 до 5", ge=1, le=5, examples=[{"value": 5}])
    comment: Optional[str] = Field(None, description="Комментарий к оценке", examples=[{"value": "Отличная работа!"}])

