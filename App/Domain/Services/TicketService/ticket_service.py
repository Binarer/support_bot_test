import logging
from typing import Optional

from App.Domain.Models.Ticket.Ticket import Ticket
from App.Infrastructure.Components.TelegramBot.ChannelManager.channel_manager import ChannelManager
from App.Infrastructure.Config import config

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, channel_manager: ChannelManager, longpoll_manager=None):
        self.channel_manager = channel_manager
        self.longpoll_manager = longpoll_manager
        self.active_tickets: dict[int, Ticket] = {}
        self.ticket_by_message_id: dict[int, Ticket] = {}
        self.ticket_by_thread_id: dict[int, Ticket] = {}
        self._load_active_tickets()
        logger.info("TicketService инициализирован")

    def _load_active_tickets(self):
        """Загружает активные тикеты из базы данных при запуске"""
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            active_db_tickets = db.query(TicketModelDB).filter(
                TicketModelDB.status.in_(["pending", "in_progress"])
            ).all()

            for db_ticket in active_db_tickets:
                ticket = Ticket(
                    db_id=db_ticket.id,
                    display_id=db_ticket.display_id,
                    user_id=db_ticket.user_id,
                    username=db_ticket.username,
                    user_message=db_ticket.user_message,
                    category=db_ticket.category,
                    status=db_ticket.status,
                    channel_message_id=db_ticket.channel_message_id,
                    topic_thread_id=db_ticket.topic_thread_id
                )

                self.active_tickets[ticket.user_id] = ticket
                if ticket.channel_message_id:
                    self.ticket_by_message_id[ticket.channel_message_id] = ticket
                if ticket.topic_thread_id:
                    self.ticket_by_thread_id[ticket.topic_thread_id] = ticket

            logger.info(f"Загружено {len(active_db_tickets)} активных тикетов из базы данных")
        finally:
            db.close()

    async def create_ticket(self, user_id: int, username: str, user_message: str, category: str = "") -> Ticket:
        logger.info(f"Создание тикета для пользователя {user_id} с категорией {category}")

        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB
        from sqlalchemy import func

        db = get_db()
        try:
            max_display_id = db.query(func.max(TicketModelDB.display_id)).scalar() or 0
            display_id = max_display_id + 1

            db_ticket = TicketModelDB(
                display_id=display_id,
                user_id=user_id,
                username=username,
                user_message=user_message,
                category=category,
                status="pending"
            )
            db.add(db_ticket)
            db.commit()
            db.refresh(db_ticket)

            ticket = Ticket(
                db_id=db_ticket.id,
                display_id=db_ticket.display_id,
                user_id=user_id,
                username=username,
                user_message=user_message,
                category=category
            )
        finally:
            db.close()

        try:
            channel_message_id, topic_thread_id = await self.channel_manager.create_ticket_topic_and_thread(ticket)
            ticket.channel_message_id = channel_message_id
            ticket.topic_thread_id = topic_thread_id

            db = get_db()
            try:
                db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket.db_id).first()
                if db_ticket:
                    db_ticket.channel_message_id = channel_message_id
                    db_ticket.topic_thread_id = topic_thread_id
                    db.commit()
            finally:
                db.close()

            self.active_tickets[user_id] = ticket
            self.ticket_by_message_id[channel_message_id] = ticket
            if ticket.topic_thread_id:
                self.ticket_by_thread_id[ticket.topic_thread_id] = ticket
            
            if self.longpoll_manager:
                from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate
                self.longpoll_manager.notify_update(
                    ticket.db_id,
                    TicketUpdate(ticket_id=ticket.db_id, status="pending", message="Тикет создан")
                )
            
            logger.info(f"Тикет создан: {ticket.id}")
        except Exception as e:
            logger.error(f"Ошибка создания топика в канале: {e}")
            raise

        return ticket

    async def take_ticket(self, admin_id: int, admin_name: str, ticket_display_id: int) -> Optional[Ticket]:
        """Взять тикет администратором"""
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == ticket_display_id).first()
            if not db_ticket:
                logger.warning(f"Тикет с display_id {ticket_display_id} не найден в базе данных")
                return None

            if db_ticket.status != "pending":
                logger.warning(f"Тикет {ticket_display_id} уже взят или закрыт")
                return None

            from datetime import datetime
            db_ticket.taken_by = admin_id
            db_ticket.taken_at = datetime.utcnow()
            db_ticket.status = "in_progress"
            db.commit()

            ticket = Ticket(
                db_id=db_ticket.id,
                display_id=db_ticket.display_id,
                user_id=db_ticket.user_id,
                username=db_ticket.username,
                user_message=db_ticket.user_message,
                category=db_ticket.category,
                status=db_ticket.status,
                channel_message_id=db_ticket.channel_message_id
            )

            try:
                menu_message_id = await self.channel_manager.take_ticket_and_create_topic(
                    ticket, admin_id, admin_name
                )

                db_ticket.topic_thread_id = ticket.topic_thread_id
                db.commit()

                self.active_tickets[ticket.user_id] = ticket
                self.ticket_by_message_id[menu_message_id] = ticket
                if ticket.topic_thread_id:
                    self.ticket_by_thread_id[ticket.topic_thread_id] = ticket

                if self.longpoll_manager:
                    from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate
                    self.longpoll_manager.notify_update(
                        ticket.db_id,
                        TicketUpdate(ticket_id=ticket.db_id, status="in_progress", message="Тикет взят в работу")
                    )

                logger.info(f"Тикет {ticket_display_id} взят администратором {admin_name}")
                return ticket

            except Exception as e:
                logger.error(f"Ошибка взятия тикета {ticket_display_id}: {e}")
                db_ticket.status = "pending"
                db_ticket.taken_by = None
                db_ticket.taken_at = None
                db.commit()
                return None

        finally:
            db.close()

    async def has_active_ticket(self, user_id: int) -> bool:
        return user_id in self.active_tickets

    async def process_support_topic_message(self, thread_id: int, message):
        """Обрабатывает сообщение поддержки в топике тикета"""
        ticket = self.get_ticket_by_thread_id(thread_id)
        if not ticket:
            logger.warning(f"Тикет для thread_id {thread_id} не найден")
            return

        support_name = message.from_user.username or message.from_user.first_name or f"user_{message.from_user.id}"

        if message.content_type in ['photo', 'video', 'sticker', 'document', 'animation']:
            await self.channel_manager.send_support_media_reply(ticket.user_id, message)
        else:
            support_message = message.text or ""
            if support_message.strip():
                await self.channel_manager.send_support_reply(ticket.user_id, support_message, support_name)

        try:
            await self.channel_manager.update_topic_icon(ticket, "☑️")
        except Exception as e:
            logger.warning(f"Не удалось обновить иконку топика: {e}")

        logger.info(f"Сообщение поддержки обработано для тикета {ticket.id}")

    async def forward_user_message(self, user_id: int, message_text: str):
        if user_id not in self.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = self.active_tickets[user_id]

        if ticket.status == "in_progress":
            await self.channel_manager.send_user_message(ticket, message_text)
            await self.channel_manager.update_topic_icon(ticket, "❓")
            logger.info(f"Сообщение от пользователя {user_id}: {message_text}")
        else:
            logger.info(f"Сообщение от пользователя {user_id} игнорировано, тикет не взят: {message_text}")

    async def forward_user_media(self, user_id: int, message):
        """Пересылает медиа пользователя в топик тикета"""
        if user_id not in self.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = self.active_tickets[user_id]

        if ticket.status == "in_progress":
            await self.channel_manager.send_user_media(ticket, message)
            await self.channel_manager.update_topic_icon(ticket, "❓")
            logger.info(f"Медиа от пользователя {user_id}")
        else:
            logger.info(f"Медиа от пользователя {user_id} игнорировано, тикет не взят")

    async def process_support_message(self, message_id: int, support_message: str, support_name: str):
        """Обработка сообщения от поддержки"""
        if message_id not in self.ticket_by_message_id:
            logger.warning(f"Сообщение {message_id} не принадлежит ни одному тикету")
            return

        ticket = self.ticket_by_message_id[message_id]

        # Отправляем ответ пользователю
        await self.channel_manager.send_support_reply(
            ticket.user_id,
            support_message,
            support_name
        )

        await self.channel_manager.update_topic_icon(ticket, "☑️")
        logger.info(f"Ответ поддержки для тикета {ticket.id}")

    def get_ticket_by_message_id(self, message_id: int) -> Optional[Ticket]:
        return self.ticket_by_message_id.get(message_id)

    def get_ticket_by_thread_id(self, thread_id: int) -> Optional[Ticket]:
        return self.ticket_by_thread_id.get(thread_id)

    async def cancel_ticket(self, display_id: int, cancelled_by_admin: bool = False) -> bool:
        """Отменяет тикет по display_id"""
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.display_id == display_id).first()
            if not db_ticket:
                logger.warning(f"Тикет с display_id {display_id} не найден")
                return False

            if db_ticket.status == "closed":
                return False

            from datetime import datetime
            db_ticket.status = "cancelled"
            db_ticket.closed_at = datetime.utcnow()
            db.commit()

            user_id = db_ticket.user_id
            ticket = self.active_tickets.get(user_id)
            if not ticket:
                ticket = Ticket(
                    db_id=db_ticket.id,
                    display_id=db_ticket.display_id,
                    user_id=db_ticket.user_id,
                    username=db_ticket.username or f"user_{db_ticket.user_id}",
                    user_message=db_ticket.user_message or "",
                    category=db_ticket.category or "",
                    status=db_ticket.status,
                    channel_message_id=db_ticket.channel_message_id,
                    topic_thread_id=db_ticket.topic_thread_id
                )

            try:
                await self.channel_manager.notify_ticket_cancelled(ticket, cancelled_by_admin)
            except Exception as e:
                logger.warning(f"Не удалось уведомить об отмене тикета {ticket.display_id}: {e}")

            if user_id in self.active_tickets:
                del self.active_tickets[user_id]

            if ticket.channel_message_id in self.ticket_by_message_id:
                del self.ticket_by_message_id[ticket.channel_message_id]
            if ticket.topic_thread_id in self.ticket_by_thread_id:
                del self.ticket_by_thread_id[ticket.topic_thread_id]

            if ticket.topic_thread_id:
                try:
                    await self.channel_manager.bot.close_forum_topic(
                        chat_id=self.channel_manager.support_channel_id,
                        message_thread_id=ticket.topic_thread_id
                    )
                except Exception as e:
                    logger.warning(f"Не удалось закрыть топик для отмененного тикета: {e}")

            if self.longpoll_manager:
                from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate
                self.longpoll_manager.notify_update(
                    ticket.db_id,
                    TicketUpdate(ticket_id=ticket.db_id, status="cancelled", message="Тикет отменен")
                )
                self.longpoll_manager.close_connections(ticket.db_id)

            logger.info(f"Тикет {display_id} отменен")
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены тикета {display_id}: {e}")
            return False
        finally:
            db.close()

    async def close_ticket_by_internal_id(self, ticket_db_id: int, admin_id: int = None) -> bool:
        """Закрывает тикет по ID базы данных"""
        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket_db_id).first()
            if not db_ticket:
                logger.warning(f"Тикет с db_id {ticket_db_id} не найден")
                return False

            from datetime import datetime
            db_ticket.status = "closed"
            db_ticket.closed_at = datetime.utcnow()
            if admin_id:
                db_ticket.admin_id = admin_id
            db.commit()

            user_id = db_ticket.user_id
            if user_id in self.active_tickets:
                ticket = self.active_tickets[user_id]
                del self.active_tickets[user_id]

                if ticket.channel_message_id in self.ticket_by_message_id:
                    del self.ticket_by_message_id[ticket.channel_message_id]
                if ticket.topic_thread_id in self.ticket_by_thread_id:
                    del self.ticket_by_thread_id[ticket.topic_thread_id]

                try:
                    closed_text = "✅ Закрыт администратором" if admin_id else "✅ Закрыт"
                    await self.channel_manager.update_general_message(ticket, closed_text)
                except Exception as e:
                    logger.warning(f"Не удалось обновить общее сообщение для закрытого тикета {ticket.display_id}: {e}")
                await self.channel_manager.close_ticket_by_user(ticket)

            if self.longpoll_manager:
                from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate
                self.longpoll_manager.notify_update(
                    ticket_db_id,
                    TicketUpdate(ticket_id=ticket_db_id, status="closed", message="Тикет закрыт")
                )
                self.longpoll_manager.close_connections(ticket_db_id)

            logger.info(f"Тикет {ticket_db_id} закрыт")
            return True
        except Exception as e:
            logger.error(f"Ошибка закрытия тикета {ticket_db_id}: {e}")
            return False
        finally:
            db.close()

    async def close_ticket_by_user(self, user_id: int):
        """Закрывает тикет по ID пользователя (самостоятельное закрытие)"""
        if user_id not in self.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = self.active_tickets[user_id]
        username = ticket.username

        from App.Infrastructure.Models.database import get_db
        from App.Infrastructure.Models import Ticket as TicketModelDB

        db = get_db()
        try:
            db_ticket = db.query(TicketModelDB).filter(TicketModelDB.id == ticket.db_id).first()
            if db_ticket:
                from datetime import datetime
                db_ticket.status = "closed"
                db_ticket.closed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

        del self.active_tickets[user_id]

        if ticket.channel_message_id in self.ticket_by_message_id:
            del self.ticket_by_message_id[ticket.channel_message_id]
        if ticket.topic_thread_id in self.ticket_by_thread_id:
            del self.ticket_by_thread_id[ticket.topic_thread_id]

        await self.channel_manager.close_ticket_by_user(ticket)
        
        if self.longpoll_manager:
            from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate
            self.longpoll_manager.notify_update(
                ticket.db_id,
                TicketUpdate(ticket_id=ticket.db_id, status="closed", message="Тикет закрыт пользователем")
            )
            self.longpoll_manager.close_connections(ticket.db_id)
        
        logger.info(f"Тикет {ticket.id} закрыт пользователем {username}")
