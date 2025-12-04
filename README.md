# Support Bot (Телегарам бот поддержки)

Telegram бот поддержки с системой тикетов, HTTP API и WebSocket для обработки обращений пользователей.

### 1. запуск бота

```bash
docker-compose up -d
```

### 2. Проверьте запуск

- **Бот**: Должен быть онлайн в Telegram
- **API**: `http://localhost:8000/docs` - Swagger UI
- **pgAdmin**: `http://localhost:8080` (admin@ticketbot.local / admin123)
- **База данных**: `localhost:15432`

### Основные endpoints:

- `POST /api/ticket/create` - Создать новый тикет
- `POST /api/ticket/{id}/message` - Отправить сообщение в тикет
- `GET /api/ticket/{id}/status` - Получить статус тикета
- `POST /api/ticket/{id}/close` - Закрыть тикет
- `POST /api/ticket/{id}/rating` - Оценить тикет
- `WebSocket /ws/ticket/{id}` - Подключение к чату тикета

## Структура проекта

```
.
├── App/                          # Основной код приложения
│   ├── Domain/                   # Бизнес логика
│   ├── Infrastructure/           # Инфраструктура и сервисы
│   └── ...
├── alembic/                      # Миграции базы данных
├── init-scripts/                 # Скрипты инициализации БД
├── main.py                       # Точка входа
├── requirements.txt              # Python зависимости
├── docker-compose.yml            # Docker конфигурация
├── Dockerfile                    # Сборка образа
├── .env.example                  # Пример конфигурации
└── bot.json                      # Сообщения и клавиатуры бота
```

## Логирование

Логи приложения записываются в файл `bot.log` и выводятся в консоль.
Уровень логирования настраивается переменной `LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR).

## Разработка

Для разработки без Docker:

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск миграций
alembic upgrade head

# Запуск бота
python main.py
```

## Контакты
dev by
https://t.me/@wasitfallen
