# LiveMatch Core

Честный Telegram-бот знакомств: подбор по цели, району и интересам, без бесконечной ленты,
без перекоса внимания, без платного преимущества в привлекательности.

Интерфейс: Telegram-бот (aiogram 3) + Telegram Mini App (vanilla JS, отдаётся тем же backend'ом).
Backend: FastAPI + PostgreSQL + Redis + SQLAlchemy/Alembic. Деплой: Docker/docker-compose.

---

## 1. Быстрый старт (локально, Docker)

```bash
cp .env.example .env
# открой .env и подставь BOT_TOKEN (получить у @BotFather: /newbot)

docker compose up --build
```

Это поднимет: `db` (Postgres), `redis`, `migrate` (применит миграции и сидинг справочников один раз),
`api` (FastAPI на :8000), `bot` (long polling), `worker` (фоновые задачи: закрытие просроченных чатов,
ежедневный AIInsight).

Проверка:
- `curl http://localhost:8000/health` → `{"status":"ok",...}`
- Mini App: `http://localhost:8000/app` (для реального теста открывается внутри Telegram через кнопку бота)
- В Telegram: найди своего бота → `/start` → `📝 Создать анкету` → `🔎 Искать` → лайк → матч → чат

## 2. Быстрый старт (без Docker, для разработки)

```bash
make venv          # создаёт .venv, ставит зависимости
cp .env.example .env
# DATABASE_URL в .env замени на sqlite+aiosqlite:///./dev.db для совсем локального теста
# либо подними Postgres/Redis сам (docker compose up db redis)

make migrate        # применить миграции
make api             # FastAPI с автоперезагрузкой, :8000
make bot              # long polling, в отдельном терминале
make worker           # фоновые задачи, в отдельном терминале
make test              # pytest, 17 сценариев на sqlite
make lint                # ruff
```

## 3. Что нужно от тебя, чтобы всё реально заработало

| Что | Где взять | Обязательно? |
|---|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` | да |
| `ADMIN_TG_IDS` | свой Telegram numeric id (например через [@userinfobot](https://t.me/userinfobot)) | да, для `/admin_report` |
| `ANTHROPIC_API_KEY` | console.anthropic.com | нет — без него AIInsight использует rule-based fallback |
| Домен + TLS (для вебхука и оплаты на проде) | твой хостинг | да, для продакшна (не нужно для polling-режима локально) |
| Stripe/LiqPay/Fondy/WayForPay ключи | соответствующие кабинеты | нет — Telegram Stars работает без них |

Telegram Stars (оплата `⭐`) работает из коробки, без отдельного провайдер-токена — это требование Telegram.

---

## 4. Архитектура

```
app/
  core/        # config, db, redis, enums, telegram_auth (HMAC-валидация WebApp initData)
  models/      # 21 SQLAlchemy-модель (User, Profile, Photo, Interest, Like, Match, Chat, Message,
               # Payment, Referral, EventLog, ActivityScore, Verification, Community, Contest,
               # SystemMetric, AIInsight, ModerationQueueItem и связи)
  services/    # вся бизнес-логика: matching, chat, like, payment, referral, verification,
               # moderation (антиспам/антифрод), community, contest, metrics, ai_insight
  payments/    # PaymentProvider интерфейс + Telegram Stars (рабочий) + Stripe/LiqPay/Fondy/
               # WayForPay (интерфейс готов, реальные вызовы — TODO, см. ниже)
  bot/         # aiogram: handlers, keyboards, FSM states, middlewares
  api/         # FastAPI: webhook, payments webhook, admin REST, community/events, webapp API
  tasks/       # фоновый scheduler: sweep просроченных чатов + ежедневный AIInsight
webapp/static/ # Telegram Mini App (один HTML-файл, vanilla JS, без сборки)
migrations/    # Alembic: схема (21 таблица) + сидинг 15 интересов / 15 комьюнити / 2 события
tests/         # pytest, 17 сценариев на sqlite (matching, chat TTL, payments, referral antifraud, antispam)
```

### Состояния пользователя
`NEW → PROFILE_CREATION → VERIFICATION → ACTIVE_SEARCH ⇄ ACTIVE_CHAT/BUFFER_MATCH ⇄ PAUSE`,
плюс `INACTIVE`, `LIMITED`, `BANNED_BY_SYSTEM` — все как enum в `app/core/enums.py`.

### Алгоритм подбора (`app/services/matching_service.py`)
Город + цель + взаимная совместимость по полу — обязательные фильтры. Дальше скоринг:
overlap интересов, активность за последние 7 дней, штраф за уже большое входящее внимание
(`incoming_counter` за скользящее окно), буст тем, у кого давно не было диалога.
**Нигде не читается `Payment`/`is_paid`** — это закреплено отдельным тестом
(`tests/test_payment_and_limits.py::test_payment_never_influences_matching_score`).

### Чаты (`app/services/chat_service.py`)
1 активный чат + буфер на пользователя (FIFO, если матчей больше чем слотов — см. комментарий в коде).
24ч TTL, продление только при обоюдном согласии (бесплатно) либо мгновенно за ⭐ (платная фича).
Просрочка и неактивность закрываются фоновым воркером каждые 5 минут.

### Безопасность
- Антиспам: rate-limit сообщений/мин, лимит одинаковых сообщений, авто-мут — всё в Redis.
- Фото: SHA-256 + perceptual hash (`ImageHash`), дубликаты помечаются.
- Верификация: жест-челлендж + фото/видео-ответ. **Честно про объём**: это не биометрия и не
  ML-проверка живости — рабочий MVP-эвристик (см. docstring в `verification_service.py`),
  для продакшна стоит подключить специализированного вендора liveness-проверки.
- Risk-keywords (предоплата, крипта, "секс за деньги" и т.п.) детектятся regex'ом, пишутся
  в `risk_score`, уходят в `moderation_queue` — **никогда не банят автоматически**.
- Скрытая кнопка "🚨 опасность/мошенничество" — тоже только в `moderation_queue`, не авто-бан.

### AI-модуль (`app/services/ai_insight_service.py`)
Реальный вызов Anthropic API (`api.anthropic.com`), если задан `ANTHROPIC_API_KEY` — иначе
честный rule-based fallback на тех же метриках. AI **никогда** не пишет сообщения за пользователя
и не накручивает показатели — пульс сервиса (`/status`) берёт цифры напрямую из БД/Redis, AI их не трогает.

---

## 5. Деплой на хостинг

### Render / Railway / Fly.io (Docker-based)
1. Запушь репозиторий в свой GitHub (см. раздел 7).
2. Создай Postgres и Redis (managed addon, либо Railway/Render plugin).
3. Создай Web Service из Dockerfile, env переменные — как в `.env.example`, `DATABASE_URL`/`REDIS_URL`
   укажи на managed-инстансы.
4. **Установи `BOT_USE_WEBHOOK=true` и `BOT_WEBHOOK_URL=https://<твой-домен>`** — тогда `api`-сервис
   сам выставит вебхук при старте (см. `lifespan` в `app/api/main.py`). Отдельный `bot` long-polling
   сервис в этом режиме не нужен — выключи его / не деплой.
5. Запусти `worker` как отдельный сервис/процесс с командой `python scripts/run_worker.py`
   (на Render это "Background Worker", на Railway — второй сервис из того же репо).
6. Перед первым стартом примени миграции: `alembic upgrade head` (одноразовая Job/Release command).

### VPS (свой сервер)
```bash
git clone <твой-репозиторий> && cd livematch-core
cp .env.example .env  # заполни
docker compose up -d --build
```
Для вебхука понадобится reverse-proxy с TLS (nginx/Caddy) перед портом 8000 и
`BOT_USE_WEBHOOK=true` + `BOT_WEBHOOK_URL=https://твой-домен`. Без вебхука (`BOT_USE_WEBHOOK=false`,
по умолчанию) бот работает через long polling — TLS не нужен, подходит для VPS без домена.

---

## 6. Тестовые сценарии

```bash
make test
```

17 сценариев на sqlite (`tests/`):
- профиль: валидация возраста, минимум 3 интереса
- подбор: совместимость по полу, ранжирование по overlap интересов
- лайк/матч/чат: создание матча при взаимном лайке, обязательность обоюдного продления,
  автозакрытие просроченного чата + промоушен буфера
- платежи: успешная активация фичи, **гарантия что оплата не влияет на ранжирование**
- лимиты: дневной лимит лайков
- рефералка: антифрод (самоприглашение, общий device fingerprint), валидное начисление
- модерация: детект risk-keywords, детект спама одинаковых сообщений

Ручной end-to-end сценарий (после `docker compose up`):
`/start` → создать анкету → `🔎 Искать` → лайк двух тестовых аккаунтов друг на друга → матч →
`💬 Открыть чат` → сообщение → `⏳ Продлить чат` → `📊 Статус сервиса` → `🔗 Рефералка` →
`⭐ Платные возможности` → оплата тестовыми Stars → `/admin_report` (с твоим tg_id в `ADMIN_TG_IDS`).

---

## 7. Запушить в свой GitHub

У ассистента нет доступа к твоему GitHub-аккаунту, поэтому финальный пуш — твоими руками:

```bash
cd livematch-core
git init
git add .
git commit -m "LiveMatch Core: initial working MVP"
git branch -M main
git remote add origin https://github.com/<твой-юзернейм>/livematch-core.git
git push -u origin main
```

GitHub Actions (`.github/workflows/ci.yml`) после пуша сам прогонит lint + tests + docker build.

---

## 8. Честно про ограничения текущего MVP (что доделать перед реальным продакшном)

- **Stripe/LiqPay/Fondy/WayForPay** — интерфейс (`app/payments/*_provider.py`) и webhook-роут готовы,
  реальные запросы к их API — `TODO` в коде (нужны твои мерчант-ключи, которых нет у ассистента).
  Telegram Stars работает полностью.
- **Верификация** — эвристика (жест + фото-хеш), не настоящая биометрия/liveness-ML.
- **FSM-хранилище бота** — Redis (`RedisStorage`), с fallback на in-memory, если Redis недоступен
  (подходит для одного процесса, для нескольких реплик бота нужен реальный Redis).
- **Мульти-инстанс масштабирование**: `worker` обязателен как отдельный процесс при >1 реплики `api`,
  иначе фоновые задачи будут дублироваться (это уже учтено флагом `RUN_SCHEDULER_IN_API=false` в
  `docker-compose.yml`).
- **AI-инсайты** — реальный вызов Claude API, но при отсутствии ключа — rule-based fallback, не "фейковая" аналитика.

Всё остальное из ТЗ (модели, миграции, FSM, лайки/матчи/чаты, платежи Stars, рефералка с антифродом,
антиспам, комьюнити, события, AIInsight, admin_report, mini-app, CI) — реализовано и покрыто тестами.
