import logging
import asyncio
from typing import Dict, List, Optional

from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate

logger = logging.getLogger(__name__)


class LongpollManager:
    def __init__(self):
        self._waiting_connections: Dict[int, List[asyncio.Queue]] = {}
        self._default_timeout = 30
        
    async def wait_for_update(self, ticket_id: int, timeout: int = None) -> Optional[TicketUpdate]:
        if timeout is None:
            timeout = self._default_timeout
            
        queue = asyncio.Queue()
        
        if ticket_id not in self._waiting_connections:
            self._waiting_connections[ticket_id] = []
        self._waiting_connections[ticket_id].append(queue)
        
        try:
            logger.info(f"Ожидание обновления для тикета {ticket_id}, timeout={timeout}")
            update = await asyncio.wait_for(queue.get(), timeout=timeout)
            logger.info(f"Получено обновление для тикета {ticket_id}: {update.status}")
            return update
        except asyncio.TimeoutError:
            logger.info(f"Таймаут ожидания обновления для тикета {ticket_id}")
            return None
        finally:
            if ticket_id in self._waiting_connections:
                try:
                    self._waiting_connections[ticket_id].remove(queue)
                    if not self._waiting_connections[ticket_id]:
                        del self._waiting_connections[ticket_id]
                except ValueError:
                    pass
    
    def notify_update(self, ticket_id: int, update: TicketUpdate):
        if ticket_id not in self._waiting_connections:
            return
            
        queues = self._waiting_connections[ticket_id].copy()
        logger.info(f"Отправка обновления для тикета {ticket_id} в {len(queues)} соединений")
        
        for queue in queues:
            try:
                queue.put_nowait(update)
            except Exception as e:
                logger.warning(f"Ошибка отправки обновления в очередь: {e}")
                try:
                    self._waiting_connections[ticket_id].remove(queue)
                except ValueError:
                    pass
        
        if ticket_id in self._waiting_connections and not self._waiting_connections[ticket_id]:
            del self._waiting_connections[ticket_id]
    
    def close_connections(self, ticket_id: int):
        if ticket_id in self._waiting_connections:
            queues = self._waiting_connections[ticket_id]
            for queue in queues:
                try:
                    queue.put_nowait(TicketUpdate(
                        ticket_id=ticket_id,
                        status="closed",
                        message="Тикет закрыт"
                    ))
                except Exception:
                    pass
            del self._waiting_connections[ticket_id]
            logger.info(f"Закрыты все соединения для тикета {ticket_id}")

