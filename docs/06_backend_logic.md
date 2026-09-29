# Backend Logic — Микросервис доставки посылок


## Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.14 |
| Фреймворк | Django 6.1 + Django REST Framework |
| БД | PostgreSQL |
| Кеш | Redis |
| Векторная БД | Qdrant / ChromaDB |
| LLM | OpenAI / YandexGPT / GigaChat / локальная |
| Планировщик | Celery Beat (или django-crontab) |
| Брокер (доп.) | RabbitMQ |
| Лог (доп.) | MongoDB |
| Контейнеризация | Docker + docker-compose |

---

## 1. Работа с сессиями

**Требование:** приложение без авторизации, пользователи различаются по сессии.

**Реализация:**
- Используется `django.contrib.sessions.middleware.SessionMiddleware`.
- Ключ сессии (`session_key`) сохраняется в поле `parcel.session_key`.
- При первом запросе Django автоматически создаёт сессию и ставит cookie.
- Все выборки посылок фильтруются по `session_key = request.session.session_key`.

**Псевдокод получения сессии:**

```python
def get_session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key
```

**Middleware для логирования (кастомный):**
- Логирует метод, путь, статус, длительность, `session_key`.
- Добавляется в `MIDDLEWARE` после `SessionMiddleware`.

---

## 2. Роуты (endpoints)

| Метод | Путь | Назначение | US |
|-------|------|-----------|----|
| POST | `/api/parcels/` | Регистрация посылки | US-01 |
| GET | `/api/parcel-types/` | Справочник типов | US-02 |
| GET | `/api/parcels/` | Список своих посылок (пагинация, фильтры) | US-03 |
| GET | `/api/parcels/{id}/` | Данные о посылке | US-04 |
| POST | `/api/support/ask/` | RAG-вопрос поддержке | US-05 |
| POST | `/api/parcels/{id}/assign/` | Привязка к компании (доп.) | US-09 |
| GET | `/api/reports/delivery-costs/` | Отчёт по типам за день (доп.) | US-11 |

---

## 3. Логика роутов

### 3.1. POST `/api/parcels/` — Регистрация посылки

**Шаги:**
1. Получить/создать сессию.
2. Валидировать тело через DRF Serializer:
   - `name` — строка, не пустая, ≤ 255;
   - `weight` — число > 0;
   - `type` — id существующего типа;
   - `content_cost_usd` — число ≥ 0.
3. Проверить существование типа (`parcel_type`).
4. Создать `parcel` с `session_key`.
5. Вернуть `201 Created` с `id`.

**Обработка ошибок:**
- Ошибки валидации → `400` со стандартизированным телом.

---

### 3.2. GET `/api/parcel-types/` — Справочник типов

**Шаги:**
1. Выбрать все `parcel_type`.
2. Вернуть `200 OK` со списком `{id, name, code}`.

---

### 3.3. GET `/api/parcels/` — Список своих посылок

**Шаги:**
1. Получить `session_key`.
2. Базовый queryset: `Parcel.objects.filter(session_key=...)`.
3. Применить фильтры:
   - `type` → `filter(type_id=...)`;
   - `has_delivery_cost` → `filter(delivery_cost__isnull=False/True)`.
4. Применить пагинацию (`page`, `page_size`).
5. Сериализовать: `id`, `name`, `weight`, `type` (имя), `content_cost_usd`, `delivery_cost`.
6. Если `delivery_cost is None` → вернуть строку «Не рассчитано».
7. Вернуть `200 OK` с метаданными пагинации.

**Оптимизация:**
- `select_related("type")` — избежать N+1.

---

### 3.4. GET `/api/parcels/{id}/` — Данные о посылке

**Шаги:**
1. Получить `session_key`.
2. `get_object_or_404(Parcel, id=id, session_key=session_key)`.
3. Сериализовать поля: `name`, `weight`, `type`, `content_cost_usd`, `delivery_cost`.
4. Вернуть `200 OK`.

**Важно:** чужая посылка → `404` (не раскрываем существование).

---

### 3.5. POST `/api/support/ask/` — RAG-вопрос

**Шаги:**
1. Валидировать `question` (непустая строка).
2. Векторизовать вопрос (embedding-модель).
3. Выполнить поиск в векторной БД (top-K, например K=5).
4. Собрать контекст из найденных фрагментов.
5. Сформировать промпт:
   ```
   Ты — служба поддержки службы доставки.
   Отвечай только на основе контекста ниже.
   Если ответа нет — скажи, что не знаешь.

   Контекст:
   {context}

   Вопрос: {question}
   ```
6. Вызвать LLM API.
7. Вернуть `200 OK` с `answer` и `sources`.

**Обработка ошибок:**
- Векторная БД недоступна → `503`.
- LLM недоступна/таймаут → `502`/`504`.

---

### 3.6. POST `/api/parcels/{id}/assign/` — Привязка к компании (доп.)

**Шаги:**
1. Валидировать `company_id` (положительное число).
2. Атомарное обновление:
   ```python
   updated = Parcel.objects.filter(
       id=parcel_id, company_id__isnull=True
   ).update(company_id=company_id)
   ```
3. Если `updated == 1` → `200 OK`.
4. Если `updated == 0`:
   - посылка не найдена → `404`;
   - уже привязана → `409 Conflict` с текущим `company_id`.

**Гарантия от гонки:** атомарный `UPDATE ... WHERE company_id IS NULL` на уровне БД.

---

### 3.7. GET `/api/reports/delivery-costs/` — Отчёт (доп.)

**Шаги:**
1. Принять параметр `date`.
2. Выполнить агрегацию в MongoDB (см. [`05_data_model_erd.md`](05_data_model_erd.md)).
3. Вернуть сумму по типам.

---

## 4. Периодическая задача расчёта стоимости

**Расписание:** каждые 5 минут (Celery Beat).

**Алгоритм:**
1. Получить курс USD/RUB:
   - проверить Redis-ключ `usd_rub_rate`;
   - при промахе — GET `https://www.cbr-xml-daily.ru/daily_json.js`;
   - извлечь `Valute.USD.Value`;
   - сохранить в Redis с TTL (например, 1 час).
2. Выбрать посылки: `Parcel.objects.filter(delivery_cost__isnull=True)`.
3. Для каждой вычислить:
   ```
   delivery_cost = (weight * 0.5 + content_cost_usd * 0.01) * rate
   ```
4. Сохранить `delivery_cost` и `delivery_cost_calculated_at`.
5. Записать в лог (MongoDB, доп.).
6. Залогировать количество обработанных.

**Псевдокод:**

```python
def calculate_delivery_costs() -> int:
    rate = get_usd_rub_rate()  # из Redis или API
    parcels = Parcel.objects.filter(delivery_cost__isnull=True)
    count = 0
    for parcel in parcels.iterator():
        cost = (parcel.weight * Decimal("0.5")
                + parcel.content_cost_usd * Decimal("0.01")) * rate
        parcel.delivery_cost = cost
        parcel.delivery_cost_calculated_at = timezone.now()
        parcel.save(update_fields=["delivery_cost",
                                   "delivery_cost_calculated_at"])
        count += 1
    logger.info("Рассчитано стоимостей: %s", count)
    return count
```

**Ручной запуск (отладка):**
- Management-команда `python manage.py calculate_delivery_costs`.

---

## 5. Кеширование (Redis)

| Ключ | Значение | TTL | Назначение |
|------|----------|-----|-----------|
| `usd_rub_rate` | float | 1 час | Курс USD/RUB |

**Логика получения курса:**

```python
def get_usd_rub_rate() -> Decimal:
    cached = redis.get("usd_rub_rate")
    if cached:
        return Decimal(cached)
    data = requests.get(CBR_URL, timeout=5).json()
    rate = Decimal(str(data["Valute"]["USD"]["Value"]))
    redis.set("usd_rub_rate", str(rate), ex=3600)
    return rate
```

---

## 6. Стандартизация ответов и ошибок

**Успешный ответ:**
```json
{
  "data": { ... },
  "meta": { "page": 1, "page_size": 20, "total": 42 }
}
```

**Ошибка:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Некорректные данные",
    "details": { "weight": ["Вес должен быть больше 0"] }
  }
}
```

**Коды ошибок:**

| HTTP | code | Ситуация |
|------|------|----------|
| 400 | `VALIDATION_ERROR` | Ошибка валидации |
| 404 | `NOT_FOUND` | Объект не найден |
| 409 | `CONFLICT` | Конфликт (посылка уже привязана) |
| 502 | `LLM_UNAVAILABLE` | LLM недоступна |
| 503 | `SERVICE_UNAVAILABLE` | Векторная БД/брокер недоступны |
| 504 | `LLM_TIMEOUT` | Таймаут LLM |

---

## 7. Логирование

- Формат: JSON или структурированный текст.
- Уровни: DEBUG (dev), INFO (prod).
- Логируются: запросы (метод, путь, статус, длительность), ошибки, результаты периодических задач.
- Кастомный middleware для HTTP-логов.

---

## 8. RAG-пайплайн

**Загрузка базы знаний (offline):**
1. Прочитать фиктивный текстовый файл с правилами.
2. Разбить на чанки (например, по 500 токенов с перекрытием).
3. Векторизовать каждый чанк.
4. Сохранить в Qdrant/ChromaDB.

**Обработка вопроса (online):**
1. Векторизовать вопрос.
2. Поиск top-K в векторной БД.
3. Собрать контекст.
4. Передать в LLM.
5. Вернуть ответ.

**Опционально:** использовать LangChain или LlamaIndex для пайплайна.

---

## 9. Docker-инфраструктура

**Сервисы в `docker-compose.yml`:**

| Сервис | Образ | Назначение |
|--------|-------|-----------|
| `web` | сборка проекта | Django-приложение |
| `db` | postgres:16 | Основная БД |
| `redis` | redis:7 | Кеш |
| `qdrant` | qdrant/qdrant | Векторная БД |
| `worker` | сборка проекта | Celery worker |
| `beat` | сборка проекта | Celery beat |
| `rabbitmq` | rabbitmq:3 | Брокер (доп.) |
| `mongo` | mongo:7 | Лог (доп.) |

**Запуск:** `docker-compose up`.

---

## 10. Swagger

- Подключить `drf-spectacular` или `drf-yasg`.
- Роут `/api/schema/` и `/api/docs/` (Swagger UI).
- Все эндпоинты документированы.