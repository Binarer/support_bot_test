import uuid
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
BOT_TOKEN = "8179950858:AAHMlatzioipOwqOyVUKvwiCG-unFxG6XlQ"  # задайте в .env или переменных окружения
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Команда для создания нового топика с UUID
@router.message(Command("newtopic"))
async def create_topic(message: Message):
    if not message.chat.is_forum:
        await message.answer("Этот чат не является форумом.")
        return

    topic_name = str(uuid.uuid4())
    try:
        topic = await bot.create_forum_topic(chat_id=message.chat.id, name=topic_name)
        await message.answer(f"Создан топик: {topic_name}\nID топика: {topic.message_thread_id}")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка при создании топика: {e}")

@router.message(Command("emoji"))
async def change_topic_emoji(message: Message, command: CommandObject):
    if message.message_thread_id is None:
        await message.answer("Эту команду можно использовать только внутри топика.")
        return

    if not message.chat.is_forum:
        await message.answer("Этот чат не является форумом.")
        return

    custom_emoji_id = command.args.strip() if command.args else None

    if custom_emoji_id:
        # Проверяем, что это похоже на ID (цифры)
        if not custom_emoji_id.isdigit():
            await message.answer(
                "Пожалуйста, укажите ID кастомного emoji (только цифры).\n"
                "Пример: /emoji 5487291217306427393\n"
                "Чтобы убрать emoji, используйте: /emoji"
            )
            return

    try:
        await bot.edit_forum_topic(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            icon_custom_emoji_id=custom_emoji_id or None  # None — убрать emoji
        )
        if custom_emoji_id:
            await message.answer("✅ Emoji топика обновлён.")
        else:
            await message.answer("✅ Emoji топика удалён.")
    except TelegramBadRequest as e:
        await message.answer(f"❌ Ошибка: {e.message}")

# Основной запуск
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())