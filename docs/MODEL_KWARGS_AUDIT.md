# MODEL_KWARGS_AUDIT — конструкторы моделей с несуществующими аргументами и смежные дефекты

Дата: 2026-11-19. Режим: только расследование; рабочая БД **только чтение** (SELECT); правки кода/конфигов/тестов/миграций запрещены; внешняя отправка не выполнялась. `request_service.py`, `public_service.py`, `models/dispatch.py`, `shifts/tasks.py`, добавляемая миграция — читаются как есть, не меняются. Коммит — только этот отчёт через pathspec с проверкой состава до push.

Метод: AST по `backend/app` (212 файлов) — каждый вызов `ClassName(...)`, где ClassName — модель SQLAlchemy (`Base.registry.mappers`); kwargs сверены с `dir(Model)` (колонки + relationships + синонимы + гибриды + методы). Отдельно: NOT NULL без default/server_default (исключая autoincrement PK), отсутствующие в явных kwargs; присваивания `obj.attr=` на инференс-экземплярах моделей; FK-цели (`column.foreign_keys`) + SELECT-подсчёт неверных строк.

**Важно (текущее состояние):** пользователь ведёт правки — ряд дефектов прошлых аудитов уже устранён (Act(driver_name/distance_km/act_number) в diadoc/scheduler больше не встречаются; присваивания task.planned_start в shift_task_service устранены). Отчёт отражает ТЕКУЩЕЕ дерево.

---

## Приоритет 1 — ПАДЕНИЕ ОБРАБОТЧИКА (TypeError на неизвестный kwarg)

Declarative-конструктор бросает `TypeError: '<kw>' is an invalid keyword argument for <Model>` при первом реальном вызове → 500.

| # | Файл:строка | Модель | Неверные kwargs | Обработчик (маршрут) | Доказательство |
|---|---|---|---|---|---|
| 1.1 | `api/routes/shifts/tasks.py:407` | RequestAssignment | `assigned_by` | `create_request_from_shift` (POST /shifts/tasks/{task_id}/create-request) | mapper RequestAssignment: колонки request_id/vehicle_id/operator_id/planned_start/planned_end/status/actual_start/actual_end/created_at/id — **assigned_by отсутствует**; `dir(RequestAssignment)` не содержит assigned_by |
| 1.2 | `api/routes/shifts/templates.py:193` | ShiftTask | `planned_start`, `planned_end`, `created_by` | `apply_shift_templates` (POST /shifts/templates/apply) | mapper ShiftTask: request_id/assignment_id/operator_id/vehicle_id/shift_date/shift_number/odometer_start/moto_hours_start/odometer_distance/fuel_level_start/status/company_id/created_at/updated_at/id — **planned_start/planned_end/created_by отсутствуют** (planned_* есть только на RequestAssignment) |
| 1.3 | `services/bank_integration_service.py:107` | BankTransaction | `doc_number`, `doc_date`, `payer_inn`, `payer_name`, `payer_account`, `payee_inn`, `payee_name`, `payee_account`, `status` (9) | `sync_payments_to_db` ← `import_bank_payments` (POST /shifts/bank/import, **не опубликован**) | mapper BankTransaction: document_number/document_date/counterparty_inn/counterparty_name/counterparty_account/match_status/… — ни одного из 9 kwargs нет (правильные: document_number, document_date, counterparty_*, match_status) |

Дополнительно к 1.1/1.2: даже если убрать неверные kwargs, останется IntegrityError (см. Приоритет 2): 1.1 не задаёт NOT NULL `planned_start/planned_end`; 1.2 не задаёт NOT NULL `request_id`. Т.е. путь нерабочий дважды (TypeError маскирует IntegrityError).

---

## Приоритет 2 — NOT NULL без default, отсутствующие в конструкторе (IntegrityError)

AST-flagged 19 конструкторов с «missing required». **Проверка показала: все независимые случаи — ложные срабатывания `**kwargs`-раскрытия** (поля приходят из валидированной Pydantic-схемы через `**payload.model_dump()` / `**data`), либо это firebase-класс, не модель:

| Файл:строка | Модель | Причина ложного срабатывания |
|---|---|---|
| api/routes/contractors.py:103 | Contractor | `Contractor(**payload.model_dump(), company_id=…)` — type/name из схемы |
| api/routes/shifts/tasks.py:59 | ShiftTask | `ShiftTask(**payload.model_dump(), company_id=…)` — request_id/vehicle_id/shift_date из ShiftTaskCreate |
| services/request_service.py:510 | Request | `Request(**payload_data, company_id=, created_by=)` — planned_start/planned_end из схемы |
| services/vehicle_service.py:253 | Vehicle | `Vehicle(**vehicle_data)` — id_type/id_value/name из dict |
| services/telematics_service.py:25 | GpsPoint | `GpsPoint(**pd.model_dump(), received_at=…)` — vehicle_id/latitude/longitude/recorded_at из pd |
| api/routes/telematics.py:166 | Geofence | `Geofence(**payload.model_dump(), company_id=…)` — name/type из схемы |
| api/routes/telematics.py:248 | FuelTransaction | `FuelTransaction(**payload.model_dump(), total_cost=, company_id=)` — vehicle_id/transaction_type/volume/occurred_at из схемы |
| api/routes/telematics.py:558 | AlertRule | `AlertRule(company_id=, **payload.model_dump())` — name/rule_type из схемы |
| services/alert_engine.py:354 | AlertRule | `AlertRule(company_id=, **rule_data)` — name/rule_type из dict |
| services/fcm_service.py:76 | «Notification» | **firebase `messaging.Notification(title,body,data)`, НЕ модель app.Notification** — ложное совпадение имени |
| cli/seed_rbac.py:321/369/492/521/560, core/seed_data.py:302 | Category/Vehicle/Invoice/Act/Payout | сиды, `**data`-раскрытие |

**Реальные missing-required** существуют только внутри уже падающих TypeError-конструкторов (1.1 RequestAssignment без planned_start/planned_end; 1.2 ShiftTask без request_id; 1.3 BankTransaction без 8 обязательных) — они неактуальны, т.к. TypeError наступает раньше. **Независимых IntegrityError-путей не обнаружено.**
**Требует подтверждения:** полнота полей в `**payload` зависит от Pydantic-схем (ShiftTaskCreate/RequestCreate и др.) — если схема не требует NOT NULL поле, возможен IntegrityError; сплошная сверка схем с NOT NULL в этой задаче не выполнялась (охват ограничен конструкторами).

---

## Приоритет 3 — ПОТЕРЯ ЗНАЧЕНИЯ (присваивание немаппленного атрибута, SQLAlchemy не бросает)

`obj.field = value`, где field не колонка/связь/синоним/гибрид → значение кладётся на экземпляр и **не сохраняется** (тише падения).

| # | Файл:строка | Объект (модель) | Атрибут | Обработчик | Доказательство / нюанс |
|---|---|---|---|---|---|
| 3.1 | `services/request_service.py:727` | assignment (RequestAssignment) | `assigned_by` | `approve_response` | mapper RequestAssignment без assigned_by; значение «кто утвердил» теряется. Инференс подтверждён (assignment = db.get(RequestAssignment,…)) |
| 3.2 | `api/routes/shifts/geofence.py:70` | task (ShiftTask) | `actual_start` | `process_geofence_event` (POST /shifts/geofence/event) | mapper ShiftTask без actual_start (есть на RequestAssignment). **Опасно:** чтение `if not task.actual_start` ДО записи на немаппленном атрибуте бросит AttributeError при первом событии |
| 3.3 | `api/routes/shifts/geofence.py:109` | task (ShiftTask) | `actual_end` | `process_geofence_event` | то же; путь геозон латентен (shift_geofences/geofence_events пусты) |

Смежное (из PHANTOM_READS, тот же класс): `request_service.py:641` `ShiftTask(operator_id=getattr(vehicle,"current_driver_id",None))` — current_driver_id phantom (есть assigned_driver_id) → operator_id=None (значение теряется, но это kwarg с None, не немаппленное присваивание).

---

## Приоритет 4 — НЕВЕРНЫЕ ДАННЫЕ (подмена идентификаторов User/Contractor/Employee)

FK-цели (интроспекция): `RequestAssignment.operator_id → employees.contractor_id`; `ShiftTask.operator_id → employees.contractor_id`. `employees.contractor_id` — PK employees, ссылается на contractors.id. `User.id` — отдельная сущность (users.id).

| # | Файл:строка | Подмена | Последствие | Данные рабочей БД (SELECT) |
|---|---|---|---|---|
| 4.1 | `services/public_service.py:772` | `RequestAssignment(operator_id=getattr(current_user,"id",None))` — кладётся **User.id** в FK на **employees.contractor_id** | Для пользователя, чей User.id не является contractor_id → **FK-нарушение (IntegrityError, 500)** при отклике на заявку; для совпадающих id — семантически неверный оператор (откликнувшийся пользователь вместо водителя/собственника техники) | request_assignments: 1 строка, operator_id=4; `operator_id NOT IN (select contractor_id from employees)` = **0**. shift_tasks: 5 строк, operator_id=4; NOT IN employees = **0**. employees.contractor_id={3,4,8,10,11,12,13,14}; users.id={1,2,3,4,5,6,7,8,9,10,11,44}. Сейчас 0 неверных (id=4 совпадает), **латентно**: User.id {1,2,5,6,7,9,44} не contractor_id → отклик такого пользователя упадёт/запишет неверно |
| 4.2 | `services/request_service.py:641` | `ShiftTask(operator_id=getattr(vehicle,"current_driver_id",None))` — current_driver_id **phantom** (есть assigned_driver_id) → operator_id=**None** | Смена создаётся без оператора (потеря значения, operator_id nullable → не падает) | shift_tasks.operator_id все =4 (созданы иным путём); bulk-путь с current_driver_id ещё не породил строк с NULL (0/5 null) — латентно |

**Вердикт 4.1:** дефект кода подтверждён (User.id вместо contractor_id в FK); на ТЕКУЩИХ данных 0 неверных строк (совпадение id=4), риск латентный (FK-нарушение для не-contractor пользователей). Маршрут: public_service respond_to_request (marketplace-отклик).
**Требует подтверждения:** семантика operator_id в marketplace-отклике — должен ли это быть contractor_id собственника/водителя техники (а не откликнувшегося пользователя); и enforced ли FK физически (при enforced — IntegrityError, при не-enforced — неверные данные).

---

## Сводка по последствиям
1. **Падение обработчика (500):** 1.1 create_request_from_shift (RequestAssignment.assigned_by), 1.2 apply_shift_templates (ShiftTask.planned_start/end/created_by), 1.3 import_bank_payments (BankTransaction 9 kwargs, не опубликован).
2. **Потеря значения (тихо):** 3.1 approve_response assigned_by, 3.2/3.3 geofence actual_start/end (+ AttributeError-риск чтения), 4.2 bulk_response operator_id=None.
3. **Неверные данные / латентное падение:** 4.1 public_service operator_id=User.id (0 неверных строк сейчас, FK-риск для не-contractor пользователей).

## Что проверено и проблем НЕ найдено (охват)
- Все 19 «missing required» (Приоритет 2) — ложные `**kwargs`/firebase; независимых IntegrityError-путей нет.
- Прочие конструкторы моделей (Contractor/ShiftTask/Request/Vehicle/GpsPoint/Geofence/FuelTransaction/AlertRule/Invoice/Act/Payout/Category) используют валидные kwargs (`**schema` или явные существующие поля).
- Подмены operator_id/owner_id/driver_id = current_user.id/user.id: grep по app нашёл только public_service:772 (4.1); owner_id/driver_id подмен не обнаружено.
- Act(driver_name/distance_km/act_number), ShiftTask.planned_start присваивания в shift_task_service — в ТЕКУЩЕМ дереве отсутствуют (устранены пользователем).

## Требует подтверждения
- Полнота NOT NULL полей в Pydantic-схемах (`**payload`) — сплошная сверка схем не выполнялась.
- Семантика operator_id в marketplace-отклике (4.1) и физическая enforced-ность FK.
- Актуальность после миграции пользователя (models/dispatch.py правится): состав колонок RequestAssignment/ShiftTask может измениться — перепроверить mapper после применения миграции.

Все находки — отчёт; исправление решает пользователь. Ничего не правилось; БД только читалась.
