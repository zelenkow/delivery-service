# Sequence-диаграммы — Микросервис доставки посылок


## SEQ-01. Регистрация посылки

```plantuml
@startuml
!theme plain
autonumber

actor "Пользователь" as U
participant "API\n(Django/DRF)" as API
participant "Session\nMiddleware" as SM
participant "Serializer\n(валидация)" as S
database "PostgreSQL" as DB

U -> API : POST /api/parcels/\n{name, weight, type, content_cost_usd}
API -> SM : получить session_key
SM --> API : session_key (создать при отсутствии)
API -> S : validate(data)
alt данные невалидны
    S --> API : ошибки
    API --> U : 400 Bad Request\n{error: VALIDATION_ERROR}
else данные валидны
    S --> API : validated_data
    API -> DB : SELECT parcel_type WHERE id = type
    alt тип не найден
        DB --> API : пусто
        API --> U : 400 Bad Request\n{error: UNKNOWN_TYPE}
    else тип найден
        DB --> API : parcel_type
        API -> DB : INSERT parcel (session_key, ...)
        DB --> API : parcel.id
        API --> U : 201 Created {id}
    end
end

@enduml
```

---

## SEQ-02. Получение списка своих посылок

```plantuml
@startuml
!theme plain
autonumber

actor "Пользователь" as U
participant "API" as API
participant "Session\nMiddleware" as SM
database "PostgreSQL" as DB

U -> API : GET /api/parcels/?page=1&page_size=20\n&type=2&has_delivery_cost=false
API -> SM : получить session_key
SM --> API : session_key
API -> DB : SELECT parcel JOIN parcel_type\nWHERE session_key = ?\nAND type_id = ?\nAND delivery_cost IS NULL\nLIMIT 20 OFFSET 0
DB --> API : rows + total
API -> API : сериализация\n(delivery_cost = NULL -> "Не рассчитано")
API --> U : 200 OK\n{data: [...], meta: {page, page_size, total}}

@enduml
```

---

## SEQ-03. Получение данных о посылке по id

```plantuml
@startuml
!theme plain
autonumber

actor "Пользователь" as U
participant "API" as API
participant "Session\nMiddleware" as SM
database "PostgreSQL" as DB

U -> API : GET /api/parcels/{id}/
API -> SM : получить session_key
SM --> API : session_key
API -> DB : SELECT parcel JOIN parcel_type\nWHERE id = ? AND session_key = ?
alt не найдено
    DB --> API : пусто
    API --> U : 404 Not Found\n{error: NOT_FOUND}
else найдено
    DB --> API : parcel
    API --> U : 200 OK\n{name, weight, type, content_cost_usd, delivery_cost}
end

@enduml
```

---

## SEQ-04. RAG-вопрос службе поддержки

```plantuml
@startuml
!theme plain
autonumber

actor "Пользователь" as U
participant "API" as API
participant "Embedding\nService" as EMB
database "Векторная БД\n(Qdrant/ChromaDB)" as VDB
participant "LLM API" as LLM

U -> API : POST /api/support/ask/\n{question: "Можно ли отправить ноутбук?"}
API -> API : валидация question
alt question пустой
    API --> U : 400 Bad Request
else question валиден
    API -> EMB : embed(question)
    EMB --> API : vector
    API -> VDB : search(vector, top_k=5)
    alt векторная БД недоступна
        VDB --> API : ошибка
        API --> U : 503 Service Unavailable
    else поиск успешен
        VDB --> API : chunks[]
        API -> API : собрать контекст + промпт
        API -> LLM : generate(prompt)
        alt LLM недоступна/таймаут
            LLM --> API : ошибка/таймаут
            API --> U : 502/504
        else ответ получен
            LLM --> API : answer
            API --> U : 200 OK {answer, sources}
        end
    end
end

@enduml
```

---

## SEQ-05. Периодический расчёт стоимости доставки

```plantuml
@startuml
!theme plain
autonumber

participant "Celery Beat" as BEAT
participant "Celery Worker" as W
participant "Redis" as R
participant "API ЦБ РФ" as CBR
database "PostgreSQL" as DB
database "MongoDB\n(лог)" as MDB

BEAT -> W : каждые 5 минут\ncalculate_delivery_costs()
W -> R : GET usd_rub_rate
alt кеш есть
    R --> W : rate
else кеша нет
    R --> W : null
    W -> CBR : GET daily_json.js
    alt API недоступен
        CBR --> W : ошибка
        W -> W : логировать ошибку
    else API доступен
        CBR --> W : {Valute: {USD: {Value}}}
        W -> R : SET usd_rub_rate (TTL 1h)
        R --> W : OK
    end
end
W -> DB : SELECT parcel WHERE delivery_cost IS NULL
DB --> W : parcels[]
loop по каждой посылке
    W -> W : cost = (weight*0.5 + content_cost_usd*0.01) * rate
    W -> DB : UPDATE parcel SET delivery_cost, calculated_at
    W -> MDB : INSERT delivery_cost_log
end
W -> W : логировать количество обработанных

@enduml
```

---

## SEQ-06. Привязка посылки к транспортной компании (доп.)

```plantuml
@startuml
!theme plain
autonumber

actor "Компания A" as A
actor "Компания B" as B
participant "API" as API
database "PostgreSQL" as DB

par A -> API : POST /api/parcels/{id}/assign/\n{company_id: 1}
and B -> API : POST /api/parcels/{id}/assign/\n{company_id: 2}
end

API -> DB : UPDATE parcel\nSET company_id = ?\nWHERE id = ? AND company_id IS NULL

alt Компания A успела первой
    DB --> API : updated = 1 (A)
    API --> A : 200 OK
    DB --> API : updated = 0 (B)
    API --> B : 409 Conflict\n{current_company_id: 1}
else Компания B успела первой
    DB --> API : updated = 1 (B)
    API --> B : 200 OK
    DB --> API : updated = 0 (A)
    API --> A : 409 Conflict\n{current_company_id: 2}
end

@enduml
```

---

## SEQ-07. Регистрация посылки через RabbitMQ (доп.)

```plantuml
@startuml
!theme plain
autonumber

actor "Пользователь" as U
participant "API" as API
participant "RabbitMQ" as MQ
participant "Worker" as W
database "PostgreSQL" as DB
participant "Redis" as R

U -> API : POST /api/parcels/\n{...}
API -> API : валидация
alt брокер недоступен
    API --> U : 503 Service Unavailable
else брокер доступен
    API -> MQ : publish(parcel_data)
    MQ --> API : ack
    API --> U : 202 Accepted {task_id}
    MQ -> W : deliver(parcel_data)
    W -> R : GET usd_rub_rate
    R --> W : rate
    W -> W : рассчитать delivery_cost
    W -> DB : INSERT parcel (со стоимостью)
    alt успех
        W -> MQ : ack
    else ошибка
        W -> MQ : nack -> DLQ
    end
end

@enduml
```

---

## SEQ-08. Подсчёт суммы стоимостей по типам за день (доп.)

```plantuml
@startuml
!theme plain
autonumber

actor "Аналитик" as A
participant "API" as API
database "MongoDB" as MDB

A -> API : GET /api/reports/delivery-costs/?date=2026-09-28
API -> MDB : aggregate([\n  {$match: {calculated_at: день}},\n  {$group: {_id: "$type_id", total: {$sum: "$delivery_cost"}}}\n])
MDB --> API : [{type_id, total}, ...]
API --> A : 200 OK {report: [...]}

@enduml