# bot.py 

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, exceptions, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

# Импорты для работы с PostgreSQL
import db_operations as db
# Инициализация БД временно отключена - таблицы созданы вручную
# from init_db import init_db as init_database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1003432522708"))
# DB_PATH больше не используется, используем переменные окружения для PostgreSQL
# Список ID администраторов (можно расширить или получать динамически из группы)
ADMIN_IDS = []  # Будет заполняться динамически при проверке прав

# Validate token before creating bot
if not TG_TOKEN:
    logger.error("TG_BOT_TOKEN is not set in environment variables!")
    logger.error("Please check your .env file or set TG_BOT_TOKEN environment variable.")
    raise ValueError("TG_BOT_TOKEN is required!")

logger.info(f"Loaded token: {TG_TOKEN[:10]}...")
logger.info(f"ADMIN_GROUP_ID: {ADMIN_GROUP_ID}")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------- DB Functions импортированы из db_operations ----------

async def get_admin_display_name(admin_id):
    """Получить отображаемое имя администратора (username или user_id)"""
    try:
        user = await bot.get_chat(admin_id)
        if user.username:
            return f"@{user.username}"
        else:
            return f"user_{admin_id}"
    except Exception:
        return f"user_{admin_id}"

async def is_admin(user_id):
    """Проверить, является ли пользователь администратором"""
    try:
        member = await bot.get_chat_member(ADMIN_GROUP_ID, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def ask_for_rating(user_id: int, ticket_number: int):
    """Запрос оценки от пользователя"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1⭐", callback_data=f"rate:{ticket_number}:1"),
                    InlineKeyboardButton(text="2⭐", callback_data=f"rate:{ticket_number}:2"),
                    InlineKeyboardButton(text="3⭐", callback_data=f"rate:{ticket_number}:3"),
                    InlineKeyboardButton(text="4⭐", callback_data=f"rate:{ticket_number}:4"),
                    InlineKeyboardButton(text="5⭐", callback_data=f"rate:{ticket_number}:5"),
                ]
            ]
        )

        await bot.send_message(
            user_id,
            "Пожалуйста, оцените работу поддержки:",
            reply_markup=keyboard
        )
        logger.info(f"Отправлен запрос оценки для тикета #{ticket_number} пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса оценки: {e}", exc_info=True)

# ---------- FSM states ----------

class RenameState(StatesGroup):
    waiting_for_new_name = State()

class RatingState(StatesGroup):
    waiting_for_comment = State()

# ---------- Helpers ----------

def user_ticket_message(number, category):
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = (
        f"🎫 <b>Ваш Тикет №{number}</b>\n\n"
        f"🛠 Услуга: <b>{category}</b>\n\n"
        f"🕒 Создана: {created}\n\n"
        "Ожидайте принятия вашего запроса. После того, как заявка будет принята, опишите Вашу проблему и предоставьте требуемую информацию.\n\n"
        "Среднее время ответа агента поддержки:\n"
        "• До 60 минут в прайм-тайм\n"
        "• До 30 минут в остальное время\n"
    )
    return text

def admin_notify_text(number, username, user_mention, category):
    """Форматирует текст уведомления для администраторов о новом тикете"""
    # Если username пустой, используем user_id из user_mention
    if not username:
        # Извлекаем user_id из user_mention (формат: <a href='tg://user?id=123456'>Name</a>)
        import re
        user_id_match = re.search(r"id=(\d+)", str(user_mention))
        if user_id_match:
            display_username = f"user_{user_id_match.group(1)}"
        else:
            display_username = "user_unknown"
    else:
        display_username = username
    
    return (
        f"📥 Поступил новый тикет #{number}\n\n"
        f"👤 Никнейм: <b>{display_username}</b>\n"
        f"🔗 Пользователь: {user_mention}\n"
        f"🗂 Категория: <b>{category}</b>\n\n"
    )

# ---------- Keyboards ----------

user_categories_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Техническая помощь", callback_data="cat:tech")],
    [InlineKeyboardButton(text="Помощь с платежами", callback_data="cat:pay")],
    [InlineKeyboardButton(text="Получить ключ", callback_data="cat:key")],
    [InlineKeyboardButton(text="Сбросить HWID", callback_data="cat:hwid")]
])

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отменить", callback_data="cancel_ticket")]
])

def admin_take_kb(number):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Взять в работу", callback_data=f"take:{number}")]
    ])

# Функция для создания inline-клавиатуры управления тикетом
def ticket_admin_keyboard(ticket_number):
    """Создает inline-клавиатуру для управления тикетом"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Закрыть тикет", callback_data=f"close_{ticket_number}"),
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{ticket_number}")
        ]
    ])

def rating_keyboard(ticket_number: int):
    """Создаёт клавиатуру с 5 кнопками для оценки тикета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("1 ⭐", callback_data=f"rate_{ticket_number}_1"),
            InlineKeyboardButton("2 ⭐", callback_data=f"rate_{ticket_number}_2"),
            InlineKeyboardButton("3 ⭐", callback_data=f"rate_{ticket_number}_3"),
            InlineKeyboardButton("4 ⭐", callback_data=f"rate_{ticket_number}_4"),
            InlineKeyboardButton("5 ⭐", callback_data=f"rate_{ticket_number}_5"),
        ],
        [
            InlineKeyboardButton("Добавить комментарий", callback_data=f"rate_comment:{ticket_number}")
        ]
    ])
    return keyboard

# ---------- Handlers ----------

@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    logger.info("Received /start from user %s (%s)", message.from_user.id, message.from_user.username)
    
    try:
        # Проверяем, является ли пользователь администратором
        is_user_admin = await is_admin(message.from_user.id)
        is_in_group = message.chat.type in ("group", "supergroup")
        
        # Если админ (в группе или в личке) - показываем только меню
        if is_user_admin:
            # Определяем время суток для приветствия
            hour = datetime.now().hour
            if 5 <= hour < 12:
                greeting = "Доброе утро ☀️"
            elif 12 <= hour < 18:
                greeting = "Добрый день 🌤"
            else:
                greeting = "Добрый вечер 🌙"
            
            # Подсчет активных тикетов для этого администратора
            active_tickets = await db.get_active_tickets_count(admin_id=message.from_user.id)
            
            text = (
                f"{greeting}, {message.from_user.full_name}!\n\n"
                f"У вас <b>{active_tickets}</b> тикета(ов) в работе."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
                    InlineKeyboardButton(text="💰 Баланс", callback_data="show_balance")
                ]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            logger.info("Sent admin menu to user %s", message.from_user.id)
            
            # Если в группе - показываем лучшего администратора
            if is_in_group:
                best_admin_id, closed_count = await db.get_best_admin_by_stats()
                if best_admin_id:
                    admin_name = await get_admin_display_name(best_admin_id)
                    best_admin_text = (
                        f"\n\n🏆 <b>Лучший администратор месяца:</b>\n"
                        f"👤 {admin_name}\n"
                        f"📊 Закрыто тикетов: <b>{closed_count}</b>"
                    )
                    await message.answer(best_admin_text, parse_mode="HTML")
        else:
            # Для обычных пользователей - показываем полное приветствие с категориями
            text = (
                "👋 Привет, я бот поддержки наших сайтов. Через меня вы можете связаться с администрацией сайта и задать интересующие вас вопросы.\n\n"
                "Чтобы начать, выберите нужный вам вопрос в этом чате, тикет будет создан автоматически.\n\n"
                "⚠️ Иногда мы можем не сразу вам ответить, так как у нас много тикетов и мы стараемся ответить всем как можно быстрее,\n\n"
                "Если вы не нашли ответ на свой вопрос в документации на сайте, пожалуйста, после создания тикета подождите ответа от нашей службы поддержки и не пишите повторно в этот чат,\n\n"
                "⏰ Рабочее время службы поддержки: с 10:00 до 23:00 по MSK (UTC+3)"
            )
            await message.answer(text, reply_markup=user_categories_kb, parse_mode="HTML")
            logger.info("Successfully sent start message to user %s", message.from_user.id)
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при обработке команды. Попробуйте позже.")
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")

@dp.callback_query(F.data == "open_menu")
async def open_menu_callback(cb: types.CallbackQuery):
    """Обработчик кнопки 'Меню' из стартового сообщения"""
    await cb.answer()
    
    # Проверяем права администратора
    if not await is_admin(cb.from_user.id):
        await cb.answer("❌ Только администраторы могут использовать меню.", show_alert=True)
        return
    
    # Определяем время суток для приветствия
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Доброе утро ☀️"
    elif 12 <= hour < 18:
        greeting = "Добрый день 🌤"
    else:
        greeting = "Добрый вечер 🌙"
    
    # Подсчет активных тикетов для этого администратора
    active_tickets = await db.get_active_tickets_count(admin_id=cb.from_user.id)
    
    text = (
        f"{greeting}, {cb.from_user.full_name}!\n\n"
        f"У вас <b>{active_tickets}</b> тикета(ов) в работе."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="show_balance")
        ]
    ])
    
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command(commands=["clear"]))
async def clear_general(message: types.Message):
    """Очистка General чата (только для админов)"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Только администраторы могут использовать эту команду.")
        return
    
    if message.chat.type == "private":
        await message.answer("❌ Эта команда работает только в группах.")
        return
    
    chat_id = message.chat.id
    deleted_count = 0
    current_id = message.message_id
    
    try:
        # Удаляем сообщения в обратном порядке (начиная с текущего и идя назад)
        # Ограничиваем 100 сообщениями для безопасности
        for i in range(100):
            msg_id = current_id - i
            if msg_id <= 0:
                break
            try:
                await bot.delete_message(chat_id, msg_id)
                deleted_count += 1
            except Exception:
                # Сообщение уже удалено или не существует
                pass
        
        # Отправляем ответ в новом сообщении (после очистки)
        await message.answer(f"🧹 Чат очищен. Удалено сообщений: {deleted_count}")
    except Exception as e:
        logger.error(f"Error clearing chat: {e}")
        await message.answer("❌ Ошибка при очистке чата.")

@dp.message(Command(commands=["menu"]))
async def menu_handler(message: types.Message):
    """Меню с статистикой и балансом"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Только администраторы могут использовать эту команду.")
        return
    
    # Определяем время суток для приветствия
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Доброе утро ☀️"
    elif 12 <= hour < 18:
        greeting = "Добрый день 🌤"
    else:
        greeting = "Добрый вечер 🌙"
    
    # Подсчет активных тикетов для этого администратора
    active_tickets = await db.get_active_tickets_count(admin_id=message.from_user.id)
    
    text = (
        f"{greeting}, {message.from_user.full_name}!\n\n"
        f"У вас <b>{active_tickets}</b> тикета(ов) в работе."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="show_balance")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "show_stats")
async def show_stats(cb: types.CallbackQuery):
    """Показать статистику обработки тикетов для конкретного администратора"""
    await cb.answer()
    
    admin_id = cb.from_user.id
    today = await db.get_closed_tickets_count("today", admin_id=admin_id)
    week = await db.get_closed_tickets_count("week", admin_id=admin_id)
    month = await db.get_closed_tickets_count("month", admin_id=admin_id)
    active = await db.get_active_tickets_count(admin_id=admin_id)
    
    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"Активных тикетов: <b>{active}</b>\n"
        f"Обработано за сегодня: <b>{today}</b>\n"
        f"Обработано за неделю: <b>{week}</b>\n"
        f"Обработано за месяц: <b>{month}</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ])
    
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "show_balance")
async def show_balance(cb: types.CallbackQuery):
    """Показать баланс администратора"""
    await cb.answer()
    
    balance = await db.get_admin_balance(cb.from_user.id)
    text = f"💰 Ваш баланс: <b>{balance:.2f}</b> ₽"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ])
    
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "back_menu")
async def back_to_menu(cb: types.CallbackQuery):
    """Вернуться в главное меню"""
    await cb.answer()
    
    # Определяем время суток для приветствия
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Доброе утро ☀️"
    elif 12 <= hour < 18:
        greeting = "Добрый день 🌤"
    else:
        greeting = "Добрый вечер 🌙"
    
    # Подсчет активных тикетов для этого администратора
    active_tickets = await db.get_active_tickets_count(admin_id=cb.from_user.id)
    
    text = (
        f"{greeting}, {cb.from_user.full_name}!\n\n"
        f"У вас <b>{active_tickets}</b> тикета(ов) в работе."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="show_balance")
        ]
    ])
    
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat:"))
async def category_selected(cb: types.CallbackQuery):
    await cb.answer()
    
    # Проверяем, не является ли пользователь администратором
    if await is_admin(cb.from_user.id):
        await cb.answer("❌ Администраторы не могут создавать тикеты. Используйте /menu для просмотра статистики.", show_alert=True)
        return
    
    category_code = cb.data.split(":")[1]
    mapping = {"tech": "Техническая помощь", "pay": "Помощь с платежами", "key": "Получить ключ", "hwid": "Сбросить HWID"}
    category = mapping.get(category_code, "Другое")

    number = await db.get_next_ticket_number()
    external_id = None
    # Используем username или user_id для сохранения в БД
    username_for_db = cb.from_user.username if cb.from_user.username else f"user_{cb.from_user.id}"
    ticket_id = await db.create_ticket_record(number, "telegram", external_id, cb.from_user.id, username_for_db, category, "")
    text = user_ticket_message(number, category)
    await bot.send_message(cb.from_user.id, text, reply_markup=cancel_kb, parse_mode="HTML")

    user_mention = f"@{cb.from_user.username}" if cb.from_user.username else f"<a href='tg://user?id={cb.from_user.id}'>{cb.from_user.full_name}</a>"
    admin_text = admin_notify_text(number, username_for_db, user_mention, category)
    try:
        await bot.send_message(ADMIN_GROUP_ID, admin_text, reply_markup=admin_take_kb(number), parse_mode="HTML")
    except exceptions.TelegramBadRequest as e:
        logger.error("Error sending to admin group: %s", e)

@dp.callback_query(F.data == "cancel_ticket")
async def cancel_ticket(cb: types.CallbackQuery):
    await cb.answer("Тикет отменён.")
    # find last ticket for user and mark closed if exists and no topic
    t = await db.get_last_ticket_for_user(cb.from_user.id)
    if t:
        ticket_id = t.id; number = t.number; status = t.status; topic = t.topic_id
        if status != "closed":
            if topic:
                # if topic exists, try remove topic
                try:
                    await bot.delete_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=topic)
                except Exception:
                    try:
                        await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=topic)
                    except Exception:
                        logger.warning("Couldn't delete/close topic on cancel")
            await db.close_ticket_by_number(number)
    # remove cancel button
    try:
        await cb.message.edit_reply_markup(None)
    except Exception:
        pass

@dp.callback_query(F.data.startswith("take:"))
async def admin_take(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    admin_id = cb.from_user.id
    try:
        member = await bot.get_chat_member(ADMIN_GROUP_ID, admin_id)
        if not (member.status in ("administrator", "creator")):
            await cb.message.answer("Только администраторы могут брать тикеты в работу.")
            return
    except Exception as exc:
        logger.warning("couldn't check admin: %s", exc)

    number = int(cb.data.split(":")[1])
    ticket = await db.get_ticket_by_number(number)
    if not ticket:
        await cb.answer("Тикет не найден.")
        return

    ticket_id = ticket.id
    user_id = ticket.user_id
    username = ticket.username or str(user_id)
    category = ticket.category

    topic_name = f"#{username} (Telegram)"
    try:
        # create forum topic
        try:
            res = await bot.create_forum_topic(chat_id=ADMIN_GROUP_ID, name=topic_name)
            topic_id = res.message_thread_id
        except Exception:
            payload = {"chat_id": ADMIN_GROUP_ID, "name": topic_name}
            res = await bot.request.post("createForumTopic", data=payload)
            topic_id = int(res.result.get("message_thread_id"))
    except Exception as e:
        logger.exception("Failed to create forum topic: %s", e)
        await cb.message.answer("Ошибка создания темы. Проверьте, что бот админ и поддерживает создание тем.")
        return

    await db.set_ticket_topic(ticket_id, topic_id, admin_id=admin_id)

    # --- красивое сообщение в тему для админа ---
    admin_name = cb.from_user.full_name
    menu_message = (
        "╔══════════════╗\n"
        "      🛠 MENU 🛠      \n"
        "╚══════════════╝\n\n"
        f"📌 Тикет #{number} взят в работу администратором <b>{admin_name}</b>\n\n"
        "Используйте кнопки ниже для управления тикетом:"
    )
    
    try:
        await bot.send_message(
            ADMIN_GROUP_ID,
            menu_message,
            parse_mode="HTML",
            message_thread_id=topic_id,
            reply_markup=ticket_admin_keyboard(number)
        )
    except Exception as e:
        logger.exception("Error sending to topic: %s", e)
        await cb.message.answer("Ошибка отправки сообщения в тему.")
        return

    # --- отправка полной инструкции пользователю ---
    user_instruction = (
        "Приветствую!\n\n"
        "Чтобы мы могли вам помочь, предоставьте информацию по форме:\n\n"
        "<b>1. Скриншот, подтверждающий покупку в нашем магазине:</b>\n"
        "- зайдите на сайт oplata.info\n"
        "- впишите почту которую вы указывали при покупке\n"
        "- выберите нужную покупку\n"
        "- сделайте скриншот (ключ должно быть видно на скриншоте)\n"
        "- пришлите ключ в текстовом формате\n\n"
        "<b>2. Нажмите Win + R и введите:</b>\n"
        "<code>msinfo32</code>\n"
        "- Нажмите Enter\n"
        "- Пришлите скриншот всего окна в этот чат-бот\n\n"
        "<b>3. Нажмите Win + R и введите:</b>\n"
        "<code>winver</code>\n"
        "- Нажмите Enter\n"
        "- Пришлите скриншот окна в этот чат-бот\n\n"
        "<b>4. Опишите подробно проблему.</b>\n"
        "При наличии ошибок — предоставьте скриншот или видео полной проблемы."
    )

    try:
        await bot.send_message(user_id, user_instruction, parse_mode="HTML")
    except Exception as e:
        logger.warning("Could not send instruction to user: %s", e)

    try:
        await cb.message.edit_text(cb.message.text + f"\n\n🔧 Взял в работу: {cb.from_user.full_name}")
        await cb.message.edit_reply_markup(None)
    except Exception:
        pass

    await cb.answer("Тикет переведён в тему.")

# Обработчики inline-кнопок для управления тикетом

@dp.callback_query(F.data.startswith("close_"))
async def close_ticket_callback(cb: types.CallbackQuery):
    """Обработчик кнопки 'Закрыть тикет'"""
    await cb.answer()
    
    # Проверка прав админа
    try:
        member = await bot.get_chat_member(ADMIN_GROUP_ID, cb.from_user.id)
        if member.status not in ("administrator", "creator"):
            await cb.answer("Только администраторы могут закрывать тикеты.", show_alert=True)
            return
    except Exception as exc:
        logger.warning("Couldn't check admin status: %s", exc)
    
    # Получаем номер тикета из callback_data
    ticket_number = int(cb.data.split("_")[1])
    ticket = await db.get_ticket_by_number(ticket_number)
    
    if not ticket:
        await cb.answer("Тикет не найден.", show_alert=True)
        return
    
    topic_id = ticket.topic_id  # topic_id из базы
    
    if not topic_id:
        await cb.answer("Тема тикета не найдена.", show_alert=True)
        return
    
    # Помечаем тикет как закрытый в БД и начисляем баланс
    admin_id = cb.from_user.id
    await db.log_ticket_closed(topic_id, admin_id)
    
    # Начисляем баланс администратору (50 ₽ за тикет)
    amount = 50.0
    new_balance = await db.add_balance(admin_id, amount)
    
    # Удаляем тему
    try:
        try:
            await bot.delete_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=topic_id)
        except Exception:
            await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=topic_id)
        await cb.answer(f"Тикет закрыт ✅\nНачислено: {amount} ₽\nБаланс: {new_balance} ₽")
    except Exception as e:
        logger.warning("Could not remove topic: %s", e)
        await cb.answer(f"Тикет помечен как закрытый.\nНачислено: {amount} ₽\nБаланс: {new_balance} ₽", show_alert=True)
    
    # Отправляем пользователю запрос на рейтинг
    user_id = ticket.user_id  # user_id из объекта
    try:
        await ask_for_rating(user_id, ticket_number)
    except Exception as e:
        logger.error(f"Ошибка при запросе оценки для тикета #{ticket_number}: {e}", exc_info=True)

@dp.callback_query(F.data.startswith("rename_"))
async def rename_ticket_callback(cb: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Переименовать'"""
    await cb.answer()
    
    # Проверка прав админа
    try:
        member = await bot.get_chat_member(ADMIN_GROUP_ID, cb.from_user.id)
        if member.status not in ("administrator", "creator"):
            await cb.answer("Только администраторы могут переименовывать тикеты.", show_alert=True)
            return
    except Exception as exc:
        logger.warning("Couldn't check admin status: %s", exc)
    
    # Получаем номер тикета из callback_data
    ticket_number = int(cb.data.split("_")[1])
    ticket = await db.get_ticket_by_number(ticket_number)
    
    if not ticket:
        await cb.answer("Тикет не найден.", show_alert=True)
        return
    
    topic_id = ticket.topic_id  # topic_id из базы
    
    if not topic_id:
        await cb.answer("Тема тикета не найдена.", show_alert=True)
        return
    
    # Сохраняем данные для переименования
    await state.update_data(rename_thread=topic_id, rename_ticket_number=ticket_number)
    await state.set_state(RenameState.waiting_for_new_name)
    
    # Отправляем запрос на новое название в ту же тему
    thread_id = getattr(cb.message, "message_thread_id", None) or topic_id
    try:
        await bot.send_message(
            ADMIN_GROUP_ID,
            "✏️ Напишите новое название для темы тикета:",
            message_thread_id=thread_id
        )
    except Exception as e:
        logger.warning("Could not send rename request: %s", e)
        await cb.message.answer("✏️ Напишите новое название для темы тикета:")

@dp.message(RenameState.waiting_for_new_name)
async def admin_rename_receive(message: types.Message, state: FSMContext):
    """Обработчик получения нового названия темы"""
    data = await state.get_data()
    thread_id = data.get("rename_thread")
    ticket_number = data.get("rename_ticket_number")
    new_name = message.text.strip()

    if not new_name:
        await message.reply("Название не может быть пустым.")
        return

    if not thread_id:
        await message.reply("Ошибка: не найден ID темы.")
        await state.clear()
        return

    try:
        try:
            await bot.edit_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=thread_id, name=new_name)
        except Exception as e1:
            logger.warning("edit_forum_topic failed, trying raw API: %s", e1)
            try:
                await bot.request.post("editForumTopic", data={
                    "chat_id": ADMIN_GROUP_ID,
                    "message_thread_id": thread_id,
                    "name": new_name
                })
            except Exception as e2:
                logger.exception("Raw API call also failed: %s", e2)
                raise
    except Exception as e:
        logger.exception("Failed renaming topic: %s", e)
        await message.reply("Не удалось переименовать тему (проверьте права бота и версию API).")
        await state.clear()
        return

    await message.reply(f"Название темы изменено на: <b>{new_name}</b> ✅", parse_mode="HTML")
    await state.clear()

# ---------- Rating handlers ----------

@dp.callback_query(F.data.startswith("rate:") & ~F.data.startswith("rate_comment:"))
async def handle_rating_callback(cb: types.CallbackQuery, state: FSMContext):
    """Обработчик нажатия на кнопку рейтинга"""
    await cb.answer()
    
    try:
        # Пример данных: "rate:123:5"
        parts = cb.data.split(':')
        if len(parts) == 3:
            ticket_number = int(parts[1])
            rating = int(parts[2])
            user_id = cb.from_user.id
            
            # Сохраняем оценку в базу
            success = await db.save_ticket_rating(ticket_number, user_id, rating)
            
            if success:
                await cb.message.edit_text(
                    f"✅ Спасибо за вашу оценку: {rating} ⭐\n"
                    f"Ваш отзыв поможет нам стать лучше!"
                )
                logger.info(f"Пользователь {user_id} оценил тикет #{ticket_number} на {rating} звезд")
                
                # Предлагаем оставить комментарий
                await state.update_data(rating_ticket=ticket_number)
                await state.set_state(RatingState.waiting_for_comment)
                await cb.message.answer("Если хотите, можете добавить комментарий к оценке. Напишите его или отправьте /skip, чтобы пропустить.")
            else:
                await cb.answer("Ошибка сохранения оценки", show_alert=True)
        else:
            await cb.answer("Ошибка обработки оценки", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка при обработке оценки: {e}")
        await cb.answer("Произошла ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("rate_comment:"))
async def rate_comment_callback(cb: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить комментарий'"""
    await cb.answer()
    parts = cb.data.split(":")
    ticket_number = int(parts[1])
    
    # Сохраняем номер тикета в state для последующего сохранения комментария
    await state.update_data(rating_ticket=ticket_number)
    await state.set_state(RatingState.waiting_for_comment)
    
    await cb.message.answer("Пожалуйста, напишите ваш комментарий к оценке. Или отправьте /skip, чтобы пропустить.")

@dp.message(RatingState.waiting_for_comment)
async def receive_rating_comment(message: types.Message, state: FSMContext):
    """Обработчик получения комментария к рейтингу"""
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        return
    
    data = await state.get_data()
    ticket_number = data.get("rating_ticket")
    
    if not ticket_number:
        await state.clear()
        return
    
    # Сохраняем комментарий в базе
    await db.save_ticket_comment(ticket_number, message.from_user.id, message.text.strip())
    
    await message.answer("Комментарий добавлен. Спасибо!")
    await state.clear()

@dp.message(Command(commands=["skip"]))
async def skip_comment(message: types.Message, state: FSMContext):
    """Пропустить добавление комментария"""
    if await state.get_state() == RatingState.waiting_for_comment:
        await message.answer("Комментарий пропущен. Спасибо за вашу оценку!")
        await state.clear()

# ---------- Forwarding logic ----------

# Admin -> User forwarding (inside topic)
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_topic_messages(message: types.Message):
    # Ignore private chat messages here; handle only group/topic messages
    # ignore bot's own messages
    if message.from_user.is_bot:
        return

    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None:
        return  # not a topic message

    # if message came from bot copying, it could be copy from user; avoid loops by ignoring messages from bot
    # check admin status
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ("administrator", "creator"):
            return  # don't forward messages from non-admins in topic
    except Exception:
        return

    # find ticket by topic_id
    ticket = await db.get_ticket_by_topic(thread_id)
    if not ticket:
        return
    user_id = ticket.user_id
    number = ticket.number

    # prepare prefix
    admin_name = message.from_user.full_name
    prefix = f"💬 Сообщение из тикета #{number} от администратора {admin_name}:\n\n"

    try:
        if message.text:
            # send text to user as bot (from bot, with prefix)
            await bot.send_message(user_id, prefix + message.text)
        else:
            # message has media / or other content; attempt to copy it to user so content preserved
            try:
                await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
                # then send a small context message so user knows admin name
                await bot.send_message(user_id, f"Сообщение из тикета #{number} от администратора {admin_name}.")
            except Exception as e:
                # fallback: notify user about new content
                logger.warning("copy_message to user failed: %s", e)
                await bot.send_message(user_id, f"Администратор {admin_name} отправил вложение в тикет #{number}.")
    except exceptions.TelegramBadRequest as e:
        logger.warning("Failed to forward admin->user: %s", e)

# User -> Topic forwarding (private chat -> topic)
@dp.message(F.chat.type == "private")
async def handle_private_messages(message: types.Message):
    # ignore bot messages
    if message.from_user.is_bot:
        return

    # Skip commands
    if message.text and message.text.startswith('/'):
        return

    # user may be sending description or follow-up
    t = await db.get_last_ticket_for_user(message.from_user.id)
    if not t:
        await message.reply("У вас нет активных тикетов.")
        return

    # Используем атрибуты объекта
    ticket_status = t.status
    topic_id = t.topic_id
    number = t.number

    if ticket_status not in ("in_progress", "new"):
        # if closed or other, notify user
        if ticket_status == "closed":
            await message.reply("Ваш тикет закрыт.")
            return

    # If topic exists and in_progress, forward message to topic
    if topic_id:
        try:
            header = f"Сообщение от пользователя @{message.from_user.username or message.from_user.full_name} (тикет #{number}):"
            if message.text:
                await bot.send_message(ADMIN_GROUP_ID, header + "\n\n" + message.text, message_thread_id=topic_id)
            else:
                # has media — copy to topic
                try:
                    await bot.copy_message(chat_id=ADMIN_GROUP_ID, from_chat_id=message.chat.id, message_id=message.message_id, message_thread_id=topic_id)
                    await bot.send_message(ADMIN_GROUP_ID, header, message_thread_id=topic_id)
                except Exception as e:
                    logger.warning("copy_message user->topic failed: %s", e)
                    await bot.send_message(ADMIN_GROUP_ID, header + "\n(Вложение было отправлено, но не удалось автоматически перенести.)", message_thread_id=topic_id)
            # Убрано сообщение пользователю - сообщение просто пересылается в тему
        except exceptions.TelegramBadRequest as e:
            logger.warning("Failed to forward user->topic: %s", e)
            await message.reply("Не удалось отправить сообщение в тему (возможно бот потерял права).")
    else:
        # no topic yet; append to ticket description in DB
        from database import SessionLocal
        from sqlalchemy import select
        from models import Ticket
        async with SessionLocal() as session:
            result = await session.execute(
                select(Ticket)
                .where(Ticket.user_id == message.from_user.id)
                .order_by(Ticket.id.desc())
                .limit(1)
            )
            ticket = result.scalar_one_or_none()
            if ticket:
                desc = ticket.description or ""
                ticket.description = desc + "\n" + (message.text or "<медиа>")
                await session.commit()
                await message.reply(f"Описание добавлено в ваш тикет #{ticket.number} (еще не принято в работу).")
            else:
                await message.reply("Не удалось найти ваш тикет.")

# ---------- Runner ----------

async def main():
    # Инициализация базы данных PostgreSQL
    # Временно отключено - таблицы созданы вручную
    # try:
    #     await init_database()
    #     logger.info("Database initialized (PostgreSQL)")
    # except Exception as e:
    #     logger.error(f"Failed to initialize database: {e}")
    #     return
    logger.info("Database initialization skipped (tables created manually)")
    
    logger.info("=" * 50)
    logger.info("Bot starting...")
    logger.info(f"ADMIN_GROUP_ID: {ADMIN_GROUP_ID}")
    logger.info(f"Bot token: {TG_TOKEN[:10]}..." if TG_TOKEN else "Bot token: NOT SET!")
    
    if not TG_TOKEN:
        logger.error("TG_BOT_TOKEN is not set! Check your .env file.")
        return
    
    # Test bot connection
    try:
        me = await bot.get_me()
        logger.info(f"Bot connected as: @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}", exc_info=True)
        return
    
    # make sure webhooks are removed to avoid conflicts (if any)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook removed (if existed)")
    except Exception:
        pass
    
    # Устанавливаем команды бота (всплывающие подсказки)
    try:
        commands = [
            BotCommand(command="start", description="Начать работу с ботом"),
            BotCommand(command="menu", description="Открыть меню (для администраторов)")
        ]
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.warning(f"Failed to set bot commands: {e}")
    
    logger.info("Starting polling...")
    logger.info("=" * 50)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
