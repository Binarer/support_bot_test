import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_ADMIN_IDS: List[int] = []
        self.SUPPORT_CHANNEL_ID: int = int(os.getenv('SUPPORT_CHANNEL_ID', '0'))
        self.GENERAL_TOPIC_ID: int = int(os.getenv('GENERAL_TOPIC_ID', '1'))  # Default to thread_id=1 if not set
        self.REVIEWS_TOPIC_ID: Optional[int] = int(os.getenv('REVIEWS_TOPIC_ID', '0')) if os.getenv('REVIEWS_TOPIC_ID') else None
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

        # Database configuration
        self.DB_HOST: str = os.getenv('DB_HOST', 'localhost')
        self.DB_PORT: str = os.getenv('DB_PORT', '15432')
        self.DB_NAME: str = os.getenv('DB_NAME', 'support_bot')
        self.DB_USER: str = os.getenv('DB_USER', 'postgres')
        self.DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')

        # Database URL for SQLAlchemy
        self.DATABASE_URL: str = f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        self.bot_messages: Dict[str, Any] = {}
        self.bot_keyboards: Dict[str, Any] = {}
        self._load_bot_messages()
        self._parse_admin_ids()
        self._validate()

    def _load_bot_messages(self):
        try:
            bot_json_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'bot.json')
            with open(bot_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.bot_messages = data.get('messages', {})
                self.bot_keyboards = data.get('keyboards', {})
        except Exception as e:
            print(f"Ошибка загрузки bot.json: {e}")
            self.bot_messages = {}
            self.bot_keyboards = {}

    def _parse_admin_ids(self):
        admin_ids_str = os.getenv('TELEGRAM_ADMIN_IDS', '')
        if admin_ids_str:
            try:
                self.TELEGRAM_ADMIN_IDS = [
                    int(admin_id.strip()) for admin_id in admin_ids_str.split(',')
                    if admin_id.strip()
                ]
            except ValueError as e:
                print(f"Ошибка парсинга TELEGRAM_ADMIN_IDS: {e}")

    def _validate(self):
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
        if not self.SUPPORT_CHANNEL_ID:
            raise ValueError("SUPPORT_CHANNEL_ID не установлен")


config = Config()
