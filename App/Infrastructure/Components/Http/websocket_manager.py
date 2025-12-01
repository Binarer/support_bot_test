import logging
import json
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

from App.Domain.Models.TicketUpdate.TicketUpdate import TicketUpdate

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        # ticket_id -> Set[WebSocket]
        self._active_connections: Dict[int, Set[WebSocket]] = {}
        # WebSocket -> (ticket_id, user_id)
        self._connection_info: Dict[WebSocket, tuple[int, int]] = {}
        
    
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
        
        # Удаляем отключенные соединения
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
        # Принимаем соединение сразу
        await websocket.accept()
        
        try:
            # Ожидаем сообщение подписки
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
                
                # Подключаем клиента (регистрируем в менеджере)
                if ticket_id not in self._active_connections:
                    self._active_connections[ticket_id] = set()
                
                self._active_connections[ticket_id].add(websocket)
                self._connection_info[websocket] = (ticket_id, user_id)
                
                logger.info(f"WebSocket подключен для тикета {ticket_id}, пользователь {user_id}")
                
                # Отправляем подтверждение подключения
                await self._send_json(websocket, {
                    "type": "connected",
                    "ticket_id": ticket_id,
                    "message": "Подключение установлено"
                })
                
                # Ожидаем сообщения от клиента (можно использовать для ping/pong или других команд)
                while True:
                    try:
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        
                        # Обработка ping/pong
                        if message.get("type") == "ping":
                            await self._send_json(websocket, {
                                "type": "pong",
                                "ticket_id": ticket_id
                            })
                        # Обработка сообщений от клиента
                        elif message.get("type") == "message":
                            await self._handle_client_message(ticket_id, user_id, message)
                        elif message.get("type") == "media":
                            await self._handle_client_media(ticket_id, user_id, message)
                        # Можно добавить другие типы сообщений здесь
                        
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

        ticket_service = TicketService(self)  # Initialize ticket service

        # Получаем текст сообщения
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
        from App.Domain.Services.TicketService.ticket_service import TicketService
        import aiohttp

        media_type = message_data.get("media_type")
        media_url = message_data.get("media_url")
        media_caption = message_data.get("media_caption", "")

        if not media_type or not media_url:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Не указан тип медиа или URL"
            })
            return

        if media_type not in ["photo", "video", "document"]:
            await self._send_json_by_ticket(ticket_id, {
                "type": "error",
                "message": "Неподдерживаемый тип медиа. Допустимые: photo, video, document"
            })
            return

        try:
            # Скачиваем медиа и отправляем в Telegram
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url) as response:
                    if response.status != 200:
                        await self._send_json_by_ticket(ticket_id, {
                            "type": "error",
                            "message": "Не удалось скачать медиа файл"
                        })
                        return

                    media_data = await response.read()
                    media_filename = message_data.get("filename", "media_file")

                    # Используем ChannelManager для отправки медиа
                    ticket_service = TicketService(self)
                    await self._send_media_to_support(ticket_service, user_id, media_type, media_data, media_filename, media_caption)

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
        import tempfile
        import os
        from aiogram.types import InputFile
        from App.Domain.Models.Ticket.Ticket import Ticket

        # Получаем активный тикет пользователя
        if user_id not in ticket_service.active_tickets:
            raise ValueError("У пользователя нет активного тикета")

        ticket = ticket_service.active_tickets[user_id]

        # Сохраняем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1] if '.' in filename else '') as temp_file:
            temp_file.write(media_data)
            temp_file_path = temp_file.name

        try:
            # Создаем InputFile для aiogram
            input_file = InputFile(temp_file_path, filename=filename)

            # Отправляем в зависимости от типа медиа
            if media_type == "photo":
                message = await ticket_service.channel_manager.bot.send_photo(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    photo=input_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )
            elif media_type == "video":
                message = await ticket_service.channel_manager.bot.send_video(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    video=input_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )
            elif media_type == "document":
                message = await ticket_service.channel_manager.bot.send_document(
                    chat_id=ticket_service.channel_manager.support_channel_id,
                    document=input_file,
                    caption=caption,
                    message_thread_id=ticket.topic_thread_id
                )

            # Обновляем иконку топика
            if ticket.status == "in_progress":
                await ticket_service.channel_manager.update_topic_icon(ticket, "❓")

        finally:
            # Удаляем временный файл
            os.unlink(temp_file_path)

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
