# SILENT_NOOP_AUDIT — данные собираются/вычисляются и молча выбрасываются

Дата: 2026-11-19. Режим: **только чтение** (AST + интроспекция mapper, `SELECT count` на живой БД, запросы к Prometheus `/api/v1/query`). Никаких правок кода/конфигов/миграций и никаких INSERT/UPDATE/DELETE/ALTER не выполнялось.

Важно: в дереве есть **незакоммиченные правки пользователя** (`backend/app/models/shift.py`, `mobile_shift_service.py`, `vehicle_readings_service.py`, миграция `c8d2e3f4a5b6_shift_meter_readings`). Аудит отражает ТЕКУЩЕЕ состояние дерева; образцы A–D частично закрыты этими правками (см. §6). Находки в незакоммиченных файлах помечены явно.

---

## 1. Методология и охват

| Проверка | Инструмент | Охват |
|---|---|---|
| 1. Присваивания `obj.attr=` не в mapper | AST + `Base.registry.mappers` (`mapper.attrs`/`columns` + дескрипторы) | 60 моделей, 496 колонок, 212 файлов `app/**` |
| 1b. Неверные kwargs конструктора `Model(attr=)` | AST Call + mapper | те же 212 файлов |
| 2. `getattr(obj,"name",default)` не в mapper | AST + mapper (per-model и global) | те же |
| 3. Колонки 0% заполнены при непустой таблице | `SELECT count(*), count(col)` per-table (sync engine) | 79 public-таблиц |
| 4. Неиспользуемые параметры endpoint (Form/Body/Query/File/Path) | AST decorator `@router.*` + Name-анализ тела | все роуты |
| 5. Метрики объявлены, но не выставляются | grep вызовов хелперов/`.set/.inc/.labels` | 12 метрик `app/core/metrics.py` |
| 6. Селекторы правил не матчат серий | Prometheus `/api/v1/query` (факт, не чтение) | 20 правил `monitoring/alert_rules.yml` |

Интроспекция: `MODELS=60 TOTAL_COLUMNS=496 FILES=212`. Модели и их атрибуты выгружены через `inspect(Model).mapper` (учтены columns + relationships + property/hybrid-дескрипторы, чтобы не ложно флагать легитимные атрибуты).

---

## 2. Находки, ранжированные по последствию (деньги и документы заказчику — выше косметики)

### Класс I — документы заказчику и деньги

**F1. Генерация актов сломана (TypeError) + часы всегда 0.**
`backend/app/api/routes/shifts/diadoc.py:596` — `Act(... driver_name=driver_name, distance_km=float(distance) ...)`. У `Act` **нет** колонок `driver_name` и `distance_km`.
Доказательство (конструирование в памяти, без записи в БД):
```
Act(driver_name) -> TypeError: 'driver_name' is an invalid keyword argument for Act
Act(distance_km) -> TypeError: 'distance_km' is an invalid keyword argument for Act
```
Дополнительно `diadoc.py:571-580`: `hours=0; if getattr(t,"planned_start",None) and getattr(t,"planned_end",None): hours=...` — `planned_start/planned_end` на `ShiftTask` отсутствуют (есть только на `RequestAssignment`) → guard всегда False → **hours всегда 0** → `total_amount = hourly_rate*0 = 0`.
Смежное: `backend/app/tasks/scheduler.py:389` — `Act(act_number=...)`: у Act `document_number`, не `act_number` → `TypeError: 'act_number' is an invalid keyword argument for Act`.
Последствие: маршруты/задача генерации актов падают при первом создании; даже при исправлении kwargs суммы нулевые. Акты заказчику не формируются. В БД 19 актов, но `acts.hours_worked/vehicle_id/driver_id/shift_task_id/counterparty_inn/counterparty_name/signature/signed_at/pdf_url` = **0/19** (созданы иным путём/сидом, эти пути не работают).

**F2. Импорт банковских выписок сломан (TypeError) — деньги.**
`backend/app/services/bank_integration_service.py:107` — `BankTransaction(doc_number=, doc_date=, payer_inn=, payer_name=, payer_account=, payee_inn=, payee_name=, payee_account=, status=)` — **9 неверных kwargs**.
Фактические атрибуты BankTransaction (mapper): `document_number, document_date, counterparty_inn, counterparty_name, counterparty_account, direction, match_status, ...` — имена не совпадают.
Доказательство:
```
BankTransaction(doc_number) -> TypeError: 'doc_number' is an invalid keyword argument for BankTransaction
BankTransaction(payer_inn)  -> TypeError: 'payer_inn' is an invalid keyword argument for BankTransaction
```
Последствие: импорт выписки падает; `bank_transactions.matched_act_id` = 0/48 (сопоставление с актами не выполняется). 48 строк созданы иным путём.

**F3. УПД/акты без госномера техники.**
`backend/app/api/routes/shifts/diadoc.py:477` — `SubElement(act,"VehicleRegNumber").text = getattr(vehicle,"plate_number","") or ""`. `Vehicle.plate_number` **ABSENT** (mapper). Реальные поля: `psm_number`, `id_value`, `vin`, `is_custom_number`.
Доказательство: `Vehicle.plate_number : ABSENT`; `vehicles.psm_number` = 0/16 (тоже не заполнен).
Последствие: XML акта/УПД уходит заказчику с пустым `VehicleRegNumber`. Контраст: `map.py:196` корректно использует `psm_number`.

**F4. SMS водителю никогда не отправляется.**
`backend/app/api/routes/shifts/notifications.py:25` — `phone = getattr(profile,"phone",None) or getattr(profile,"contact_phone",None)`, где `profile = db.get(DriverProfile, driver_id)`. У `DriverProfile` **нет** `phone`/`contact_phone` (они на `Contractor`/`Employee`).
Доказательство: `DriverProfile` mapper attrs не содержат phone/contact_phone; `Contractor.contact_phone` существует (contractor.py:50), но читается не с того объекта.
Последствие: всегда `phone=None` → лог "No phone for driver profile" → `return False`. SMS-уведомления водителям молча не работают.

**F5. Наработка машины не обновляется через legacy-маршрут отчёта (остаток образца D).**
`backend/app/api/routes/shifts/reports.py:267 submit_shift_report` принимает `payload.operator_moto_hours/operator_odometer/operator_fuel_used`, сохраняет в `ShiftReport.operator_*`, переводит в `client_review`, но **не обновляет** `vehicle.odometer_km/engine_hours` и не вызывает `apply_shift_readings`. `reports.py:303 approve_and_sign` фиксирует `final_* = operator_*`, но наработку машины тоже не трогает.
Доказательство: `vehicles.odometer_km` = **0/16** (NULL у всех); `apply_shift_readings` вызывается только в `driver.py:132/209` и `mobile_shift_service.py:100`, но НЕ в `reports.py`.
Последствие: если оператор отправляет отчёт через этот маршрут, регламент ТО стоит на сидовых числах.
**Требует подтверждения:** `operator_*` здесь семантически «выработка за смену» (разность), а не накопленное показание — обновлять `vehicle.engine_hours` напрямую из них нельзя (нужен `*_end`). Нужно решить: (а) активен ли маршрут `reports.py` параллельно с `driver.py`, (б) должен ли он переводить выработку в показание. Помечаю как неоднозначное, не утверждаю баг.

**F6. Excel выплат без владельца.**
`backend/app/services/public_service.py:933` — `ws.cell(... value=getattr(p,"owner_name","") or "")`, где `p` — объект выплаты (`p.payout_date`). `owner_name` **ABSENT** во всех моделях.
Доказательство: global-phantom `getattr(p,'owner_name')`; `owner_name` не встречается ни в одном mapper.
Последствие: колонка «владелец» в финансовом Excel-отчёте по выплатам всегда пуста.

### Класс II — планирование смен и ТО

**F7. Обновление смены теряет плановые время/создателя.**
`backend/app/services/shift_task_service.py:76/78` — `task.planned_start = datetime.fromisoformat(...)` / `task.planned_end = ...`. `ShiftTask.planned_start/planned_end` **ABSENT** (есть на `RequestAssignment`). Присваивание кладёт атрибут на экземпляр; `db.commit(); db.refresh(task)` перезагружает из БД и стирает его.
`backend/app/api/routes/shifts/templates.py:193` — `ShiftTask(planned_start=, planned_end=, created_by=)` → все три **TypeError** (proof: `ShiftTask(planned_start) -> TypeError`, `ShiftTask(created_by) -> TypeError`).
Последствие: API обновления смены принимает плановые время и рапортует успех, но они не сохраняются; создание смены из шаблона падает. Связано с F1 (diadoc читает те же фантомные `planned_*` → пустые PlannedStart/End в XML).

**F8. Геозоны: фактическое время старта/финиша смены не сохраняется (латентно).**
`backend/app/api/routes/shifts/geofence.py:70` — `if not task.actual_start: task.actual_start = ts`; `:109` — `if not task.actual_end: task.actual_end = ts`. `ShiftTask.actual_start/actual_end` **ABSENT** (есть на `RequestAssignment`).
Доказательство: cross-model detector + mapper (`ShiftTask` valid без actual_start/end).
Последствие: авто-старт/финиш по геозоне не фиксирует время. **Требует подтверждения / латентно:** таблицы `shift_geofences`, `geofence_events` пусты (путь не используется); кроме того, чтение `task.actual_start` ДО записи на незамапленном атрибуте бросит `AttributeError` при первом событии — то есть путь не просто тихий, а потенциально падающий. Не утверждаю активный баг.

**F9. Утверждение назначения теряет «кто утвердил».**
`backend/app/services/request_service.py:727` — `assignment.assigned_by = user_id` (RequestAssignment, **ABSENT** `assigned_by`).
`backend/app/api/routes/shifts/tasks.py:401` — `RequestAssignment(assigned_by=...)` → `TypeError: 'assigned_by' is an invalid keyword argument for RequestAssignment`.
Последствие: аудит «кто утвердил отклик» не сохраняется; создание назначения через tasks.py падает.

**F10. Смена создаётся без оператора.**
`backend/app/services/request_service.py:641` — `operator_id=getattr(vehicle,"current_driver_id",None)`. `Vehicle.current_driver_id` **ABSENT**; реальное поле — `assigned_driver_id` (PRESENT).
Доказательство: `Vehicle.current_driver_id : ABSENT`, `Vehicle.assigned_driver_id : PRESENT`.
Последствие: при создании ShiftTask из утверждённого назначения `operator_id` всегда None → смена без закреплённого водителя.

**F11. Guard правдоподобия выработки инертен (незакоммиченный файл пользователя).**
`backend/app/services/vehicle_readings_service.py:84/87` — `getattr(task,"actual_start_at",None)` / `getattr(task,"actual_end_at",None)`. `ShiftTask.actual_start_at/actual_end_at` **ABSENT** (и имена не совпадают с `RequestAssignment.actual_start/actual_end`).
Доказательство: mapper `ShiftTask` без actual_start_at/end_at; `end_at` всегда None → блок `if start_at is not None and end_at is not None:` никогда не выполняется.
Последствие: проверка «выработка > длительности смены» (анти-фрод) никогда не срабатывает. Файл — незакоммиченная правка пользователя; сообщаю как находку в текущем дереве.

**F12. Акт ТО без владельца техники.**
`backend/app/api/routes/maintenance.py:609-610` — `getattr(order.vehicle,"owner_name",None) or getattr(order.vehicle,"contractor_name",None) or "Не указан"`. Оба **ABSENT** на Vehicle (есть `owner_id` FK).
Доказательство: `Vehicle.owner_name : ABSENT`, `Vehicle.contractor_name : ABSENT`; комментарий «пробуем разные варианты имени поля» — оба варианта фантомные.
Последствие: `vehicle_owner` в данных акта ТО всегда «Не указан».

### Класс III — телеметрия, метрики, интерфейс

**F13. GPS не несёт моточасы → наработка из телематики не обновляется.**
`gps_points.engine_hours` = **0/6905** (также `gps_best/gps_stage/gps_points_bak3.engine_hours` = 0). Запись в коде есть: `telematics_service.py:343 engine_hours=engine_hours`, `:746 engine_hours=pdata.get("engine_hours")`, `gps_providers/base.py:149 engine_hours=raw.get("engine_hours")`.
Доказательство: SQL-count 0/6905 при непустой таблице + наличие записи в коде → случай C (источник всегда None).
Последствие: провайдер GPS не отдаёт engine_hours (или адаптер не маппит) → `vehicle.engine_hours` не обновляется из телематики; регламент ТО зависит только от ручного ввода/сида. **Требует подтверждения:** какой провайдер активен и отдаёт ли он моточасы вообще.

**F14. Мёртвые метрики Prometheus (объявлены + хелпер, но не вызываются).**
`backend/app/core/metrics.py`: `auth_attempts_total` (:24), `auth_failures_total` (:30), `telematics_events_total` (:56). Хелперы `record_auth_attempt` (:172), `record_auth_failure` (:177), `record_telematics_event` (:182) **не вызываются нигде** в `app/**`.
Доказательство: grep `record_auth_attempt|record_auth_failure|record_telematics_event|auth_attempts_total|auth_failures_total` — только определения в metrics.py, ни одного call-site.
Последствие: мониторинг auth-попыток/неудач (brute-force) и телематической нагрузки слеп. Остальные метрики живые (см. §5).

**F15. Список актов без водителя.** `diadoc.py:314` — `getattr(a,"driver_name",None) or ""`; `Act.driver_name` ABSENT (есть `driver_id`). → `driver_name` в списке актов всегда "".

**F16. Карта без типа техники.** `map.py:194` — `getattr(vehicle,"type",None)`; `Vehicle.type` ABSENT (есть `category`, `model_name`). → `vehicle_type` всегда None.

**F17. Админ-дашборд: тип сущности пуст.** `admin.py:446` — `getattr(a,"entity_type","")`; `AuditLog.entity_type` ABSENT, реальное поле `resource_type`. → recent_actions.entity всегда "".

**F18. Геозона в уведомлении «N/A».** `geofence.py:137` — `getattr(sg,"name","N/A")`; `ShiftGeofence.name` ABSENT (имя на `Geofence` через `geofence_id`). → dispatcher видит геозону «N/A».

**F19. Список смен водителя без адреса/описания.** `driver.py:99-100` — `getattr(t,"address",None)` / `getattr(t,"description",None)`; `ShiftTask.address/description` ABSENT. → всегда None.

### Требует подтверждения (не утверждаю)
- `rental_service.py:878/910` — `getattr(client/owner,"user_id",None)`: `client/owner` интерпретируются как Contractor; `user_id` есть на связной модели (contractor.py:90), не факт что на самом Contractor. Нужно уточнить тип объекта и наличие связи contractor→user.
- Семантика и активность `reports.py` submit/approve (F5).
- Активный GPS-провайдер и наличие моточасов в его выдаче (F13).
- Какие именно пути создали 19 актов и 48 банковских транзакций при падающих конструкторах (F1/F2) — сид или иной маршрут.

---

## 3. Проверка 3: колонки 0% заполнены (scan 79 таблиц, read-only)

`TABLES_SCANNED=79`, `ZERO_FILLED_COLUMNS=144`, пустых таблиц 24.

Бизнес-значимые 0%-колонки (непустая таблица) и класс:
| Колонка | Заполнено | Пишется в коде? | Класс |
|---|---|---|---|
| `vehicles.odometer_km` | 0/16 | да (`vehicle_readings_service.py:116`) | C (новый поток не использован) |
| `vehicles.next_maintenance_km/last_maintenance_km/maintenance_interval_km` | 0/16 | требует проверки | км-регламент ТО не настроен |
| `shift_tasks.odometer_start/moto_hours_start/odometer_distance` | 0/5 | да (`apply_shift_readings`) | C (образец C; поток не использован) |
| `shift_tasks.fuel_level_start` | 0/5 | запись не найдена | мёртвое поле (кандидат) |
| `shift_reports.odometer_end/moto_hours_end` | 0/6 | да (`apply_shift_readings`) | C |
| `shift_reports.operator_signature/client_signature/signed_at` | 0/6 | да (`reports.py:283/322`) | подписи не сохранялись (путь не использован) |
| `acts.hours_worked/vehicle_id/driver_id/counterparty_*/signature/signed_at` | 0/19 | да, но пути падают (F1) | C через сломанный путь |
| `gps_points.engine_hours/altitude/signal_quality/device_id` | 0/6905 | да (`telematics_service`) | C (источник None, F13) |
| `requests.actual_start/actual_end/final_amount/requirements` | 0/29 | `final_amount` да (`request_service.py:1016`) | завершение заявок не выполнялось |
| `companies.diadoc_api_key/diadoc_box_id` | 0/4 | да (EdoSettings) | не настроено (не баг) |
| `uploaded_files.vehicle_id/contractor_id/payout_id` | 0/468 | требует проверки | связи файлов не проставлены |

Полный список 144 колонок и 24 пустых таблиц получен scan-скриптом (`SELECT count(*), count(col)` по каждой public-таблице); пустые таблицы: alert_rules, auto_assign_rules, company_cost_rates, device_tokens, disputes, document_archive, downtime_events, edo_send_logs, employee_certificates, engine_hours_logs, geofence_events, gps_sync_logs, notification_templates, pre_shift_checklists, rental_items, rentals, reviews, shift_audit_log, shift_data_reconciliations, shift_fuel_entries, shift_geofences, shift_template_exclusions, shift_templates, vehicle_checklist_configs.

Разделение классов: «0% + пишется в коде» = случай C (данные не персистятся / поток не использован); «0% + не упоминается на запись» = мёртвое поле (другой класс, требует отдельного решения об удалении — не делаю).

---

## 4. Проверка 4: параметры endpoint

Синтаксически неиспользуемых параметров `Form/Body/Query/File/Path/Header/Cookie` в теле endpoint-функций: **0** (AST: имя параметра не встречается как Name в теле). Образец D — **семантический** noop (параметр используется, сохраняется в ShiftReport, но не пропагируется в наработку машины), поэтому синтаксический детектор его не ловит; он разобран в F5 чтением потока.

---

## 5. Проверка 5: метрики — что живо (не найдено проблем)

Живые (выставляются в коде):
- `vehicles_active`, `requests_pending`, `alerts_active`, `db_connections_active` — `scheduler.py:974/979/989/999` (комментарий :950 отмечает, что раньше сеттеры не вызывались — теперь исправлено).
- `maintenance_due_without_order` — `scheduler.py:997`.
- `scheduler_job_failures_total`, `scheduler_job_missed_total` — `scheduler.py:40/50` (event-driven).
- `cache_hits_total`, `cache_misses_total` — `sync_cache.py:44/48`; sync_cache используется (`main.py:143`, `analytics.py:9`).

Мёртвые: F14 (auth ×2, telematics ×1).

---

## 6. Образцы A–D: текущее состояние дерева

- **A (`shift_tasks.odometer_distance` присваивался без колонки):** колонка ТЕПЕРЬ есть (`shift.py`, незакоммичено), `apply_shift_readings` пишет `task.odometer_distance`. Прямых фантомных присваиваний `obj.attr=` не найдено (0). Закрыто на уровне модели; данные 0/5, т.к. поток не использован.
- **B (`getattr(task,"odometer_distance",None)`):** атрибут теперь существует → больше не фантом. НО найден тот же класс на других атрибутах (F3/F4/F6/F10/F11/F12/F15–F19).
- **C (`moto_hours_start/odometer_start` все NULL):** колонки есть, 0/5 NULL — ни один использованный маршрут их не заполнил (данные созданы до нового потока).
- **D (`submit_shift_report` не обновлял наработку):** `driver.py:150` маршрут теперь вызывает `apply_shift_readings` → обновляет `vehicle.odometer_km/engine_hours`. Legacy `reports.py:267` — НЕ обновляет (F5, требует подтверждения).

---

## 7. Проверка 6: селекторы правил — мёртвых НЕТ (проверено фактом)

Запрос `/api/v1/query` по каждому селектору (серии):
```
up{job="spectech-backend"}=1  spectech_maintenance_due_without_order=1
pg_up=1  pg_stat_activity_count=37  pg_settings_max_connections=1  pg_stat_database_deadlocks=6
redis_up=1  redis_memory_used_bytes=1  redis_memory_max_bytes=1
node_filesystem_*{mountpoint="/mnt/docker-desktop-disk"}=1  node_filesystem_*{mountpoint="/mnt/host/c"}=1
container_start_time_seconds{id=~"/docker/.*"}=110  up=6  backup_last_success_timestamp_seconds=1
http_requests_total=0  http_request_duration_seconds_bucket=0  scheduler_job_failures_total=0  scheduler_job_missed_total=0
```
- `http_*` = 0 в покое — **не мёртвые**: проверено фактом, read-only `GET /docs` (200) → `http_requests_total=1` (handler=/docs, status=2xx), `http_request_duration_seconds_bucket=4`. Instrumentator работает; HighErrorRate/HighLatency event-driven.
- `scheduler_job_*` = 0 — event-driven Counter, нет провалов/пропусков → не дефект.
- `ContainerRestarting` селектор матчит 110 серий (жив); эффективность ограничена замороженным `container_start_time_seconds` на Docker Desktop — задокументировано в комментарии правила, не новая находка.
- DiskSpaceLow/HostDiskSpaceLow/backup-правила матчат (исправлены ранее).

**Вывод по проверке 6:** среди 20 правил нет селекторов, которые не матчат ничего по причине ошибки. Все 0-серийные случаи объяснены (event-driven) и подтверждены.

---

## 8. Что проверено и проблем НЕ найдено (охват)

1. Прямые фантомные присваивания `obj.attr=` (global-phantom, атрибут отсутствует во ВСЕХ моделях): **0**.
2. Синтаксически неиспользуемые параметры endpoint (Form/Body/Query/File/Path): **0**.
3. Мёртвые селекторы alert-правил: **0** (http_* подтверждены живыми запросом).
4. Метрики cache/vehicles/requests/alerts/db_connections/maintenance/scheduler — живые.
5. `map.py:196 plate_number` через `psm_number` — корректно (в отличие от diadoc.py:477).
6. `driver.py:93-97 planned_start/end` читает из `RequestAssignment` (`asg`) — корректно (в отличие от diadoc.py, читающего с ShiftTask).
7. `apply_shift_readings` корректно пишет `task.odometer_start/moto_hours_start/odometer_distance`, `report.odometer_end/moto_hours_end`, `vehicle.odometer_km/engine_hours` (атрибуты существуют) — сам сервис не фантомный; проблема в том, что его не вызывает legacy-маршрут (F5) и не использован на данных.

---

## 9. Сводка приоритетов

1. **F1/F2** — падают генерация актов и импорт банковских выписок (TypeError конструктора) + нулевые часы актов. Деньги/документы.
2. **F3/F4/F6** — документы заказчику без госномера, SMS водителям не работает, Excel выплат без владельца.
3. **F5/F13** — наработка машины не обновляется (legacy-маршрут + GPS без моточасов) → регламент ТО на сидовых числах. Требует подтверждения.
4. **F7/F9/F10** — планирование смен теряет плановые время/утвердившего/оператора; создание из шаблона падает.
5. **F11/F12/F8** — guard выработки инертен, акт ТО без владельца, геозоны латентно.
6. **F14–F19** — мёртвые метрики и косметические пустые поля интерфейсов.

Все находки — только отчёт. Решение об исправлении/удалении принимает пользователь; ничего не правилось.
