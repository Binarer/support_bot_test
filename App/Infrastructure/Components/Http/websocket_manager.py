import logging
import json
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self, channel_manager=None):
        
        self._active_connections: Dict[int, Set[WebSocket]] = {}
        
        self._connection_info: Dict[WebSocket, tuple[int, int]] = {}
        self.channel_manager = channel_manager
        
    
    async def disconnect(self, websocket: WebSocket):
        """Отключить WebSocket клиента"""
        if websocket not in self._connection_info:
            return
        
        ticket_id, user_id = self._connection_info[websocket]
        
        if ticket_id in self._active_connections:
            self._active_connections[ticket_id].discard(websocket)
            if not self._active_connections[ticket_id]:
                del self._active_connections[ticket_id]
        
        del self._connection_info[websocket]
        logger.info(f"WebSocket отключен для тикета {ticket_id}, пользователь {user_id}")
    
    async def notify_update(self, ticket_id: int, update: TicketUpdate):
        """Отправить обновление всем подключенным клиентам тикета"""
        if ticket_id not in self._active_connections:
            return
        
        connections = self._active_connections[ticket_id].copy()
        logger.info(f"Отправка обновления для тикета {ticket_id} в {len(connections)} WebSocket соединений")
        
        message = {
            "type": "update",
            "ticket_id": update.ticket_id,
            "status": update.status,
            "message": update.message,
            "timestamp": update.timestamp.isoformat() if update.timestamp else None
        }
        
        disconnected = []
        for websocket in connections:
            try:
                await self._send_json(websocket, message)
            except Exception as e:
                logger.warning(f"Ошибка отправки обновления в WebSocket: {e}")
                disconnected.append(websocket)
        
        
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def close_connections(self, ticket_id: int, message: str = "Тикет закрыт"):
        """Закрыть все соединения для тикета"""
        if ticket_id not in self._active_connections:
            return
        
        connections = self._active_connections[ticket_id].copy()
        logger.info(f"Закрытие {len(connections)} WebSocket соединений для тикета {ticket_id}")
        
        close_message = {
            "type": "ticket_closed",
            "ticket_id": ticket_id,
            "message": message
        }
        
        for websocket in connections:
            try:
                await self._send_json(websocket, close_message)
                await websocket.close()
            except Exception:
                pass
            finally:
                await self.disconnect(websocket)
    
    async def _send_json(self, websocket: WebSocket, data: dict):
        """Отправить JSON сообщение через WebSocket"""
        await websocket.send_text(json.dumps(data, ensure_ascii=False))
    
    async def handle_websocket(self, websocket: WebSocket, ticket_id: int):
        """Обработать WebSocket соединение"""
        
        await websocket.accept()
        
        try:
            
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(f"WebSocket отключен до получения сообщения подписки для тикета {ticket_id}")
                return
            try:
                message = json.loads(data)
                if message.get("type") != "subscribe":
                    await self._send_json(websocket, {
                        "type": "error",
                        "message": "Ожидается сообщение типа 'subscribe'"
                    })
                    await websocket.close()
                    return
                
                subscribe_ticket_id = message.get("ticket_id")
                user_id = message.get("user_id")
                
                if subscribe_ticket_id != ticket_id:
                    await self._send_json(websocket, {
                        "type": "error",
                        "message": f"ticket_id в сообщении ({subscribe_ticket_id}) не совпадает с ticket_id в URL ({ticket_id})"
                    })
                    await websocket.close()
                    return
                
                if not user_id:
                    await self._send_json(websocket, {
                        "type": "error",
                        "message": "user_id обязателен в сообщении подписки"
                    })
                    await websocket.close()
                    return
                
                
                if ticket_id not in self._active_connections:
                    self._active_connections[ticket_id] = set()

                self._active_connections[ticket_id].add(websocket)
                self._connection_info[websocket] = (ticket_id, user_id)

                logger.info(f"WebSocket подключен для тикета {ticket_id}, пользователь {user_id}")

                
                await self._send_json(websocket, {
                    "type": "connected",
                    "ticket_id": ticket_id,
                    "message": "Подключение установлено"
                })
                
                
                while True:
                    try:
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        
                        
                        if message.get("type") == "ping":
                            await self._send_json(websocket, {
                                "type": "pong",
                                "ticket_id": ticket_id
                            })
                        
                        elif message.get("type") == "message":
                            await self._handle_client_message(ticket_id, user_id, message)
                        elif message.get("type") == "media":
                            await self._handle_client_media(ticket_id, user_id, message)
                        
                        
                    except WebSocketDisconnect:
                        break
                    except json.JSONDecodeError:
                        await self._send_json(websocket, {
                            "type": "error",
                            "message": "Неверный формат JSON"
                        })
                        
            except json.JSONDecodeError:
                await self._send_json(websocket, {
                    "type": "error",
                    "message": "Неверный формат JSON в сообщении подписки"
                })
                await websocket.close()
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket отключен для тикета {ticket_id}")
        except Exception as e:
            logger.error(f"Ошибка обработки WebSocket для тикета {ticket_id}: {e}", exc_info=True)
        finally:
            await self.disconnect(websocket)

    async def _handle_client_message(self, ticket_id: int, user_id: int, message_data: dict):
        """Обработка текстового сообщения от клиента"""
        from App.Domain.Services.TicketService.ticket_service import TicketService

        ticket_service = TicketService(self.channel_manager, self)  

        
        message_text = message_data.get("message", "").strip()
        if not message_text:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Пустое сообщение"
            })
            return

        try:
            success = await ticket_service.forward_user_message(user_id, message_text)
            if success:
                await self._send_json_by_ticket(ticket_id, {
                    "type": "message_sent",
                    "message": "Сообщение отправлено"
                })
            else:
                await self._send_json_by_ticket(ticket_id, {
                    "type": "error",
                    "message": "Не удалось отправить сообщение"
                })
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователем {user_id}: {e}")
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Ошибка отправки сообщения"
            })

    async def _handle_client_media(self, ticket_id: int, user_id: int, message_data: dict):
        """Обработка медиа-сообщения от клиента"""
        import aiohttp
        import base64
        from App.Domain.Services.TicketService.ticket_service import TicketService

        media_type = message_data.get("media_type")
        media_url = message_data.get("media_url")
        media_data_b64 = message_data.get("media_data")
        media_caption = message_data.get("media_caption", "")
        media_filename = message_data.get("filename")

        if not media_type:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Не указан тип медиа"
            })
            return

        if not media_url and not media_data_b64:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Укажите media_url или media_data"
            })
            return

        if media_type not in ["photo", "video", "document"]:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Неподдерживаемый тип медиа. Допустимые: photo, video, document"
            })
            return

        try:
            media_binary_data = None
            filename = media_filename or "media_file"

            
            if media_data_b64:
                if not media_filename:
                    await self._send_json_by_ticket(ticket_id, {
                        "type": "error",
                        "message": "filename обязателен при использовании media_data"
                    })
                    return

                try:
                    
                    if media_data_b64.startswith('data:'):
                        media_data_b64 = media_data_b64.split(',')[1]

                    media_binary_data = base64.b64decode(media_data_b64)
                    logger.info(f"Декодирован base64 файл {filename}, размер: {len(media_binary_data)} байт")
                except Exception as decode_error:
                    logger.error(f"Ошибка декодирования base64: {decode_error}")
                    await self._send_json_by_ticket(ticket_id, {
                        "type": "error",
                        "message": "Неверный формат base64 данных"
                    })
                    return

            
            elif media_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(media_url) as response:
                        if response.status != 200:
                            await self._send_json_by_ticket(ticket_id, {
                                "type": "error",
                                "message": "Не удалось скачать медиа файл"
                            })
                            return

                        media_binary_data = await response.read()
                        logger.info(f"Скачан файл по URL {media_url}, размер: {len(media_binary_data)} байт")

            
            ticket_service = TicketService(self.channel_manager, self)
            await self._send_media_to_support(ticket_service, user_id, media_type, media_binary_data, filename, media_caption)

            await self._send_json_by_ticket(ticket_id, {
                "type": "media_sent",
                "message": f"Медиа ({media_type}) отправлено"
            })

        except Exception as e:
            logger.error(f"Ошибка отправки медиа пользователем {user_id}: {e}")
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Ошибка отправки медиа"
            })

    async def _send_media_to_support(self, ticket_service: 'TicketService', user_id: int, media_type: str, media_data: bytes, filename: str, caption: str):
        """Отправка медиа в поддержку через Telegram бот"""
        from io import BytesIO
        from aiogram.types import BufferedInputFile
        from App.Domain.Models.Ticket.Ticket import Ticket

        
        if user_id not in ticket_service.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = ticket_service.active_tickets[user_id]

        try:
            
            buffered_file = BufferedInputFile(media_data, filename=filename)

            
            if media_type == "photo":
                message = await ticket_service.channel_manager.bot.send_photo(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    photo=buffered_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )
            elif media_type == "video":
                message = await ticket_service.channel_manager.bot.send_video(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    video=buffered_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )
            elif media_type == "document":
                message = await ticket_service.channel_manager.bot.send_document(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    document=buffered_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )

            logger.info(f"Медиа {filename} типа {media_type} отправлено в топик тикета 
            print(f"DEBUG: Медиа {filename} отправлено в Telegram как {media_type}")

            
            if ticket.status == "in_progress":
                await ticket_service.channel_manager.update_topic_icon(ticket, "❓")

        except Exception as e:
            logger.error(f"Ошибка отправки медиа в Telegram: {e}")
            print(f"DEBUG: Ошибка отправки медиа: {e}")
            raise

    async def _send_json_by_ticket(self, ticket_id: int, data: dict):
        """Отправить JSON сообщение всем websocket соединениям тикета"""
        if ticket_id not in self._active_connections:
            return

        connections = self._active_connections[ticket_id].copy()
        for websocket in connections:
            try:
                await self._send_json(websocket, data)
            except Exception as e:
                logger.warning(f"Ошибка отправки JSON через WebSocket: {e}")

    async def send_support_message_to_client(self, ticket_id: int, message_text: str, support_name: str):
        """Отправить текстовое сообщение поддержки клиенту через websocket"""
        message_data = {
            "type": "support_message",
            "message": message_text,
            "support_name": support_name,
            "timestamp": str(datetime.now())
        }
        await self._send_json_by_ticket(ticket_id, message_data)

    async def send_support_media_to_client(self, ticket_id: int, media_type: str, media_url: str, filename: str, caption: str, support_name: str):
        """Отправить медиа поддержки клиенту через websocket"""
        message_data = {
            "type": "support_media",
            "media_type": media_type,
            "media_url": media_url,
            "filename": filename,
            "caption": caption,
            "support_name": support_name,
            "timestamp": str(datetime.now())
        }
        await self._send_json_by_ticket(ticket_id, message_data)

    async def send_support_media_base64_to_client(self, ticket_id: int, media_type: str, base64_data: str, filename: str, caption: str, support_name: str):
        """Отправить медиа поддержки клиенту через websocket в base64 формате"""
        message_data = {
            "type": "support_media_base64",
            "media_type": media_type,
            "media_data": base64_data,
            "filename": filename,
            "caption": caption,
            "support_name": support_name,
            "timestamp": str(datetime.now())
        }
        await self._send_json_by_ticket(ticket_id, message_data)
