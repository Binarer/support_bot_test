import logging
from typing import Optional

from App.Infrastructure.Models.database import get_db
from App.Infrastructure.Models import AdminBalance

logger = logging.getLogger(__name__)


class BalanceService:
    """Сервис для управления балансом администраторов"""

    def __init__(self):
        logger.info("BalanceService инициализирован")

    def get_admin_balance(self, admin_id: int) -> float:
        """Получить баланс администратора"""
        db = get_db()
        try:
            admin = db.query(AdminBalance).filter(AdminBalance.admin_id == admin_id).first()
            return admin.balance if admin else 0.0
        finally:
            db.close()

    def add_balance(self, admin_id: int, amount: float) -> float:
        """Начислить баланс администратору"""
        db = get_db()
        try:
            admin = db.query(AdminBalance).filter(AdminBalance.admin_id == admin_id).first()
            if not admin:
                admin = AdminBalance(admin_id=admin_id, balance=amount)
                db.add(admin)
            else:
                admin.balance += amount
            db.commit()
            db.refresh(admin)
            logger.info(f"Начислено {amount} ₽ администратору {admin_id}, новый баланс: {admin.balance}")
            return admin.balance
        finally:
            db.close()
