# tgbotstory2 — Telegram-бот для мониторинга контента VK / Instagram* / TikTok

Бот отслеживает новые публикации (посты и истории) указанных пользователей и пабликов в VK, Instagram* и TikTok. При появлении нового контента бот автоматически скачивает медиафайлы и отправляет их в Telegram-чат.

> \* Деятельность Meta Platforms Inc. (Instagram, Facebook) запрещена на территории РФ.

---

## 🏗️ Архитектура

```
┌──────────────────────────────────────────────────┐
│              Bothost Docker-контейнер              │
│  /app ← Git bind mount (авто-деплой)              │
│  /app/data ← Персистентный volume                  │
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
│  │      SQLite /app/data/bot.db (WAL mode)       │  │
│  │  target | content_hash | auth_credential      │  │
│  │         | poll_log                            │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  /app/data/tmp/  ← временные медиафайлы            │
│  stdout          ← структурированные логи          │
└──────────────────────────────────────────────────┘
```

## 📦 Требования

| Компонент | Минимальная версия |
|-----------|-------------------|
| Python | 3.11+ |
| Bothost.ru тариф | 2 vCPU, 1 GB RAM, 5 GB Disk |
| Доступ к Telegram API | Прямой (без прокси) |

## 🚀 Быстрый старт (Bothost)

1. **Создайте проект** в [Bothost.ru](https://bothost.ru) → «Новый бот».
2. **Привяжите Git-репозиторий** — Bothost автоматически клонирует репозиторий в `/app` и пересобирает контейнер при push.
3. **Настройте переменные окружения** в панели Bothost (см. таблицу ниже).
4. **Нажмите «Запустить»** — платформа соберёт образ из [`Dockerfile`](Dockerfile), установит зависимости и Playwright-браузеры, запустит бота.

Bothost автоматически:
- Устанавливает `BOT_TOKEN` из настроек платформы
- Подставляет `requirements.txt` через `pip install`
- Монтирует `/app` из Git и `/app/data` как персистентный volume
- Собирает образ по [`Dockerfile`](Dockerfile) (если есть) или авто-определяет Python-проект

## ⚙️ Настройки Bothost

| Параметр | Значение | Примечание |
|----------|----------|------------|
| **Тип проекта** | Docker (кастомный Dockerfile) | ✅ |
| **BOT_TOKEN** | _(авто из платформы)_ | ✅ Bothost подставляет сам |
| **ADMIN_IDS** | `123456789,987654321` | ID администраторов через запятую |
| **VK_USER_TOKEN** | `ваш_токен` | Для stories.get / wall.get |
| **VK_SERVICE_TOKEN** | `ваш_токен` | Для публичных страниц |
| **IG_USERNAME** | `ваш_логин` | Instagram логин |
| **IG_PASSWORD** | `ваш_пароль` | Instagram пароль |
| **TT_MS_TOKEN** | `ваш_токен` | TikTok ms_token |
| **ENCRYPTION_KEY** | `сгенерированный_ключ` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| **DB_PATH** | `sqlite+aiosqlite:////app/data/bot.db` | Не менять |
| **TEMP_MEDIA_DIR** | `/app/data/tmp` | Не менять |
| **LOG_LEVEL** | `INFO` | `DEBUG` для отладки |

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
├── Dockerfile               # Bothost Docker-образ
├── pyproject.toml           # Python-метаданные
├── requirements.txt
├── .env.example
└── README.md
```

## 📝 Лицензия

MIT
