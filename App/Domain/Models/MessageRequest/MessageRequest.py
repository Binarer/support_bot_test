from pydantic import BaseModel, Field
from typing import Optional, Literal, Union


class MessageRequest(BaseModel):
    message: str = Field(..., description="Текст сообщения для отправки в тикет", examples=[{"value": "Дополнительная информация по проблеме"}])
    media_type: Optional[Literal["photo", "video", "document"]] = Field(
        None,
        description="Тип медиа файла для загрузки",
        examples=[{"value": "photo"}]
    )
    media_url: Optional[str] = Field(
        None,
        description="URL медиа файла для скачивания и пересылки поддержке (альтернатива media_data)",
        examples=[{"value": "https://example.com/image.jpg"}]
    )
    media_data: Optional[str] = Field(
        None,
        description="Бинарные данные медиа файла в base64 формате (альтернатива media_url)",
        examples=[{"value": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}]
    )
    media_caption: Optional[str] = Field(
        None,
        description="Подпись к медиа файлу",
        examples=[{"value": "Скриншот проблемы"}]
    )
    filename: Optional[str] = Field(
        None,
        description="Имя файла для медиа (обязательно при использовании media_data)",
        examples=[{"value": "screenshot.jpg"}]
    )
