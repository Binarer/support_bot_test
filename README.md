
```
support_bot_test
├─ .idea
│  ├─ inspectionProfiles
│  │  └─ profiles_settings.xml
│  ├─ misc.xml
│  ├─ modules.xml
│  ├─ MypyPlugin.xml
│  ├─ PylintPlugin.xml
│  ├─ support_bot_test.iml
│  ├─ vcs.xml
│  └─ workspace.xml
├─ App
│  ├─ Application
│  │  ├─ Dto
│  │  ├─ Jobs
│  │  ├─ Middleware
│  │  └─ Queries
│  ├─ Domain
│  │  ├─ Enums
│  │  │  └─ TicketStatus
│  │  │     └─ TicketStatus.py
│  │  ├─ Models
│  │  │  ├─ Ticket
│  │  │  │  └─ Ticket.py
│  │  │  └─ TicketStates
│  │  │     └─ ticket_states.py
│  │  └─ Services
│  │     ├─ CallbackService
│  │     │  └─ callback_service.py
│  │     ├─ MessageService
│  │     │  └─ message_service.py
│  │     ├─ TicketService
│  │     │  └─ ticket_service.py
│  │     └─ __init__.py
│  └─ Infrastructure
│     ├─ Actions
│     ├─ Components
│     │  └─ TelegramBot
│     │     ├─ ChannelManager
│     │     │  └─ channel_manager.py
│     │     ├─ processors
│     │     │  └─ message_processor.py
│     │     └─ telegram_bot.py
│     ├─ Config
│     │  └─ __init__.py
│     └─ storage
├─ main.py
├─ README.md
└─ requirements.txt

```