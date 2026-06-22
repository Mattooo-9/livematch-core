# LiveMatch Core

Честный живой сервис знакомств. Telegram-бот + Mini App + FastAPI backend.

**Стек:** Python 3.11, aiogram 3, FastAPI, PostgreSQL, Redis, SQLAlchemy, Alembic, Docker

---

## Быстрый старт (Docker)

```bash
git clone <repo> && cd livematch-core
cp .env.example .env          # заполни BOT_TOKEN и ADMIN_TG_IDS
make run                      # docker compose up --build
```

После старта:
- API: http://localhost:8000
- Healthcheck: http://localhost:8000/health
- Mini App: http://localhost:8000/app

---

## Локальный запуск (без Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # заполни DATABASE_URL, REDIS_URL, BOT_TOKEN, ADMIN_TG_IDS

# применить миграции
alembic upgrade head

# запустить API
make api

# в отдельном терминале — бот (long polling, для разработки)
make bot

# фоновый воркер (sweep чатов + AI инсайты)
make worker
```

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен @BotFather |
| `ADMIN_TG_IDS` | ✅ | Telegram ID через запятую |
| `DATABASE_URL` | ✅ | postgresql+asyncpg://... |
| `REDIS_URL` | ✅ | redis://... |
| `BOT_WEBHOOK_URL` | prod | https://yourdomain.com |
| `BOT_USE_WEBHOOK` | prod | true |
| `BOT_WEBHOOK_SECRET` | prod | случайная строка |
| `ANTHROPIC_API_KEY` | нет | для AI-инсайтов |
| `TELEGRAM_PAYMENTS_PROVIDER_TOKEN` | нет | для Stars (пустая строка = Stars XTR) |

Полный список — в `.env.example`.

---

## Деплой на Railway / Render / Fly.io (бесплатный тир)

### Railway (рекомендуется, бесплатный тир есть)

1. Зарегистрируйся на https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Добавь плагины **PostgreSQL** и **Redis** (через "+")
4. Скопируй DATABASE_URL и REDIS_URL из Railway в переменные проекта
5. Добавь все переменные из `.env.example`
6. Railway автоматически обнаружит `Dockerfile` и задеплоит

Для webhook режима:
```
BOT_USE_WEBHOOK=true
BOT_WEBHOOK_URL=https://<твой-проект>.up.railway.app
```

### Render

1. https://render.com → "New Web Service" → подключи GitHub
2. Build Command: `pip install -r requirements.txt && alembic upgrade head`
3. Start Command: `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
4. Добавь Postgres (Render Managed) и Redis (Upstash бесплатный)

### VPS (Fly.io / любой Docker-хост)

```bash
# установи flyctl: https://fly.io/docs/getting-started/
fly launch
fly secrets import < .env
fly deploy
```

---

## Архитектура

```
Telegram Bot (aiogram 3)
    ↕ polling / webhook
FastAPI
    /webhook/telegram/{secret}   — входящие апдейты бота
    /webhook/payments/{provider} — fiat-платежи (Stripe/LiqPay/Fondy/WayForPay)
    /admin/*                     — REST-панель (X-Admin-Token)
    /webapp/*                    — API для Mini App (X-Telegram-Init-Data)
    /app                         — статика Mini App
    /health                      — healthcheck

Services
    matching_service  — алгоритм подбора (активность, интересы, баланс внимания)
    chat_service      — 24ч TTL, 1 активный + 1 буфер, взаимное продление
    like_service      — лайки + дневной лимит + Redis-счётчик
    moderation_service — антиспам (Redis), риск-слова, очередь модерации
    verification_service — perceptual hash dedup + жест-верификация
    payment_service   — Stars (рабочий) + Stripe/LiqPay/Fondy/WayForPay (интерфейс готов)
    referral_service  — антифрод (device fingerprint, self-invite)
    ai_insight_service — Anthropic API (или rule-based fallback)
    metrics_service   — пульс сервиса + daily aggregate

PostgreSQL (21 таблица) + Redis (эфемерные счётчики, онлайн-TTL)
```

---

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Старт / главное меню |
| `/profile` | Создать / изменить анкету |
| `/search` | Искать |
| `/next` | Следующая анкета |
| `/status` | Пульс сервиса |
| `/pause` | Включить / выключить паузу |
| `/verify` | Верификация (жест) |
| `/referral` | Реферальная ссылка |
| `/pay` | Платные возможности (Stars) |
| `/community` | Комьюнити по интересам |
| `/events` | Активные события |
| `/help` | Справка |
| `/admin_report` | Только для ADMIN_TG_IDS |

---

## Платежи

**Telegram Stars** — работает из коробки, `TELEGRAM_PAYMENTS_PROVIDER_TOKEN` оставь пустым.

**Stripe / LiqPay / Fondy / WayForPay** — интерфейс `PaymentProvider` реализован, API-вызовы
помечены `TODO(production)` в `app/payments/*_provider.py`. Для активации:
- Заполни ключи в `.env`
- Реализуй `create_invoice()` и `verify_webhook()` в соответствующем провайдере

---

## Тесты

```bash
make test        # pytest -q  (17 тестов, in-memory SQLite, без внешних зависимостей)
```

---

## Честность алгоритма

Деньги **не покупают позицию в поиске**. Проверяется тестом:

```
test_payment_never_influences_matching_score
```

Тест читает исходник `matching_service.py` и статически убеждается, что там нет
никакого импорта или обращения к Payment/is_paid данным.

---

## Безопасность

- Webhook защищён токеном в URL (`BOT_WEBHOOK_SECRET`)
- Mini App: каждый запрос валидируется по HMAC-SHA256 `initData` от Telegram
- Admin API: `X-Admin-Token` header
- Фото: SHA256 + perceptual hash dedup (imagehash)
- Антиспам: Redis rate limit (20 сообщений/мин) + дедупликация идентичных
- Опасные сигналы → `moderation_queue`, **не автобан**
- Секреты только через `.env`, не в коде
