# Архитектура C4 — Микросервис доставки посылок


## C4 Level 1 — Контекстная диаграмма

Показывает систему в окружении внешних акторов и систем.

```plantuml
@startuml
!theme plain
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

title Контекстная диаграмма — Служба доставки посылок

Person(user, "Пользователь", "Анонимный клиент, идентифицируется по сессии")
Person(company, "Транспортная компания", "Привязывает посылки (доп. задание)")
Person(analyst, "Аналитик", "Запрашивает отчёты (доп. задание)")

System(delivery, "Сервис доставки посылок", "Регистрация посылок, расчёт стоимости, RAG-поддержка")

System_Ext(cbr, "API ЦБ РФ", "Курс USD/RUB (daily_json.js)")
System_Ext(llm, "LLM API", "OpenAI / YandexGPT / GigaChat / локальная")

Rel(user, delivery, "Регистрирует посылки, смотрит список, задаёт вопросы", "HTTPS/JSON")
Rel(company, delivery, "Привязывает посылку к себе", "HTTPS/JSON")
Rel(analyst, delivery, "Запрашивает отчёт по типам", "HTTPS/JSON")
Rel(delivery, cbr, "Получает курс USD/RUB", "HTTPS")
Rel(delivery, llm, "Отправляет промпт, получает ответ", "HTTPS")

@enduml
```

---

## C4 Level 2 — Диаграмма контейнеров

Показывает основные технические контейнеры системы.

```plantuml
@startuml
!theme plain
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

title Диаграмма контейнеров — Сервис доставки посылок

Person(user, "Пользователь")
Person(company, "Транспортная компания")

System_Boundary(delivery, "Сервис доставки посылок") {
    Container(web, "Web API", "Django + DRF", "REST API, валидация, сессии, Swagger")
    Container(worker, "Celery Worker", "Python", "Периодический расчёт стоимости, обработка очереди")
    Container(beat, "Celery Beat", "Python", "Планировщик задач (каждые 5 минут)")
    ContainerDb(db, "PostgreSQL", "БД", "Посылки, типы посылок")
    ContainerDb(redis, "Redis", "Кеш", "Курс USD/RUB")
    ContainerDb(vdb, "Qdrant / ChromaDB", "Векторная БД", "Эмбеддинги базы знаний")
    ContainerDb(mongo, "MongoDB", "БД (доп.)", "Лог расчётов стоимости")
    ContainerQueue(mq, "RabbitMQ", "Брокер (доп.)", "Очередь регистрации посылок")
}

System_Ext(cbr, "API ЦБ РФ")
System_Ext(llm, "LLM API")

Rel(user, web, "Использует", "HTTPS/JSON")
Rel(company, web, "Привязывает посылку", "HTTPS/JSON")
Rel(web, db, "Читает/пишет", "SQL")
Rel(web, redis, "Кеширует курс", "Redis protocol")
Rel(web, vdb, "Векторный поиск", "gRPC/HTTP")
Rel(web, llm, "Генерация ответа", "HTTPS")
Rel(web, mq, "Публикует сообщения (доп.)", "AMQP")
Rel(beat, worker, "Запускает задачу", "Celery")
Rel(worker, db, "Обновляет стоимости", "SQL")
Rel(worker, redis, "Читает курс", "Redis protocol")
Rel(worker, cbr, "Запрашивает курс", "HTTPS")
Rel(worker, mongo, "Пишет лог (доп.)", "MongoDB protocol")
Rel(worker, mq, "Читает очередь (доп.)", "AMQP")

@enduml
```

---

## C4 Level 3 — Диаграмма компонентов (Web API)

Декомпозиция контейнера Web API.

```plantuml
@startuml
!theme plain
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml

title Диаграмма компонентов — Web API

Container_Boundary(web, "Web API (Django)") {
    Component(urls, "URL Router", "Django URLs", "Маршрутизация запросов")
    Component(session_mw, "Session Middleware", "Django", "Идентификация по сессии")
    Component(log_mw, "Logging Middleware", "Custom", "Логирование запросов")
    Component(parcel_view, "ParcelViewSet", "DRF", "CRUD посылок, фильтры, пагинация")
    Component(type_view, "ParcelTypeView", "DRF", "Справочник типов")
    Component(support_view, "SupportView", "DRF", "RAG-эндпоинт")
    Component(assign_view, "AssignView", "DRF", "Привязка к компании (доп.)")
    Component(report_view, "ReportView", "DRF", "Отчёт по типам (доп.)")
    Component(serializers, "Serializers", "DRF", "Валидация и сериализация")
    Component(rag_service, "RAG Service", "Python", "Векторизация, поиск, промпт")
    Component(cache_service, "Cache Service", "Python", "Работа с Redis")
    Component(error_handler, "Error Handler", "DRF", "Стандартизация ошибок")
}

ContainerDb(db, "PostgreSQL")
ContainerDb(redis, "Redis")
ContainerDb(vdb, "Qdrant/ChromaDB")
System_Ext(llm, "LLM API")

Rel(urls, parcel_view, "маршрутизирует")
Rel(urls, type_view, "маршрутизирует")
Rel(urls, support_view, "маршрутизирует")
Rel(urls, assign_view, "маршрутизирует")
Rel(urls, report_view, "маршрутизирует")
Rel(session_mw, parcel_view, "передаёт session_key")
Rel(log_mw, parcel_view, "логирует")
Rel(parcel_view, serializers, "использует")
Rel(parcel_view, db, "ORM")
Rel(type_view, db, "ORM")
Rel(assign_view, db, "атомарный UPDATE")
Rel(support_view, rag_service, "вызывает")
Rel(rag_service, vdb, "векторный поиск")
Rel(rag_service, llm, "генерация")
Rel(cache_service, redis, "кеш курса")
Rel(error_handler, parcel_view, "обрабатывает ошибки")

@enduml
```

---

## Компоненты и их ответственность

| Компонент | Ответственность |
|-----------|-----------------|
| URL Router | Маршрутизация HTTP-запросов |
| Session Middleware | Идентификация пользователя по сессии |
| Logging Middleware | Логирование запросов |
| ParcelViewSet | Регистрация, список, детали посылок |
| ParcelTypeView | Справочник типов |
| SupportView | RAG-эндпоинт |
| AssignView | Привязка к компании |
| ReportView | Отчёт по типам |
| Serializers | Валидация и сериализация |
| RAG Service | Векторизация, поиск, формирование промпта |
| Cache Service | Работа с Redis |
| Error Handler | Стандартизация ошибок |

---

## Технологические решения

| Решение | Обоснование |
|---------|-------------|
| Django + DRF | Требование задания, встроенные сессии, ORM, Swagger |
| PostgreSQL | Требование задания, надёжность, поддержка частичных индексов |
| Redis | Быстрый кеш курса, требование задания |
| Qdrant/ChromaDB | Требование задания для RAG |
| Celery + Beat | Периодические задачи, масштабируемость |
| RabbitMQ | Доп. задание, асинхронная регистрация |
| MongoDB | Доп. задание, хранение лога расчётов |
| Docker Compose | Требование задания, единый запуск |

---

## Диаграмма развёртывания (Docker)

```plantuml
@startuml
!theme plain

node "Docker Host" {
    node "web" as web
    node "worker" as worker
    node "beat" as beat
    database "postgres" as pg
    database "redis" as rd
    database "qdrant" as qd
    database "mongo" as mg
    queue "rabbitmq" as mq
}

cloud "API ЦБ РФ" as cbr
cloud "LLM API" as llm

web --> pg
web --> rd
web --> qd
web --> llm
web --> mq
worker --> pg
worker --> rd
worker --> cbr
worker --> mg
worker --> mq
beat --> worker

@enduml