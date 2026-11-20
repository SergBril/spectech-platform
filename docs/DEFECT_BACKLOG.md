# DEFECT_BACKLOG — сводный приоритизированный список дефектов по шести аудитам

Дата: 2026-11-20. Режим: только расследование и один документ; правки кода/конфигов/тестов запрещены; запись в рабочую БД и внешняя отправка не выполнялись. Файлы пользователя (`PlatformOverviewPage`, `shifts/templates.py` и др.) не тронуты. Коммит — только этот документ через pathspec с проверкой состава до push.

**Источники (6 отчётов):** `PHANTOM_READS_AUDIT` (4f18c1d), `FRONTEND_RENAME_PLAN` (4cd44d1), `NOTIFICATION_DELIVERY_AUDIT` (e146f1e), `EMAIL_FAILURE_ROOT_CAUSE` (e76fbee), `MODEL_KWARGS_AUDIT` (8e8d972), `RESPONSE_CONTRACT_AUDIT` (8d3757a). Смежные: SILENT_NOOP (ecd7252), SCHEDULER_JOB (fad833c), API_CONTRACT (e12a77c), UNPUBLISHED_HANDLERS (e3114e6), PUBLICATION_READINESS (d04cf17), AUTOMATCH_RISK (d40db07).

**Как проверены статусы (не по памяти отчётов):** текущее дерево + `git log`/`git show --stat` + наличие закрепляющего теста. HEAD = `1ca407a` («marketplace response had no author»), дерево чистое. Важно: коммит `1ca407a` уже включил прежние «незакоммиченные» правки пользователя (public_service / salary_notification_dispatcher / email_service / request_service / dispatch + миграция `d9e3f4a5b6c7` + тесты test_payslip_delivery / test_response_chain / test_email_attachment_headers) — они FIXED, а не «в работе».

**Легенда статусов:**
- **FIXED** — починено; указан хеш коммита И закрепляющий тест (или честная оговорка, если теста нет).
- **OPEN** — дефект на месте в текущем дереве, чинится кодом. Приоритет: **P1** ложные данные под видом факта → **P2** падающие обработчики → **P3** тихие потери значений → **P4** пустые поля интерфейса.
- **DECISION** — нужно решение оператора (конфиг/продуктовая семантика); вопрос одним предложением + варианты.
- **OBSERVATION** — не дефект (мёртвый код, недоделка без регресса, покрыто иным механизмом).

Префиксы ID: RC=RESPONSE_CONTRACT, PR=PHANTOM_READS, MK=MODEL_KWARGS, ND=NOTIFICATION_DELIVERY, EF=EMAIL_FAILURE, FR=FRONTEND_RENAME. Дубли между отчётами — §5.

---

## 1. OPEN — приоритизировано

### P1. Ложные данные под видом факта

| ID | Суть | Файл:строка | Последствие для пользователя | Доказательство |
|---|---|---|---|---|
| **RC-1** | `revenue_trend` не возвращается, замаскирован hardcoded-массивом | `frontend/src/pages/PlatformOverviewPage.tsx:97`; `backend/app/services/shift_stats_service.py:1232` (`get_platform_overview` без `revenue_trend`) | `(data.revenue_trend \|\| [65,45,80,55,90,70,85])` → **выдуманный тренд выручки показан как факт** | grep `shift_stats_service` — `revenue_trend` отсутствует; fallback-массив в TSX. Прим.: пользователь правит обзор платформы — на момент проверки OPEN |
| **RC-2** | `counterparty` захардкожен пустой строкой | `backend/app/api/routes/shifts/bank.py:216` (`get_receivables_dashboard`); `frontend/src/pages/ReceivablesPage.tsx:107` | Дебиторка **всегда без контрагента** (`a.counterparty \|\| '—'` → всегда '—') | bank.py:216 `"counterparty": ""`. Дубль: AUTOMATCH_RISK + RESPONSE_CONTRACT |

### P2. Падающие обработчики

| ID | Суть | Файл:строка | Последствие для пользователя | Доказательство |
|---|---|---|---|---|
| **MK-1** | Импорт выписки: битый импорт модели + неверные kwargs + NOT NULL | `backend/app/services/bank_integration_service.py:88` (`from app.models.bank import BankTransaction` — модуля нет), `:107` (`doc_number/doc_date/payer_*/payee_*/status`), роут `bank.py:25` `import_bank_payments` → `:59 sync_payments_to_db` | Импорт выписки 1C/CSV → **500, транзакции не создаются** | glob `models/bank*.py` = только `bank_statement.py`; класс `BankTransaction` (`bank_statement.py:119`) имеет `document_number/counterparty_name/match_status/direction`, NOT NULL `statement_id/bank_transaction_id/document_type/document_date/processed_date/counterparty_name`; `app.models.bank` не существует → ModuleNotFoundError ещё до конструктора. Дубль: SILENT_NOOP + MODEL_KWARGS + PUBLICATION_READINESS |
| **MK-2** | `ShiftTask(planned_start=…, planned_end=…)` — нет таких колонок | `backend/app/api/routes/shifts/templates.py:193`; модель `backend/app/models/shift.py:46` | Генерация смен из шаблона → **TypeError, смены не создаются** | `shift.py` grep: есть `start_time/end_time` (time, :179-180) и `created_by` (:182), НЕТ `planned_start/planned_end`. `created_by` теперь валиден, `planned_start/planned_end` — нет. Прим.: пользователь правит шаблоны смен — на момент проверки OPEN. Дубль: MODEL_KWARGS + PHANTOM_READS |
| **PR-1** | `emp.first_name`/`emp.last_name` — у Employee нет этих полей | `backend/app/api/routes/shifts/tasks.py:163,553`; `shifts/diadoc.py:485`; `backend/app/services/shift_task_service.py:258` | Список смен / календарь / акты / авто-назначение водителя → **AttributeError → 500** (при наличии Employee) | `emp = db.get(Employee, …)`; `Employee` (`contractor.py:80`, таблица employees) имеет `position/role_in_system/user_id/salary_*`, имя — через `contractor.name`; `first_name/last_name` отсутствуют. Дубль: PHANTOM_READS |
| **PR-2** | `Rental.vehicle_id` — у Rental нет vehicle_id | `backend/app/services/marketplace_service.py:272` (календарь доступности) | Календарь доступности техники маркетплейса → **AttributeError → 500** | `Rental` (`rental.py:51`) без `vehicle_id`; `vehicle_id` только у `RentalItem` (`rental.py:172`). Дубль: PHANTOM_READS |
| **RC-8** | Кнопка «Выгрузка 1С» зовёт несуществующий путь | `frontend/src/pages/UtilizationPage.tsx:36` (`/api/v1/shifts/export/1c-acts`) vs реальный `/shifts/acts/export/1c` | Кнопка → **404, ничего не выгружает** | UtilizationPage:36 путь не изменён коммитом 4eadffc (он тронул 8 других файлов). Дубль: FRONTEND_RENAME + RESPONSE_CONTRACT |

### P3. Тихие потери значений

| ID | Суть | Файл:строка | Последствие для пользователя | Доказательство |
|---|---|---|---|---|
| **MK-3** | `task.actual_start`/`task.actual_end` — немаппленные присваивания | `backend/app/api/routes/shifts/geofence.py:70,109` | Фактические начало/конец смены по геозоне **молча не сохраняются** | `ShiftTask` (`shift.py:46`) без `actual_start/actual_end` → присваивание атрибута теряется (не колонка). Дубль: MODEL_KWARGS + SILENT_NOOP |
| **PR-3** | Мёртвый литерал статуса `Vehicle.status == "available"` | `backend/app/api/routes/shifts/max_messenger.py:132,181` | Выборка свободной техники для MAX-бота **всегда пуста** (в БД статус 'free') | Литерал 'available' не совпадает со значением enum 'free'. Латентно: канал MAX глобально выключен (D-2). Дубль: PHANTOM_READS (Class 2) |

### P4. Пустые поля интерфейса

| ID | Суть | Файл:строка | Последствие для пользователя | Доказательство |
|---|---|---|---|---|
| **RC-3** | `signature` не возвращается реестром актов | `backend/app/api/routes/shifts/diadoc.py:301-320` (items без `signature`); `frontend/src/pages/ActsPage.tsx:163` | У подписанных актов **не показывается KEP-бейдж ✍️** (`a.status==='signed' && a.signature` → undefined) | registry items: id/act_number/act_date/vehicle_name/driver_name/hours_worked/total_amount/vat_amount/status/edo_message_id — signature нет |
| **RC-4** | `gps_health` не возвращается | `frontend/src/pages/PlatformOverviewPage.tsx:116-124`; `shift_stats_service.py:1232` (без `gps_health`) | Блок «Здоровье GPS» = **'—' / 0** | grep `shift_stats_service` — `gps_health` отсутствует; optional chaining в TSX |
| **RC-5** | `summary: {}` при отсутствии записей | `backend/app/services/shift_stats_service.py:1144` (`get_fuel_dashboard` early-return); `frontend/src/pages/FuelDashboardPage.tsx:42-66` | При пустых данных карточки **undefined/NaN** вместо явных 0/«нет данных» | shift_stats_service:1144 `"summary": {}` |
| **RC-6** | `vehicle_id` не возвращается реестром (fallback) | `shifts/diadoc.py:301-320` (есть `vehicle_name`, нет `vehicle_id`); `ActsPage.tsx:147` | При пустом `vehicle_name` fallback `a.vehicle_id` → undefined → **пусто** (minor) | registry items без vehicle_id |
| **RC-7** | Форма ответа verify-signature расходится с типом фронта | `frontend/src/api/finance.ts:538` (`{valid,xml_size,sig_size}`) vs `shifts/diadoc.py:421-423` (`{valid,provider,signed_at}`) | `xml_size/sig_size` undefined. **Латентно:** `verifyUpdSignature` не вызывается ни одной страницей | diadoc.py:421-423 return; grep tsx — нет UI-потребителя. Дубль: FRONTEND_RENAME + RESPONSE_CONTRACT (путь починен 4eadffc, форма — нет) |
| **PR-4** | `user.first_name` — у User только full_name | `backend/app/services/telegram_bot.py:66,73` | Приветствие Telegram-бота → **AttributeError**. Латентно: Telegram выключен (D-2) | `User` (`auth.py:36`) имеет `full_name` (:43), без `first_name`. Дубль: PHANTOM_READS |

---

## 2. FIXED — подтверждено коммитом и тестом

| ID | Суть | Коммит | Закрепляющий тест | Дубли между отчётами |
|---|---|---|---|---|
| **RC-9 / PR / MK** | PnL/utilization/cost-forecast: часы всегда 0 (фантом `planned_start`) | `ed3b51f` | `tests/integration/test_pnl_hours.py` | PHANTOM_READS + MODEL_KWARGS + RESPONSE_CONTRACT (один корень, разные формулировки — §5) |
| **PR / ND** | Alert-email диспетчерам: фильтр `User.is_active` (поля нет) | `49a6cde` | `tests/integration/test_alert_email_dispatch.py` | SCHEDULER_JOB + NOTIFICATION_DELIVERY |
| **MK / PR** | `monthly_auto_acts` падал до создания актов + выдуманные цены (`act_number`/`planned_start`) | `ac4f54b` | `tests/integration/test_monthly_auto_acts.py` | SCHEDULER_JOB + MODEL_KWARGS |
| **PR** | Реестр банковских транзакций: фантомные `status/payer_*` (страница не работала) | `f2a2a15` | `tests/integration/test_bank_transactions_page.py` | PHANTOM_READS + SILENT_NOOP + API_CONTRACT. Теперь `bank.py:296-318` читает `t.counterparty_name/match_status`. **Не путать с MK-1** (это `list_bank_transactions`, а не `sync_payments_to_db`) |
| **FR** | 10 frontend-вызовов на несуществующие маршруты (pnl-per-vehicle, cost-rates, alerts/check-idle, drivers/shifts, bulk-responses, bulk-role, driver) | `4eadffc` | **unit-теста нет** (frontend-переименование, 8 файлов); проверка — `npm run typecheck`/build | API_CONTRACT + FRONTEND_RENAME. Исключение: 1c-acts не тронут → RC-8 OPEN |
| **ND** | Role-change email: `ImportError` (модульной `send_email` нет) | `1ca407a` | прямого теста role-change email не выделено; смежное покрытие `test_response_chain.py`/`test_email_attachment_headers.py` | NOTIFICATION_DELIVERY. Теперь `admin.py:138-156` зовёт `email_service.send_email(to_email,subject,body)`; `body` валиден (`email_service.py:88`); `role_change` есть в `DEFAULT_TEMPLATES:13`. Битый `rbac_email_service` больше не вызывается → O-1 |
| **MK / ND** | Salary dispatcher: `create_notification` без await + `send_email(to=)` вместо `to_email=` | `1ca407a` | `tests/integration/test_payslip_delivery.py` | NOTIFICATION_DELIVERY + MODEL_KWARGS. Теперь `salary_notification_dispatcher.py:94 await create_notification` + `:113 send_email(to_email=…)` |
| **EF / ND** | Email 550 «invalid headers»: кириллический filename encoded-word + пустой PDF ломал MIME | `1ca407a` | `tests/unit/test_email_attachment_headers.py` | EMAIL_FAILURE + NOTIFICATION_DELIVERY. Теперь `email_service.py:71-77` RFC2231 `filename=("utf-8","",filename)` + `:55` guard `len<100` для ВСЕХ PDF (не только payout) |
| **MK / ND** | Подмена ID: `RequestAssignment(operator_id=current_user.id)` вместо FK employees.contractor_id; у отклика не было автора | `1ca407a` | `tests/integration/test_response_chain.py` | MODEL_KWARGS + NOTIFICATION_DELIVERY. Теперь `public_service.py:772 operator_id=resp_vehicle.assigned_driver_id` + `created_by_user_id=current_user.id` |
| **MK** | `assigned_by` — немаппленное присваивание/чтение в RequestAssignment | `1ca407a` (+ миграция `d9e3f4a5b6c7_assignment_created_by`) | `tests/integration/test_response_chain.py` | MODEL_KWARGS + SILENT_NOOP. Теперь `created_by_user_id`/`assigned_by_user_id` (`models/dispatch.py:172` комментарий фиксирует замену) |
| **ND** | Не опубликованы ProfilePage / NotificationTemplates (+ дрейф модели) | `9345b07` | `tests/integration/test_profile_and_templates_pages.py` | API_CONTRACT + UNPUBLISHED_HANDLERS + PUBLICATION_READINESS |
| **ND** | Не опубликованы DocumentArchive / AutoAssignRules / FinanceDashboard | `5d60c24` | `tests/integration/test_archive_rules_finance_pages.py` | API_CONTRACT + UNPUBLISHED_HANDLERS + PUBLICATION_READINESS |
| **PR / FR** | Календарь смен сломан на 4 слоях | `5d5840e` | `tests/integration/test_shift_calendar_page.py` | API_CONTRACT + FRONTEND_RENAME. Чтение `planned_start` теперь через `getattr(t,"planned_start",None)` (`tasks.py:165`) — guarded (O-7); запись в конструктор всё ещё OPEN (MK-2) |
| **PR / RC** | Top-equipment chart: выдуманные нули вместо моточасов (фантом `Rental.moto_hours/vehicle_id`) | `ae25c22` | `tests/integration/test_revenue_by_vehicle.py` | PHANTOM_READS + RESPONSE_CONTRACT. `finance.py:678` переведён на `ShiftDataReconciliation`; `finance_reports.py:254 r.moto_hours` теперь агрегат (O-6). **marketplace `Rental.vehicle_id` не тронут → PR-2 OPEN** |
| **MK** | Показания счётчиков смен не доходили до БД и счётчиков техники | `759cecb` | `test_shift_meter_readings.py` + `test_driver_readings_api.py` | SILENT_NOOP |
| **MK** | Массовая генерация актов дублировала pricing и ничего не создавала | `2939f39` | `test_monthly_auto_acts.py` (доп. кейсы) | SILENT_NOOP |
| **MK** | Пустой отчёт о смене отвергался после lookup, а не на границе | `82dee56` | **отдельного теста нет** (1 файл `driver.py`) | SILENT_NOOP |
| **MK** | Расчёт ТО читал дневную выработку как пожизненный счётчик | `6aaa14c` | `test_maintenance_due_service.py` | SILENT_NOOP |

---

## 3. DECISION — вопрос оператору + варианты

| ID | Вопрос оператору (одним предложением) | Варианты ответа | Доказательство/контекст |
|---|---|---|---|
| **D-1** | Подтверждён ли app-password mail.ru для SMTP (пароль приложения, а не основной пароль ящика)? | (а) задать app-password в `.env.prod` `SMTP_PASSWORD` и пересоздать контейнер (`up -d`, не `restart`); (б) сменить SMTP-провайдера; (в) оставить email выключенным | EMAIL_FAILURE: 535 = требуется app-password (исторически разрешён — подтвердить текущий статус); 550 MIME починен (EF FIXED). Рабочая БД не проверялась на запись |
| **D-2** | Включать ли каналы MAX/FCM/Telegram и заполнить получателей (сейчас max_chat_id 0/12, telegram_id 0/12, device_tokens 0)? | (а) включить MAX + заполнить max_chat_id; (б) включить FCM + зарегистрировать устройства; (в) включить Telegram + привязать telegram_id; (г) оставить только email/in_app | NOTIFICATION_DELIVERY: каналы глобально мертвы (нет получателей + флаги выключены); FCM-stub возвращает True. Маскирует PR-3/PR-4 |
| **D-3** | Засеять ли `notification_templates` в рабочей БД для кодов вне 4 DEFAULT_TEMPLATES (role_change/overdue_acts/act_signed/act_rejected)? | (а) `init_default_templates` + добавить недостающие коды; (б) расширить `DEFAULT_TEMPLATES`; (в) оставить fallback только для 4 кодов | NOTIFICATION_DELIVERY: таблица 0 строк; `notification_template_service.py:12` DEFAULT_TEMPLATES = 4 кода; прочие коды → `render_template` None → уведомления нет |
| **D-4** | Кто получатель еженедельного дайджеста — фильтр ищет accountant/admin/manager/owner, а в рабочей БД роли driver/operator? | (а) назначить роли accountant/manager сотрудникам; (б) изменить аудиторию фильтра; (в) отключить дайджест | NOTIFICATION_DELIVERY: `weekly_digest_service.py:362` `role_in_system.in_(["accountant","admin","manager","owner"])`; при отсутствии таких ролей дайджест уходит никому |
| **D-5** | Зависшие выплаты (>3 дней) сейчас только логируются — слать ли уведомление ответственным? | (а) wired email/in_app; (б) метрика + панель Grafana; (в) оставить лог | NOTIFICATION_DELIVERY: `scheduler.py:724 _check_pending_payouts` только `logger.warning`. Maintenance_due уже питает метрику/панель → O-3 |
| **D-6** | Задеплоить ли Celery-воркер — `.delay()` без воркера не исполняется (латентно)? | (а) поднять воркер; (б) перевести задачи на APScheduler; (в) удалить мёртвые `.delay` | Смежно (Celery-worker-not-deployed): очередь без исполнителя; не аварийный баг, а латентная недоделка |
| **D-7** | Публиковать ли репозиторий и в какой видимости (пример из постановки задачи, не из 6 отчётов)? | (а) private; (б) public; (в) внутренний mirror | Решение оператора по видимости/remote; на код не влияет |

---

## 4. OBSERVATION — не дефекты

| ID | Суть | Файл:строка | Почему не дефект |
|---|---|---|---|
| **O-1** | `rbac_email_service.send_role_change_email` с битым `from app.services.email_service import send_email` | `backend/app/services/rbac_email_service.py:10,33` | **Не вызывается** (grep: только определение; `admin.py` использует `email_service.send_email` напрямую). Мёртвый код; удаление — на решение пользователя |
| **O-2** | `driver_name` в реестре актов всегда "" | `shifts/diadoc.py:315` (`getattr(a,"driver_name",None)`; у Act нет driver_name) | Недоделанная колонка «Водитель», не регресс. Дубль: PHANTOM_READS + RESPONSE_CONTRACT §2 |
| **O-3** | `maintenance_due` только лог + метрика | `scheduler.py:681`, gauge `set_maintenance_due_without_order` (:921) | Покрыто метрикой/панелью Grafana (c7a570c), не email — иной механизм, не «тихая потеря» |
| **O-4** | Поля возвращаются, но не читаются фронтом | `get_driver_kpi` active_days/total_days; receivables overdue_acts[].status; platform-overview date; fuel-analytics drains | RESPONSE_CONTRACT §2: возвращаются корректно, просто не используются — не дефект |
| **O-5** | Калибровка `Request.status == 'new'` | PHANTOM_READS Class 2 | Подтверждено: литерал совпадает со значением enum, работает |
| **O-6** | `finance_reports.py:254 r.moto_hours` | `backend/app/services/finance/finance_reports.py:254` | После ae25c22 `r` — агрегат `ShiftDataReconciliation.final_moto_hours` (label), НЕ Rental → корректно, не фантом |
| **O-7** | Чтение `ShiftTask.planned_start` через getattr | `shifts/tasks.py:165` (`getattr(t,"planned_start",None) or …`) | Guarded fallback (5d5840e) — не падает. В отличие от ЗАПИСи в конструктор `templates.py:193` (MK-2 OPEN) |

---

## 5. Дубликаты и противоречия между отчётами

**Один дефект в нескольких отчётах (разные формулировки):**
- **Нулевые часы** — PHANTOM_READS (фантом `planned_start`), MODEL_KWARGS (конструктор/значение), RESPONSE_CONTRACT (§5 «дефект значения, не контракта»). Корень один → **FIXED ed3b51f**. Противоречия нет: RC отделял «поле есть, значение неверно» от «поля нет», PR/MK называли причину.
- **User.is_active** — SCHEDULER_JOB + NOTIFICATION_DELIVERY → FIXED 49a6cde.
- **Неопубликованные обработчики** — API_CONTRACT + UNPUBLISHED_HANDLERS + PUBLICATION_READINESS → FIXED 9345b07 / 5d60c24.
- **Переименования фронта** — API_CONTRACT + FRONTEND_RENAME → FIXED 4eadffc (кроме 1c-acts → RC-8 OPEN).
- **verify-signature** — FRONTEND_RENAME + RESPONSE_CONTRACT → RC-7 OPEN: путь починен (4eadffc), форма ответа `{valid,provider,signed_at}` vs тип `{valid,xml_size,sig_size}` всё ещё расходится.
- **counterparty** — AUTOMATCH_RISK + RESPONSE_CONTRACT → RC-2 OPEN.
- **Подмена ID / автор отклика** — MODEL_KWARGS + NOTIFICATION_DELIVERY → FIXED 1ca407a.
- **salary await / to=** — NOTIFICATION_DELIVERY + MODEL_KWARGS → FIXED 1ca407a.
- **email MIME 550** — EMAIL_FAILURE + NOTIFICATION_DELIVERY → FIXED 1ca407a.
- **bank-дефекты** — SILENT_NOOP + MODEL_KWARGS + PUBLICATION_READINESS + PHANTOM_READS + API_CONTRACT. **Внимание: это ДВА разных дефекта в одном модуле bank, не дубль:** `list_bank_transactions` (фантомные поля ответа) → FIXED f2a2a15; `sync_payments_to_db` (битый импорт + kwargs) → MK-1 OPEN. Не объединять.

**Уточнения/противоречия по факту:**
- MODEL_KWARGS указывал `BankTransaction` в `finance.py` — фактически класс в `bank_statement.py:119` (уточнение расположения; суть дефекта MK-1 подтверждена: колонки `doc_number/payer_*` отсутствуют).
- PHANTOM_READS «фантомы Rental/Employee»: `Rental.moto_hours/vehicle_id` в finance top-equipment → FIXED ae25c22, но `Rental.vehicle_id` в marketplace → PR-2 OPEN; `Employee.first_name` → PR-1 OPEN. Один класс фантомов, разные файлы/статусы — не считать всё починенным.
- RESPONSE_CONTRACT §5 «PnL hours=0 — дефект значения, не контракта» vs PR/MK «фантом planned_start» — разные формулировки одного корня (FIXED ed3b51f), не противоречие.

**Требует подтверждения (не выдавать за факт):**
- RC-1/RC-4: пользователь прямо сейчас правит обзор платформы — возможен фикс `revenue_trend/gps_health` в незакоммиченном виде; на момент проверки (дерево чистое, HEAD 1ca407a) поля в `get_platform_overview` отсутствуют → OPEN.
- MK-2: пользователь правит шаблоны смен — возможен фикс `planned_start/planned_end`; на момент проверки конструктор всё ещё с неверными kwargs → OPEN.
- D-1: текущий статус app-password mail.ru в рабочей БД/`.env.prod` не проверялся (запрет записи/чтения секретов); 535 исторически разрешён — подтвердить.
- D-4: наличие ролей accountant/admin/manager/owner в рабочей БД не пересчитывалось в этой задаче; фильтр кода подтверждён.

---

## 6. Сводка

- **OPEN: 15** — P1: 2 (RC-1, RC-2); P2: 5 (MK-1, MK-2, PR-1, PR-2, RC-8); P3: 2 (MK-3, PR-3); P4: 6 (RC-3, RC-4, RC-5, RC-6, RC-7, PR-4).
- **FIXED: 18** находок (§2), все с хешем коммита; у 15 есть закрепляющий тест, у 3 честная оговорка (FR 4eadffc — typecheck/build, unit-теста нет; MK 82dee56 — отдельного теста нет; ND role-change 1ca407a — прямого теста нет, смежное покрытие).
- **DECISION: 7** (D-1…D-7).
- **OBSERVATION: 7** (O-1…O-7).

Первоочередное для оператора: **P1** (выдуманный тренд выручки RC-1, hardcoded counterparty RC-2) → **P2** (импорт выписки MK-1, генерация смен MK-2, падающие driver_name PR-1 / календарь маркетплейса PR-2 / кнопка 1С RC-8). Решения D-1/D-2/D-3 разблокируют каналы уведомлений. Ничего не правилось; исправление и коммиты кода — за пользователем.
