from pydantic import BaseModel, Field
from typing import Optional, Literal


class MessageRequest(BaseModel):
    message: str = Field(..., description="Текст сообщения для отправки в тикет", examples=[{"value": "Дополнительная информация по проблеме"}])
    media_type: Optional[Literal["photo", "video", "document"]] = Field(
        None,
        description="Тип медиа файла для загрузки",
        examples=[{"value": "photo"}]
    )
    media_url: Optional[str] = Field(
        None,
        description="URL медиа файла для скачивания и пересылки поддержке",
        examples=[{"value": "https://example.com/image.jpg"}]
    )
    media_caption: Optional[str] = Field(
        None,
        description="Подпись к медиа файлу",
        examples=[{"value": "Скриншот проблемы"}]
    )
