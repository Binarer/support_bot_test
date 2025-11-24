import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_ADMIN_IDS: List[int] = []
        self.SUPPORT_CHANNEL_ID: int = int(os.getenv('SUPPORT_CHANNEL_ID', '0'))
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self._parse_admin_ids()
        self._validate()

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