# PHANTOM_READS_AUDIT — фантомные чтения и мёртвые литералы статусов

Дата: 2026-11-19. Режим: только расследование; рабочая БД **только чтение** (SELECT DISTINCT / интроспекция mapper). Правки кода/конфигов/миграций/тестов не выполнялись. Задачи не запускались (для доказательств крахов использованы уже полученные ранее traceback на копии + интроспекция).

Метод:
- **КЛАСС 1:** AST по `app/**` (212 файлов), обращения `obj.attr`/`Model.attr` в контексте Load; valid-набор = `dir(Model)` (покрывает columns, relationships, property/hybrid, методы, SQLA-атрибуты). Тип объекта: прямой доступ `Model.attr` (высокая надёжность), инференс `var = Model(...)`/`db.get(Model,...)`, эвристика имён (проверена по колонкам моделей, ложные отброшены). Особое внимание `select().where(Model.field == ...)`.
- **КЛАСС 2:** AST-коллектор строковых литералов в `Compare`/`.in_()` по полям статусов/типов (111 фильтров); сверка с Enum модели (`mapper.columns[type].enum_class`) **и** `SELECT DISTINCT` рабочей БД.

---

## Калибровка (известные примеры — подтверждение метода, не новые находки)

- **`scheduler.py:382 t.planned_start`** (monthly_auto_acts): подтверждено эмпирически в SCHEDULER_JOB_AUDIT (fad833c) — `AttributeError: 'ShiftTask' object has no attribute 'planned_start'` на 1-е числа при completed-смене. ShiftTask не имеет planned_start/planned_end (есть на RequestAssignment). Детектор этого аудита независимо флагует `task.planned_start` в mobile.py:96, tasks.py:389 (тот же класс).
- **`alert_service.py:98 User.is_active`**: **в текущем дереве УЖЕ ИСПРАВЛЕН** — строка 98 теперь `User.status == UserStatus.active` (незакоммиченные правки пользователя). Как новую находку НЕ выдаю. Метод подтверждён: User не имеет is_active (есть status:UserStatus; is_active только у UserSession), SQL `column "is_active" does not exist`.

---

## КЛАСС 1. Фантомные чтения (ранг по последствию)

### Деньги / документы

**P1. Финансовый отчёт по аренде молча пуст — `finance.py:689-698`.**
`func.sum(Rental.moto_hours)`, `.join(Vehicle, Rental.vehicle_id == Vehicle.id)`. У `Rental` **нет** `moto_hours` и **нет** `vehicle_id` (mapper: cols без обоих; rels client/items/request). Запрос падает AttributeError, обёрнут в `try/except Exception: results = []` (finance.py:701) → секция отчёта **всегда пустая**, ошибка проглочена. Достижим: маршрут finance (отчёт по технике). Деньги.
Доказательство: mapper Rental.cols = [actual_return_date, base_price, client_id, …, volume_rate] — без moto_hours/vehicle_id.

**P2. Маршруты банка падают — `shifts/bank.py`.**
- `:77 BankTransaction.status == "processed"` — у BankTransaction **нет** `status` (есть `match_status`). Фильтр падает сразу (AttributeError при построении запроса). Маршрут «непроведённые входящие платежи» → 500.
- `:295-300 t.payer_name / t.payer_inn / t.payee_name / t.status` (t — BankTransaction) — **нет** payer_name/payer_inn/payee_name/status (есть counterparty_name/counterparty_inn, match_status). Список транзакций падает при итерации.
- `:347 txn.doc_number` — **нет** doc_number (есть document_number).
- `bank_integration_service.py:98 BankTransaction.doc_number` — тот же фантом (маршрут импорта 1C/CSV `shifts/bank.py:59`).
Достижим: роутер shifts/bank. Деньги.
Доказательство: mapper BankTransaction.cols (amount, counterparty_*, document_number, document_date, match_status, …) — без status/doc_number/payer_*/payee_*.

**P3. Имя водителя в XML акта — `shifts/diadoc.py:485, 594`.**
`emp = db.get(Employee, …); driver_name = f"{emp.first_name} {emp.last_name}"`. У `Employee` **нет** first_name/last_name (mapper cols: contractor_id, fire_date, hire_date, position, role_in_system, salary_*, user_id; rels contractor/driver_profile). При существующем emp → AttributeError → экспорт XML акта (DriverName) падает. Имя хранится на Contractor/User, не на Employee. Документы заказчику.
Доказательство: mapper Employee.cols — без first_name/last_name.

**P4. Уведомления об одобрении/отклонении отклика молча не шлются — `request_service.py:656,662,673,679,774,826`.**
`user_id=assignment.assigned_by`, `manager.send_to_user(assignment.assigned_by, …)`. У `RequestAssignment` **нет** `assigned_by` (mapper cols: actual_end, actual_start, created_at, id, operator_id, planned_end, planned_start, request_id, status, vehicle_id). Чтение падает AttributeError, обёрнуто в `try/except Exception: pass` → уведомление инициатору молча не отправляется. (Плюс `assigned_by` пишется в :727 как фантомный атрибут — не персистится.)
Доказательство: mapper RequestAssignment.cols — без assigned_by.

### Планирование смен / чат / уведомления

**P5. Мобильный ввод топлива и маршрут смен падают — `shifts/mobile.py:96-97`, `shifts/tasks.py:389-390`.**
`if task.planned_start and task.planned_end:` (task — ShiftTask). ShiftTask без planned_start/planned_end → AttributeError. mobile.py:96 — расчёт расхода топлива при вводе заправки; tasks.py:389 — маршрут смен. Достижимы из роутеров.
Доказательство: mapper ShiftTask.cols — без planned_start/end; тот же класс, что monthly_auto_acts.

**P6. Чат смен падает — `shifts/chat.py:49-50`.**
`ChatMessage.room_id.in_(room_ids)`, `.order_by(ChatMessage.sent_at.desc())`. У ChatMessage **нет** room_id (есть chat_id) и **нет** sent_at (есть created_at). Без guard → AttributeError при построении запроса → маршрут сообщений чата смен падает.
Доказательство: mapper ChatMessage.cols = [attachments, chat_id, content, created_at, …] — без room_id/sent_at.

**P7. MAX-мессенджер: последние уведомления — `shifts/max_messenger.py:209,217,219`.**
`.order_by(Notification.created_at.desc())` — у Notification **нет** created_at (есть sent_at) → падение запроса. Далее `a.created_at` и `a.title or a.message` — у Notification нет message (есть body). Маршрут «последние уведомления» падает.
Доказательство: mapper Notification.cols = [alert_id, body, channel, id, is_read, read_at, sent_at, title, user_id] — без created_at/message.

**P8. Геозоны (известный класс) — `shifts/geofence.py:69,108`.**
`task.actual_start` / `task.actual_end` (ShiftTask) — нет таких колонок (есть на RequestAssignment). Латентно: shift_geofences/geofence_events пусты; чтение до записи опасно AttributeError. Подтверждение метода.

### Benign (фантомный атрибут, но guarded — НЕ отказ)
- `finance_service.py:317 act.contractor_id` — guard `hasattr(act,"contractor_id") and act.contractor_id` → ветка всегда False, fallback на `request.client_id` работает. Мёртвая ветка, не крах.
- `chat.py:395 ChatMessage.sent_at` — guard `hasattr(ChatMessage,"created_at")` → берётся created_at, sent_at не вычисляется. Не крах.

### Ложные срабатывания детектора (отброшены после проверки типа)
- `request.query/json/headers/url/method/client` — FastAPI Request, не модель Request.
- `t.*` в fuel_service/telematics_service (transaction_type/volume/total_cost/occurred_at/odometer) — FuelTransaction, атрибуты валидны; `t.*` в templates.py (weekday/start_time/end_time/is_active) — ShiftTemplate, валидны; `t.*` в shifts/admin.py (code/channel/subject/body) — NotificationTemplate, валидны.
- `a.severity` (telematics_service) — Alert, валиден; `a.planned_start/end` (vehicles.py:614) — RequestAssignment, валидны.
- `user.first_name` (telegram_bot:66,73) — telegram.User (python-telegram-bot), не модель User.
- `vehicle.last_seen` (telematics_tasks:225-236) — Row с labeled column `subquery.c.last_seen` (func.max(GpsPoint.recorded_at)), не поле Vehicle.
- `t.setStyle` (reportlab) — Table; `statement.validate` — объект парсера.

---

## КЛАСС 2. Литералы статусов, которых не существует (ранг по последствию)

### Деньги / документы

**S1. Еженедельный дайджест бухгалтерам всегда пуст — `weekly_digest_service.py:362`.**
`Employee.role_in_system.in_(["accountant","admin","manager","owner"])`. **DB DISTINCT employee.role_in_system = driver(5), operator(2), NULL(1)** — ни одного accountant/admin/manager/owner. `_find_accountants` всегда возвращает [] → дайджест 0 recipients (подтверждено прогоном планировщика: «No accountants found» ×4). Фильтр мёртв против текущих данных; данные (driver/operator) код дайджеста не знает. Финансовый дайджест молча не уходит.
Доказательство: SQL DISTINCT выше + лог прогона weekly_digest (SCHEDULER_JOB_AUDIT).
**Требует подтверждения:** должны ли существовать сотрудники с ролью accountant, либо фильтр использует не тот словарь ролей.

### Уведомления / интерфейс

**S2. Счётчик свободной техники всегда 0 — `shifts/max_messenger.py:132,181`.**
`Vehicle.status == "available"`. **DB DISTINCT vehicles.status = free(14), busy(1), maintenance(1)** — «available» нет. Команда «Статус» показывает «Свободной техники: 0» при 14 свободных. Канонический статус свободной техники — `free` (telegram_bot:235 использует `free` корректно, DB использует `free`). Несогласованность словаря: available vs free.
Доказательство: SQL DISTINCT vehicles.status; mapper Vehicle.status — String (без Enum-ограничения).
Смежное: DB содержит `busy`(1) (ставится seed_rbac:344/seed_data:282), но ни один фильтр в коде не ссылается на «busy» — данные, которые код не обрабатывает в явную.

**S3. Админ-панель: системные уведомления — `admin.py:132`.**
`Notification.channel == "system"`. **DB DISTINCT notification.channel = in_app(15)** — «system» нет; create_notification шлёт channel="in_app". Фильтр мёртв (системных уведомлений нет). Косметика.
**Требует подтверждения:** предполагается ли канал system вообще.

### Планирование / данные, которые код не знает

**S4. RequestAssignment: два пути создания с разными статусами — требует подтверждения.**
`request_service.py:150` создаёт `status="planned"`; `public_service.py:783` создаёт `status="pending_approval"`. Approval-workflow (`request_service.py:613,627,721,735,807`) фильтрует **только** `pending_approval`. **DB DISTINCT request_assignments.status = planned(1)** — назначение, созданное request_service, в workflow одобрения не попадает. `vehicles.py:601` фильтрует [planned,confirmed,active] — planned там обрабатывается. Неоднозначно: возможно, прямое назначение (planned) и не должно проходить одобрение. **Требует подтверждения** семантики двух путей.

**S5. Vehicle.status: мёртвые значения фильтров — требует подтверждения.**
`vehicles.py:589` [repair, decommissioned, sold], `scheduled_tasks.py:28` "archived", `public_service.py:742` [maintenance, repair, decommissioned]. DB vehicles.status = free/busy/maintenance — repair/decommissioned/sold/archived отсутствуют. Фильтры сейчас пусты (data-dependent). **Требует подтверждения:** ставятся ли эти статусы где-либо (если нет — мёртвые ветки; если ставятся вручную — данные вне кода).

### Калибровка — проверено, РАБОТАЕТ (не находка)
**Request.status == "new" (`scheduler.py:936`, гейдж pending_requests):** «new» **входит** в RequestStatus Enum (new/processing/assigned/confirmed/released/in_progress/completed/signed/closed/cancelled/disputed/has_responses/expired/draft) **и** DB DISTINCT requests.status = new(27), assigned(2). Гейдж requests_pending = 27 = DB new. Premise калибровочного примера («new невалиден → вечный ноль») **не подтвердился** — гейдж работает.

---

## Что проверено и проблем НЕ найдено (охват)

**КЛАСС 2 — все литералы статусов валидны относительно Enum и/или DB:**
- Request.status: new/processing/assigned/confirmed/in_progress/has_responses/completed/closed/cancelled — все в Enum; DB new/assigned известны коду.
- ShiftTask.status: planned/confirmed/in_progress/completed — в Enum; DB draft/signed_by_operator/completed известны.
- ShiftReport.status, Act.status (draft/sent_to_edo/signed), Invoice.status (draft/sent/overdue/paid), Payout.status, MaintenanceOrder.status, User.status (active), Alert.status (resolved) — все литералы в соответствующих Enum (DocumentStatus/UserStatus/AlertStatus и др.).
- Contractor.type (client/employee) = DB employee(7)/client(4). FuelTransaction.transaction_type (refuel/drain) = DB refuel(7)/drain(2).
- BankTransaction.match_status: DB unmatched/auto_matched/manual_matched; код использует MatchStatus.unmatched (валиден).

**КЛАСС 1:** прямые фантомные чтения `Model.attr` вне фильтров и чтения на инференс-экземплярах проверены сплошняком по 212 файлам; ложные эвристики отброшены по колонкам моделей (список выше). Benign-guarded случаи (hasattr) не являются отказами.

---

## Сводка приоритетов
1. **P1/P2/P3** — деньги/документы: фин-отчёт по аренде молча пуст; маршруты банка падают; XML акта без имени водителя (крах).
2. **S1** — финансовый дайджест бухгалтерам всегда пуст (роль не совпадает с данными).
3. **P4/P5/P6/P7** — уведомления об одобрении молча не шлются; мобильный ввод топлива/маршрут смен/чат смен/MAX-уведомления падают.
4. **S2/S3** — счётчик свободной техники всегда 0 (available vs free); системные уведомления админки пусты.
5. **S4/S5** — требует подтверждения (статусы назначений и техники).
6. Калибровка Request.status "new" — работает; User.is_active — уже исправлен в дереве.

Все находки — отчёт; исправление решает пользователь. Ничего не правилось; рабочая БД только читалась.
