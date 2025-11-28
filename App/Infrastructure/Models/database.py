import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем синхронный движок
engine = create_engine(config.DATABASE_URL, echo=False)

# Создаем сессию
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Получить сессию базы данных"""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def create_tables():
    """Создать все таблицы в базе данных"""
    Base.metadata.create_all(bind=engine)


def init_db():
    """Инициализация базы данных"""
    try:
        create_tables()
        logger.info("База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")

