from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    user_id: int = Field(..., description="ID пользователя", examples=[{"value": 123456789}])
    username: str = Field(..., description="Имя пользователя", examples=[{"value": "user123"}])
    message: str = Field(..., description="Сообщение пользователя", examples=[{"value": "Помогите с проблемой"}])
    category: str = Field("", description="Категория тикета", examples=[{"value": "technical"}])

