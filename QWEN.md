# QWEN.md — Spectech Platform («СпецТехника Про»)

Инструкционный контекст для AI-агентов и разработчиков. Дополняет `.cursorrules` (обязательные правила агента) и `README.md` (продуктовое описание). Отвечай на русском языке; комментарии в коде — на русском.

## 1. Обзор проекта

**СпецТехника Про** — multi-tenant SaaS-платформа для компаний, сдающих в аренду спецтехнику (версия 1.6.1). Ключевые домены:

- управление заявками на аренду и сменными заданиями (статусы: новая → в работе → завершена → оплачена);
- парк техники: каталог, статусы (свободна / в работе / на ремонте / списана), привязка к компаниям;
- GPS-трекинг и телематика (Wialon/Mapix): реал-тайм координаты через WebSocket, геозоны, моточасы, топливо;
- учёт топлива: заправки/сливы, алерты на подозрительные операции;
- финансовый документооборот: счета, акты, УПД, выплаты; PDF с учётом системы налогообложения (ОСНО, УСН 6/15%, Патент, НПД) и корректным НДС (включён/сверх);
- маркетплейс техники с региональным матчингом;
- справочник контрагентов (клиенты, собственники, субподрядчики) с полными реквизитами (ИНН, КПП, ОГРН, банк);
- email-уведомления, чат, аналитика (dashboard, Recharts).

**Главный архитектурный принцип — изоляция данных по `company_id`** (см. §7).

## 2. Технологический стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async, asyncpg), Pydantic v2, Alembic, APScheduler, Redis 7, MinIO (S3/boto3) |
| PDF/Email | WeasyPrint, ReportLab, fpdf2, Jinja2, aiosmtplib (в Docker-образе — кириллические шрифты DejaVu/FreeFont) |
| Frontend | React 18, TypeScript 5.5, Vite 5, TailwindCSS 3, React Router v6, Axios, Recharts, Leaflet (+draw, markercluster), lucide-react, react-hot-toast |
| Тесты | pytest + pytest-asyncio (auto), pytest-cov, factory_boy, Faker, testcontainers, locust; Vitest + Testing Library (jsdom), Playwright (e2e) |
| Качество | black (88 символов, py312), ruff (E/W/F/I/C4/UP), mypy (плагин SQLAlchemy), pre-commit, detect-secrets, gitleaks |
| Инфраструктура | Docker Compose, Nginx, PostgreSQL 16 / TimescaleDB, Prometheus + Grafana, GlitchTip (Sentry-совместимый), ежедневный бэкап БД |

## 3. Структура репозитория

```
backend/
  app/
    main.py            # точка входа FastAPI: lifespan, ~47 роутеров, middleware
    api/routes/        # ~47 модулей роутеров (auth, vehicles, requests, shifts/,
                       #   gps, telematics, finance, invoices, acts, payouts,
                       #   marketplace, chat, websocket, system, ...)
    models/            # 22 модуля моделей SQLAlchemy (company, rental, shift, ...)
    schemas/           # Pydantic-схемы (в т.ч. public.py)
    core/              # config, db, logging_config, metrics, sentry_config,
                       #   middleware, exception_handlers
    services/          # бизнес-логика (storage_service и др.)
    tasks/scheduler.py # фоновые задачи APScheduler
    middleware/        # rate_limiter
  alembic/             # миграции (+ alembic.ini в backend/)
  tests/               # pytest, фикстуры в tests/conftest.py
  scripts/             # entrypoint.sh, backup_db.sh, seed_*
  requirements.txt     # все зависимости (включая dev/test)
  pytest.ini           # asyncio_mode=auto, маркеры unit/integration/slow
  pyproject.toml       # black / ruff / mypy
frontend/
  src/                 # код приложения; типы — @/types; тест-setup — src/test/setup.ts
  vite.config.ts       # dev-сервер :3000, proxy /api и /api/v1/ws → 127.0.0.1:8000
  playwright.config.ts # e2e
docker-compose.yml           # базовый compose (nginx :8888, TimescaleDB, Redis, MinIO,
                             #   backend, frontend, Prometheus :9091, Grafana :3002,
                             #   GlitchTip :9090, db-backup)
docker-compose.override.yaml # dev-override (применяется автоматически): backend :8000,
                             #   postgres :5470, монтирование исходников, ENVIRONMENT=development
docker-compose.dev.yml       # альтернативный override (read-only монтирование app/tests)
docker-compose.prod.yaml     # production: nginx :80/:443, postgres:16-alpine, env_file .env.prod
nginx/  monitoring/          # конфиги reverse proxy и мониторинга
```

Ключевые документы: `README.md`, `DEPLOYMENT.md`, `DOCKER_SHUTDOWN.md`, `SECURITY_POLICY.md`, `PLATFORM_OWNER.md`, `CHANGELOG.md`, `.cursorrules`.

## 4. Сборка и запуск

### Переменные окружения

```bash
cp backend/.env.example backend/.env   # Windows: copy backend\.env.example backend\.env
```

Основные переменные: `DATABASE_URL`, `REDIS_HOST/PORT/DB/PASSWORD`, `JWT_SECRET_KEY`, `CORS_ORIGINS` (по умолчанию `http://localhost:3000`), `SCHEDULER_ENABLED`, `TELEGRAM_*`, `PLATFORM_OWNER_EMAIL`. Для production — `.env.prod` (не коммитить). Секреты проверяются detect-secrets/gitleaks.

### Docker — разработка

```bash
docker-compose up -d        # base + docker-compose.override.yaml (автоматически)
docker-compose ps           # дождаться healthy
```

- Backend API: http://localhost:8000/docs (healthcheck: `/api/v1/system/health`)
- PostgreSQL: `localhost:5470` (TimescaleDB + pg_stat_statements)
- Nginx: http://localhost:8888
- Исходники `backend/app` и `backend/tests` смонтированы в контейнер (hot-reload).
- Миграции применяются автоматически при старте контейнера (`scripts/entrypoint.sh`), кроме `ENVIRONMENT=testing`.

### Docker — production

```bash
docker-compose -f docker-compose.prod.yaml --env-file .env.prod up -d
```

Nginx :80/:443; порт PostgreSQL наружу не публикуется; бэкап БД ежедневно в 02:00 (хранение 30 дней). Подробности — `DEPLOYMENT.md`. Корректное завершение — `DOCKER_SHUTDOWN.md` (graceful shutdown: остановка планировщика, закрытие соединений БД/Redis).

### Backend локально (без Docker)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

В контейнере запускается `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}`.

### Миграции (Alembic, из `backend/`)

```bash
alembic upgrade head                          # применить
alembic revision --autogenerate -m "описание" # новая миграция (проверяй сгенерированный код!)
alembic current / alembic history             # диагностика
```

### Frontend (из `frontend/`)

```bash
npm install
npm run dev          # Vite :3000, proxy /api и /api/v1/ws → backend :8000
npm run build        # production-сборка в dist/
npm run preview
npm run typecheck    # tsc -b
```

## 5. Тестирование

**Мандат TDD** (`.cursorrules`): сначала тест, потом код. Цель — 100% покрытие модуля.

Backend (из `backend/`, конфиг `pytest.ini`, `asyncio_mode=auto`):

```bash
pytest                                   # все тесты
pytest -m unit                           # быстрые изолированные
pytest -m integration                    # с реальной БД
pytest --cov=app --cov-report=term-missing
pytest tests/path/test_file.py::test_name
```

- Фикстуры — из `tests/conftest.py` (`auth_client`, `db_session`, `sample_vehicle` и др.). Не хардкодь ID — UUID/динамические значения.
- Обязательные негативные кейсы: 404 (не найдено), 403 (чужая компания), 422 (валидация).
- WebSocket: первым сообщением может быть системное событие (`user_joined`) или ping — читай сообщения гибко.
- Мокай внешние сервисы (MAX Bot, Wialon, Diadoc, Dadata), но **не мокай слой БД** в интеграционных тестах.

Frontend (из `frontend/`):

```bash
npm run test:unit            # Vitest (jsdom)
npm run test:unit:coverage
npm run test:e2e             # Playwright (есть :ui и :headed варианты)
```

Агент ОБЯЗАН сам запустить соответствующие тесты перед выдачей результата.

## 6. Качество кода

```bash
# из backend/
black .                      # форматирование (88 символов, py312)
ruff check . --fix           # линт + автофиксы (isort включён)
mypy app                     # типы (плагин SQLAlchemy)
pre-commit install           # установка хуков (один раз)
pre-commit run --all-files   # black, ruff, detect-secrets, базовые проверки
```

Особенности ruff: `E712` игнорируется (SQLAlchemy требует `== True`), `B008` разрешён (FastAPI `Depends`). Секреты: `.secrets.baseline` (detect-secrets), `.gitleaks.toml`; `.env*` с реальными значениями не коммитить.

## 7. Конвенции разработки

### Multi-tenant изоляция (критично)

1. ЛЮБОЙ запрос к БД (чтение или изменение) фильтруется по `company_id`.
2. Компания определяется зависимостью `get_current_company_id(db, user)`; суперпользователь переключает компанию заголовком `X-Company-Id`.
3. Тест на чужую компанию (403) обязателен для каждого эндпоинта.

### Backend

- Асинхронные эндпоинты (`async def`) и `AsyncSession`; `select()` / `scalars()` / `options(joinedload())` против N+1.
- Валидация — строго Pydantic v2 (`Field`, `model_validator`). Схемы — в `app/schemas/`.
- Чёткие HTTP-статусы: 404 / 403 / 409 / 422; без утечки трейсбеков в продакшене.
- **Запрет wildcard-импортов моделей** (`from app.models import *`) — вызывает shadowing имён роутеров (известная ошибка). Импортируй явно: `from app.models.vehicle import Vehicle`. В `main.py` роутеры импортируются с алиасами ДО моделей — порядок не ломать.
- Перед выдачей кода проверяй, что все функции/классы импортированы (никаких `NameError`/`ImportError`); при правке проверяй влияние на импорты в других файлах.
- Перед крупной правкой проверь, не является ли функция «мёртвым кодом» (например, нет декоратора `@router`).

### Frontend

- Строгая типизация: никаких `any`; интерфейсы из `@/types` или генерация из Pydantic-схем.
- API — через кастомный экземпляр Axios с перехватчиками (токен + `X-Company-Id`).
- **Москва и Московская область всегда вверху списков/выпадающих меню регионов.**

### Доменная логика

- Маркетплейс: региональный скоринг +15 за точное совпадение региона, +8 за соседний; кросс-категорийные подсказки (землеройная техника → земляные работы).
- Телематика: GPS-данные (Wialon/Mapix) обрабатываются асинхронно; синхронизации логируются через `_logged_call`.
- Финансы: налоговые режимы ОСНО / УСН 6% / УСН 15% / Патент / НПД; НДС «включён» или «сверх»; PDF (счёт, акт, УПД) с полными реквизитами и русскими единицами (час, смена, км).

### Workflow и коммиты

- Перед кодом — краткий план (1–2 предложения). Не уверен в структуре модели — сначала поиск по кодовой базе, не галлюцинируй поля.
- После задачи: тесты зелёные → коммит в стиле **Conventional Commits** (`fix:`, `perf:`, `feat:` ...; см. `git log`). Коммить только относящиеся к задаче файлы.
- Язык общения и комментариев — русский.

## 8. Важные нюансы и известные грабли

- **Планировщик APScheduler запускается только в одном uvicorn-воркере** (иначе дублирование задач) — не меняй эту логику без необходимости.
- Уникальность GPS-точек enforced в БД: одна точка на `(vehicle_id, recorded_at)`.
- Бюджет пула соединений SQLAlchemy должен учитывать `max_connections` Postgres (особенно при нескольких воркерах).
- Graceful shutdown: lifespan останавливает планировщик, закрывает engine и Redis; в compose заданы `stop_grace_period` и `stop_signal` — см. `DOCKER_SHUTDOWN.md`.
- `TESTING`-режим пропускает подключение к MinIO; в тестах не полагайся на реальный S3.
- Комиссия маркетплейса хранится как доля (fraction), не проценты — учитывай в формах и расчётах.
- В корне репозитория есть служебные/временные файлы (логи, патчи, SQL-скрипты) — не трогай их без запроса и не включай в коммиты.

## 9. Проверка изменений (чек-лист агента)

1. `pytest` (затронутые модули + негативные кейсы) — из `backend/`.
2. `black . && ruff check . && mypy app` — из `backend/`.
3. `npm run typecheck && npm run test:unit` — из `frontend/` (если затронут frontend).
4. Миграция сгенерирована и проверена вручную (если менялись модели).
5. Изоляция `company_id` сохранена; тест 403 на чужую компанию есть.

## Правила выполнения команд
- Никогда не запускать интерактивные команды: `python` без аргументов,
  `psql`, `git log`/`git diff` без `--no-pager`. Использовать `python -c "..."`.
- Не устанавливать зависимости и не создавать окружения без явного разрешения.
- Тесты запускать только по конкретному файлу: `python -m pytest <путь> -x -q`.
  Полный прогон (3367 тестов) не запускать никогда без отдельной команды.
- Если команда не вернулась за 60 секунд — сообщить мне, а не ждать.
- Перед длинной операцией сначала писать, что именно собираешься запустить.


## 12. Правила работы агента (выстрадано на практике)

### 12.1 Окружение
- Каноническое окружение — контейнер `spectech-backend`. Команды Python/pytest/ruff/black/alembic выполнять через `docker compose exec -T backend <cmd>`.
- Внутри контейнера cwd = `/app`. Пути вида `backend/app/...` там НЕ существуют — использовать `app/...`.
- Не запускать локальный `uvicorn app.main:app` из `.venv` параллельно с контейнером: дублирует планировщик и рвёт port-forward.
- Полный прогон тестов ~19 мин. Для итераций использовать `-k` или конкретный файл.
- `pytest-timeout` НЕ установлен — флаг `--timeout` ломает запуск.

### 12.2 Windows / PowerShell
- `Set-Content -Encoding UTF8` в PowerShell 5.1 дописывает BOM. BOM в `pytest.ini` ломает pytest.
- Писать файлы так: `[System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))`.

### 12.3 Никогда не угадывать имена
Перед использованием таблицы/колонки/атрибута/пути — проверить фактом:
- колонки БД: `python -c "from app.models.catalog import Vehicle; print([c.name for c in Vehicle.__table__.columns])"`
- атрибуты ORM (могут отличаться от колонок): `sqlalchemy.inspect(Vehicle).attrs.keys()`
- схема API: `app.openapi()` в процессе, а не угадывать URL
- путь роутера: искать в `app/main.py` по `include_router`

Реальные ошибки: `plate_number` (нет такой колонки), `vehicle_categories` (таблица `categories`), `model` как kwarg, `api/v1/payouts.py` (реально `api/routes/payouts.py`).

### 12.4 Миграции
- Ревизию создавать ТОЛЬКО через `alembic revision -m "..."`. Ручной ID вызвал `Cycle is detected` на веере из 17 веток от `sprint3_002`.
- После генерации проверять `alembic heads`; если граф сломан — удалить файл ДО рестарта контейнера (entrypoint выполняет `alembic upgrade head` и уйдёт в краш-луп).
- `detect-secrets` считает hex-ID ревизии секретом → добавлять `# pragma: allowlist secret`.
- Проверять обратимость: `alembic downgrade -1`, затем `alembic upgrade head`.

### 12.5 Коммиты
- pre-commit (black, ruff) меняет файлы и срывает коммит. После автофиксов повторить `git add` и `git commit`.
- Не заявлять «готово» без вывода проверки.

### 12.6 TimescaleDB
- `UPDATE`/`DELETE` по `gps_points` требуют `decompress_chunk` для сжатых чанков.
- Уникальный индекс обязан включать колонку партиционирования (`recorded_at`).
- Размер hypertable: `hypertable_size('gps_points')`, а не `pg_total_relation_size`.

### 12.7 Неопределённые имена
- Авторитетный инструмент: `ruff check --select F821 app/`. Самописные AST-проверки пропускают lowercase-имена (`datetime`, `select`).

### 12.8 Границы автономности
Агент МОЖЕТ самостоятельно: механические фиксы импортов (F821), форматирование, тесты, оптимизация запросов с замером до/после, документация.

Требует ревью человека (НЕ делать автономно): tenant-изоляция (`company_id`) и авторизация; денежная математика (комиссии, выплаты, НДС); миграции, меняющие типы/семантику данных; удаление данных.

### 12.9 Протокол параллельных задач
- Одна задача = одна группа файлов. Не трогать файлы, которые правит другой исполнитель.
- Общие файлы (`app/main.py`, `app/core/config.py`, модели) — только по согласованию.
- Каждая задача заканчивается проверяемым критерием: `ruff F821 <file>` = 0, импорт модуля OK, целевые тесты зелёные.
- Отчёт: что изменено, чем проверено, вывод команды.

### 12.10 Код не перезагружается сам
В `entrypoint.sh` uvicorn запущен БЕЗ `--reload` (только `--workers 4`). После любого изменения кода обязателен `docker compose restart backend` перед проверкой через HTTP — иначе воркеры исполняют старый модуль из памяти и дают ложные результаты (проверено: 200 вместо 401 на закрытом эндпоинте).


### 12.11 Сверка путей и имён — с фактом, а не с догадкой
- Пути эндпоинтов сверять с `app.routes`, а не только с `app.openapi()`: маршруты с `include_in_schema=False` в OpenAPI не попадают (например `GET /`).
- SQLAlchemy для PEP-435 Enum использует **`.name`**, а не `.value`, как строку в БД. Имена членов должны совпадать со значениями в БД (поэтому в проекте они lowercase).
- Дрейф model vs БД — реальный класс багов: `DocumentStatus` имел 7 из 14 значений, и строка со `sent_to_edo` ломала **весь** список актов; `Act.signed_at`, `ShiftTemplate.operator_id`, `UploadedFile.payout_id` не существовали.
