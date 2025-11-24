"""Подключение к PostgreSQL через SQLAlchemy"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем параметры подключения из .env
DB_USER = os.getenv("DB_USER", "botuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ticketbot")

# Используем asyncpg для асинхронного подключения
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Устанавливаем правильную кодировку для клиента через server_settings
    connect_args={
        "server_settings": {
            "client_encoding": "utf8"
        }
    },
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=3600,   # Переподключение каждые 3600 секунд
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()


