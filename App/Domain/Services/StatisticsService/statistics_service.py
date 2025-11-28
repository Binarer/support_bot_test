import logging
import io
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

from App.Infrastructure.Models.database import get_db
from App.Infrastructure.Models import Ticket, AdminBalance

logger = logging.getLogger(__name__)


class StatisticsService:
    """Сервис для генерации статистики с графиками"""

    def __init__(self, bot=None):
        self.bot = bot
        logger.info("StatisticsService инициализирован")

    def get_active_tickets_count(self, admin_id: int = None) -> int:
        """Получить количество активных тикетов"""
        db = get_db()
        try:
            query = db.query(Ticket).filter(Ticket.status.in_(["pending", "taken", "answered"]))
            if admin_id:
                query = query.filter(Ticket.taken_by == admin_id)
            return query.count()
        finally:
            db.close()

    async def _get_admin_display_name(self, admin_id: int) -> str:
        """Получить отображаемое имя администратора (username или user_id)"""
        if not self.bot:
            return f"Админ {admin_id}"
        try:
            user = await self.bot.get_chat(admin_id)
            if user.username:
                return f"@{user.username}"
            else:
                return f"user_{admin_id}"
        except Exception:
            return f"user_{admin_id}"

    def get_closed_tickets_count(self, period: str = "today", admin_id: int = None) -> int:
        """Получить количество закрытых тикетов за период"""
        db = get_db()
        try:
            now = datetime.now()
            if period == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start_date = now - timedelta(days=7)
            elif period == "month":
                start_date = now - timedelta(days=30)
            else:
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

            query = db.query(Ticket).filter(
                Ticket.status == "closed",
                Ticket.closed_at >= start_date
            )
            if admin_id:
                query = query.filter(Ticket.taken_by == admin_id)
            return query.count()
        finally:
            db.close()

    def get_best_admin_by_closed(self):
        """Получить лучшего администратора по количеству закрытых тикетов за месяц"""
        db = get_db()
        try:
            now = datetime.now()
            start_date = now - timedelta(days=30)

            from sqlalchemy import func
            result = db.query(Ticket.taken_by, func.count(Ticket.id).label("closed_count")).filter(
                Ticket.status == "closed",
                Ticket.closed_at >= start_date,
                Ticket.taken_by.isnot(None)
            ).group_by(Ticket.taken_by).order_by(func.count(Ticket.id).desc()).first()

            if result:
                return result[0], result[1]
            return None, 0
        finally:
            db.close()

    def generate_stats_image(self, admin_id: int) -> bytes:
        """Генерировать изображение с графиком статистики администратора"""
        today = self.get_closed_tickets_count("today", admin_id)
        week = self.get_closed_tickets_count("week", admin_id)
        month = self.get_closed_tickets_count("month", admin_id)
        active = self.get_active_tickets_count(admin_id)

        periods = ['Сегодня', 'За неделю', 'За месяц']
        closed_counts = [today, week, month]

        sns.set_style("whitegrid")
        plt.figure(figsize=(8, 5))
        plt.suptitle(f'Статистика администратора {admin_id}', fontsize=16, fontweight='bold')
        plt.subplot(1, 2, 1)

        plt.bar(periods, closed_counts, color=['skyblue', 'lightgreen', 'coral'])
        plt.title('Закрытые тикеты', fontsize=14)
        plt.ylabel('Количество', fontsize=12)

        plt.subplot(1, 2, 2)
        plt.axis('off')
        info_text = f"""Активных тикетов: {active}
Закрыто сегодня: {today}
За неделю: {week}
За месяц: {month}"""
        plt.text(0.1, 0.5, info_text, fontsize=12, verticalalignment='center', bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat"))

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf.getvalue()

    async def generate_top_stats_image(self) -> bytes:
        """Генерировать изображение с статистикой"""
        from App.Infrastructure.Models.database import get_db
        from datetime import datetime, timedelta
        from sqlalchemy import func

        db = get_db()
        try:
            now = datetime.now()
            start_date = now - timedelta(days=30)

            results = db.query(Ticket.taken_by, func.count(Ticket.id).label("closed_count")).filter(
                Ticket.status == "closed",
                Ticket.closed_at >= start_date,
                Ticket.taken_by.isnot(None)
            ).group_by(Ticket.taken_by).order_by(func.count(Ticket.id).desc()).limit(10).all()

            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 8), facecolor='black')
            ax.axis('off')

            fig.suptitle('ТОП ПОДДЕРЖКИ ЗА 30 ДНЕЙ', fontsize=18, fontweight='bold', color='white', y=0.93)

            if results:
                table_data = []
                for i, (admin_id, count) in enumerate(results, 1):
                    admin_name = await self._get_admin_display_name(admin_id)
                    table_data.append([f'{i}.', admin_name, f'{count}'])
                col_labels = ['№', 'Админ', 'Тикетов']
            else:
                table_data = [['—', 'Нет данных', '—']]

            table = ax.table(
                cellText=table_data,
                colLabels=col_labels,
                cellLoc='center',
                colLoc='center',
                loc='center',
                colWidths=[0.15, 0.4, 0.25],
            )

            table.auto_set_font_size(False)
            table.set_fontsize(12)
            table.scale(1, 2)

            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#555555')
                table[(0, i)].set_text_props(weight='bold', color='white')

            for i in range(1, len(table_data) + 1):
                color = '#333333' if i % 2 == 0 else '#2a2a2a'
                for j in range(len(col_labels)):
                    table[(i, j)].set_facecolor(color)
                    table[(i, j)].set_text_props(color='white')

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            plt.style.use('default')
            buf.seek(0)
            return buf.getvalue()
        finally:
            db.close()

    async def generate_stats_text(self, admin_id: int) -> str:
        """Генерировать текстовую статистику администратора для edit_message"""
        try:
            today = self.get_closed_tickets_count("today", admin_id)
            week = self.get_closed_tickets_count("week", admin_id)
            month = self.get_closed_tickets_count("month", admin_id)
            active = self.get_active_tickets_count(admin_id)

            rating = self._get_admin_average_rating(admin_id)

            stats_text = "📊 <b>ВАША СТАТИСТИКА</b>\n\n"
            stats_text += f"🎫 <b>Активных тикетов:</b> {active}\n"
            stats_text += f"✅ <b>Закрыто сегодня:</b> {today}\n"
            stats_text += f"📅 <b>За неделю:</b> {week}\n"
            stats_text += f"📊 <b>За месяц:</b> {month}\n"

            if rating > 0:
                stars = "⭐" * int(rating)
                stats_text += f"🌟 <b>Средний рейтинг:</b> {rating:.1f} {stars}\n\n"
            else:
                stats_text += "🌟 <b>Рейтинг:</b> Нет оценок\n\n"

            if month >= 50:
                stats_text += "🏆 <i>Отличная работа! Вы в числе лучших!</i>"
            elif month >= 20:
                stats_text += "💪 <i>Хорошая работа! Продолжайте!</i>"
            elif month >= 5:
                stats_text += "👏 <i>Вы на верном пути!</i>"
            else:
                stats_text += "🚀 <i>Начните помогать пользователям!</i>"

            return stats_text
        except Exception as e:
            logger.error(f"Ошибка генерации текста статистики для администратора {admin_id}: {e}")
            return "❌ Ошибка загрузки статистики"

    def _get_admin_average_rating(self, admin_id: int) -> float:
        """Получить средний рейтинг администратора"""
        from App.Infrastructure.Models import TicketRating
        db = get_db()
        try:
            from sqlalchemy import func
            result = db.query(func.avg(TicketRating.rating).label("avg_rating")).filter(
                TicketRating.ticket_id.in_(
                    db.query(Ticket.id).filter(Ticket.taken_by == admin_id)
                )
            ).first()

            if result and result.avg_rating:
                return round(float(result.avg_rating), 1)
            return 0.0
        except Exception as e:
            logger.error(f"Ошибка получения среднего рейтинга для администратора {admin_id}: {e}")
            return 0.0
        finally:
            db.close()

    def get_admin_stats_by_username(self, username: str) -> dict:
        """Получить статистику администратора по username"""
        from App.Infrastructure.Models.database import get_db
        from App.Domain.Models.Ticket.Ticket import Ticket
        from datetime import datetime, timedelta

        db = get_db()
        try:
            return {}
        finally:
            db.close()
