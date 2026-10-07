# Delivery Service

Микросервис международной доставки посылок: регистрация посылок, расчёт стоимости доставки, RAG-помощник поддержки и отчёты по типам за день. Авторизации нет — пользователь идентифицируется по `session_key` Django.

## Стек

- **Python** 3.14, **Django** 6.1 + **DRF** 3.18, **drf-spectacular**
- **PostgreSQL** 18 — основное хранилище
- **Redis** 8 — кэш курса USD/RUB и брокер Celery
- **MongoDB** 7 — лог расчётов стоимости
- **Qdrant** 1.19 — векторная база для RAG
- **Celery** + **Celery Beat** — фоновые и периодические задачи
- **LangChain** + **FastEmbed** (`minishlab/potion-multilingual-128M`), **DeepSeek** LLM
- **uv** — управление пакетами, **Docker Compose** — запуск
- **Ruff**, **mypy** (strict), **bandit**, **pytest** — качество кода

## Быстрый старт

```bash
docker compose up -d --build
```

## Инициализация

**Автоматически при `docker compose up`:**

- `migrate` — контейнер применяет миграции Django (включая seed типов посылок: `одежда`, `электроника`, `разное`)
- `init_mongo` — создаёт индексы в MongoDB (`{calculated_at: 1, type_id: 1}`)
- `web`, `worker`, `beat` — стартуют после успешной миграции

**Вручную:**

```bash
# Загрузить базу знаний в Qdrant (RAG)
docker compose exec web python manage.py load_knowledge_langchain

# Создать суперпользователя для админки
docker compose exec web python manage.py createsuperuser
```

## Тесты

```bash
uv run pytest -v
```

Для тестов нужен только PostgreSQL. Внешние зависимости (Qdrant, DeepSeek, MongoDB) мокаются через `pytest-mock`.

## API

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| `POST` | `/api/parcels/` | Регистрация посылки |
| `GET` | `/api/parcels/` | Список посылок (пагинация, фильтры `type`, `has_delivery_cost`) |
| `GET` | `/api/parcels/{id}/` | Детали посылки |
| `POST` | `/api/parcels/{id}/assign/` | Атомарная привязка к транспортной компании |
| `GET` | `/api/parcel-types/` | Справочник типов посылок |
| `POST` | `/api/support/ask/` | RAG-вопрос (векторный поиск + LLM) |
| `GET` | `/api/reports/delivery-costs/?date=YYYY-MM-DD` | Отчёт по типам за день (MongoDB aggregation) |

Swagger: http://localhost:8000/api/docs/

## Периодические задачи

| Задача | Расписание | Описание |
|--------|------------|----------|
| `parcels.tasks.calculate_delivery_costs` | каждые 5 минут | Считает стоимость для посылок без неё |

Ручной запуск:

```bash
docker compose exec web python manage.py calculate_delivery_costs
```

## Ключевые архитектурные решения

- **Чистая функция расчёта** — `compute_delivery_cost(parcel, rate)` не ходит в сеть; курс получается один раз на батч
- **Батчинг** — `iterator(chunk_size=500)` + `bulk_update` даёт N/500 UPDATE вместо N
- **MongoDB для лога** — `Decimal128` для точности, индекс `{calculated_at: 1, type_id: 1}` под агрегацию по дням
- **Атомарность assign** — `UPDATE ... WHERE company_id IS NULL`, первая компания побеждает
- **Singleton для дорогих объектов** — embedding-модель и клиент Mongo кэшируются через `lru_cache`
- **Partial index** — `delivery_cost IS NULL` ускоряет периодическую задачу
- **Изоляция по сессии** — `session_key` в middleware и queryset, пользователь видит только свои посылки
- **Rate limiting** — DRF throttling на Redis: 10/hour на RAG, 100/hour на остальное
- **Кэш курса** — USD/RUB в Redis, TTL 1 час, источник — ЦБ РФ

## Обоснования

**Почему MongoDB для лога расчётов?**
Лог — это append-only поток событий с гибкой схемой. Реляционная БД потребовала бы отдельной таблицы с миграциями под каждое изменение полей. MongoDB даёт быструю запись пачками (`insert_many`) и агрегацию по дням одним pipeline.

**Почему `Decimal128`, а не `float`?**
Деньги нельзя хранить в `float` — накопление ошибок округления искажает суммы в отчётах. `Decimal128` в MongoDB и `Decimal` в Python дают точную арифметику.

**Почему partial index на `delivery_cost IS NULL`?**
Периодическая задача выбирает только посылки без стоимости. Partial index покрывает именно этот срез, а не всю таблицу — меньше размер индекса, быстрее выборка.

**Почему Qdrant?**
Нужен векторный поиск по базе знаний с фильтрацией и персистентностью. Qdrant даёт нативный API, read-only ключи и интеграцию с LangChain через `langchain-qdrant`.

**Почему LangChain?**
Готовые абстракции для RAG: сплиттеры, векторные сторы, LCEL-цепочки. Меньше кода, проще менять модель эмбеддингов и LLM.

**Почему FastEmbed, а не OpenAI embeddings?**
`minishlab/potion-multilingual-128M` работает локально, поддерживает мультиязычность и не требует платить за каждый вызов. Модель скачивается один раз в volume `hf_cache`.

## Известные ограничения

- **RabbitMQ-регистрация** (доп. задание №2) — пропущено осознанно, Celery на Redis покрывает потребности
- **Веб-интерфейс** — не реализован, только API
- **OpenTelemetry / Prometheus** — метрики и трейсинг не подключены
- **Метрики и трейсинг** — отсутствуют, логи идут в stdout

## Структура проекта

```
delivery-service/
├── delivery/                  # Конфигурация Django-проекта
│   ├── settings.py            # Настройки, Celery Beat, DRF, кэш
│   ├── urls.py                # Корневые URL + Swagger
│   ├── celery.py              # Инициализация Celery
│   ├── asgi.py / wsgi.py      # Точки входа
├── parcels/                   # Основное приложение
│   ├── models.py              # Parcel, ParcelType
│   ├── serializers.py         # Сериализаторы API
│   ├── views.py               # ViewSet'ы и APIView
│   ├── filters.py             # Фильтры type, has_delivery_cost
│   ├── services.py            # Курс USD/RUB, формула стоимости
│   ├── tasks.py               # Celery-задача расчёта
│   ├── mongo.py               # Клиент MongoDB, агрегация
│   ├── middleware.py          # Логирование запросов
│   ├── utils.py               # Работа с session_key
│   ├── exceptions.py          # Единый формат ошибок
│   ├── rag/                   # RAG-компоненты
│   │   ├── builder.py         # Построение базы знаний
│   │   ├── embeddings.py      # Обёртка FastEmbed
│   │   ├── retriever.py       # Поиск в Qdrant
│   │   └── generator.py       # Генерация ответа через LLM
│   ├── knowledge/             # Исходные тексты базы знаний
│   ├── management/commands/   # load_knowledge_langchain, calculate_delivery_costs
│   └── migrations/            # Миграции + seed типов
├── tests/                     # pytest-тесты
├── docs/                      # Артефакты аналитика
├── docker-compose.yml         # Сервисы: web, worker, beat, postgres, redis, mongo, qdrant
├── Dockerfile                 # Образ на python:3.14-slim + uv
├── Makefile                   # lint, fmt, typecheck, security, test
└── pyproject.toml             # Зависимости и конфиги инструментов
```

## Продакшн-заметки

В тестовом окружении использованы упрощения. В проде:

- вместо `.env` — **Vault** или **AWS Secrets Manager**
- вместо `runserver` — **gunicorn** (или uvicorn для ASGI)
- вместо `docker logs` — **Loki + Grafana**
- вместо ручного `load_knowledge_langchain` — init-контейнер или job в CI/CD