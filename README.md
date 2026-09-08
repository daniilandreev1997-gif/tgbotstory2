# tgbotstory2 — Telegram-бот для мониторинга контента VK / Instagram* / TikTok

Бот отслеживает новые публикации (посты и истории) указанных пользователей и пабликов в VK, Instagram* и TikTok. При появлении нового контента бот автоматически скачивает медиафайлы и отправляет их в Telegram-чат.

> \* Деятельность Meta Platforms Inc. (Instagram, Facebook) запрещена на территории РФ.

---

## 🏗️ Архитектура

```
┌──────────────────────────────────────────────────┐
│                  systemd unit: tgbotstory2         │
│  Type=simple | Restart=always | WatchdogSec=60s    │
│                                                    │
│  ┌─────────────────────┐  ┌──────────────────────┐│
│  │  aiogram Bot + DP   │  │  APScheduler         ││
│  │  (long-polling)     │  │  (AsyncIOScheduler)  ││
│  │                     │  │                      ││
│  │  • /start — меню    │  │  VK:  stories 5min   ││
│  │  • Добавить цель    │  │       posts   120min ││
│  │  • Удалить цель     │  │  IG:  stories 5min   ││
│  │  • Список целей     │  │       posts   160min ││
│  │  • Загрузить токен  │  │  TT:  posts   15min  ││
│  │  • Доступные цели   │  │       stories 20min  ││
│  └─────────┬───────────┘  └──────────┬───────────┘│
│            │                         │             │
│            ▼                         ▼             │
│  ┌──────────────────────────────────────────────┐  │
│  │          SQLite (aiosqlite + WAL mode)        │  │
│  │  target | content_hash | auth_credential      │  │
│  │         | poll_log                            │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  /tmp/tgbotstory2_media/  ← временные файлы       │
│  logs/bot.log              ← ротация 10 MB × 3    │
└──────────────────────────────────────────────────┘
```

## 📦 Требования

| Компонент | Минимальная версия |
|-----------|-------------------|
| Python | 3.10+ |
| Bothost.ru тариф | 2 vCPU, 1 GB RAM, 5 GB Disk |
| Доступ к Telegram API | Прямой (без прокси) |
| systemd | user-юниты (linger) |

## 🚀 Быстрый старт

```bash
cd /home/user
git clone https://github.com/daniilandreev1997-gif/tgbotstory2.git
cd tgbotstory2
bash scripts/setup.sh
nano .env  # fill BOT_TOKEN, ENCRYPTION_KEY, etc.
systemctl --user restart tgbotstory2
```

## 📁 Структура проекта

```
tgbotstory2/
├── bot/
│   ├── main.py              # точка входа
│   ├── config.py            # pydantic-settings
│   ├── crypto.py            # Fernet-шифрование
│   ├── handlers/            # Telegram-обработчики
│   ├── extractors/          # VK, Instagram, TikTok
│   ├── scheduler/           # APScheduler-джобы
│   ├── transport/           # доставка медиа
│   ├── db/                  # SQLAlchemy-модели
│   └── middleware/          # structlog
├── tests/                   # 31 тест (31/31 ✅)
├── spec/                    # SPARC-спецификации
├── scripts/
│   ├── setup.sh             # скрипт развёртывания
│   └── healthcheck.sh       # healthcheck
├── tgbotstory2.service      # systemd unit
├── requirements.txt
├── .env.example
└── README.md
```

## 📝 Лицензия

MIT