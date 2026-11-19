# SCHEDULER_JOB_AUDIT — эмпирическая проверка задач планировщика + коррекция F1/F2

Дата: 2026-11-19. Режим: рабочая БД **только чтение**; задачи прогонялись на **одноразовой копии** (восстановление последнего бэкапа). Правки кода/конфигов/миграций/тестов запрещены и не выполнялись. Внешняя отправка отключена и доказана значениями настроек + сетевым guard.

---

## ЧАСТЬ 1. Противоречие F1/F2 прежнего отчёта: откуда 19 актов и 48 транзакций

**Вердикт: находки F1/F2 были ЧАСТИЧНО НЕВЕРНЫ (последствие преувеличено).** Падающие пути реальны, но они **вторичные/legacy**; первичные пути создания работают и именно они создали данные.

### Акты (19 строк) — созданы валидными путями, не падающими
Факт из БД (read-only):
- id 1–2: `АКТ-001/АКТ-002`, created_by NULL, comment «Работы выполнены»/«Ожидает подписи», суммы 48000/75480, status paid/sent → **сид** `backend/app/cli/seed_rbac.py:499-521` (`Act(**act_data)` с валидными kwargs: document_number, request_id, client_id, total_amount, act_date, status, comment). Совпадает с БД дословно.
- id 3–20: `ACT-2026-0001…0017`, created_by=1, request_id 7/8, total_amount ненулевые (40000–122000), `shift_task_id/vehicle_id/hours_worked` NULL, comment пуст → **`request_service.py:1053` (complete_request)**: `Act(document_number=generate_document_number(db,"ACT"), request_id, client_id, company_id, total_amount, vat_amount, vat_rate, tax_system, is_vat_included, act_date, status, comment)` — **все kwargs валидны**. Формат `generate_document_number` (`finance_service.py:28`) = `ACT-{year}-{seq:04d}` — точно совпадает. Пустой comment означает, что строки созданы более ранней версией кода (до добавления комментария), но путь валидный.

### Банковские транзакции (48) — созданы валидным путём
Факт: все 48 с `statement_id=6`, единый `created_at=2026-10-07 17:48:22` (один bulk-импорт), `source=manual`, counterparty_inn заполнены. Выписка id=6: `file_name=tmpz3yiw2pz.txt`, `status=parsed`, `total_transactions=48`, `uploaded_by=1`.
Источник — **`payments_service.py:117` (upload_statement)**: `BankTransaction(statement_id, company_id, bank_transaction_id, document_type, document_number, document_date, direction, amount, processed_date, counterparty_name, counterparty_inn, counterparty_kpp, counterparty_account, counterparty_bank, counterparty_bik, purpose, is_excluded, exclusion_reason, match_status)` — **все kwargs валидны** (совпадают с mapper).

### Падающие пути подтверждены (но не источник этих данных)
- `shifts/diadoc.py:596` — генерация актов по сменам: `Act(driver_name=, distance_km=)` → TypeError (доказано в памяти ранее); плюс `hours` всегда 0 (`planned_start/end` на ShiftTask фантомные). Маршрут не создавал эти 19 актов (у них shift_task_id NULL).
- `scheduler.py:389` — `monthly_auto_acts`: `Act(act_number=)` TypeError + `t.planned_start` AttributeError (см. Часть 2, доказано эмпирически).
- `bank_integration_service.py:107` — `sync_payments_to_db` (вызывается из `shifts/bank.py:59`, импорт 1C/CSV): 9 неверных kwargs → TypeError. Это **другой** маршрут импорта, не `upload_statement`; 48 транзакций созданы не им.

**Коррекция формулировок прежнего отчёта:** «акты не формируются» и «импорт выписок падает» — неверно как общее утверждение. Акты формируются через complete_request, выписки импортируются через upload_statement. Падают только shift-генерация актов, monthly_auto_acts и 1C/CSV-синхронизация. Эти пути остаются сломанными (латентно, пока не вызваны), но данные в БД созданы рабочими путями.

---

## ЧАСТЬ 2. Эмпирический прогон 15 задач планировщика на КОПИИ

### Метод
1. Копия: одноразовый `timescale/timescaledb:2.30.1-pg16` (`spectech-sched-copy`), сеть database (порт наружу не публиковался), отдельный том. Восстановлен свежий бэкап `spectech_20261119_100000.sql.gz` по доказанной процедуре (`timescaledb_pre_restore` → `pg_restore --no-owner --no-privileges --disable-triggers` → `post_restore`), **exit 0**. Counts копии совпали с рабочей: vehicles 16, acts 19, shift_tasks 5, bank_transactions 48, requests 29, maintenance_orders 5.
2. Harness перехватил `scheduler.add_job` (собраны 15 функций без реального планирования), `DATABASE_URL` указывал на копию. Код — текущий из дерева.
3. Каждая задача вызвана (`asyncio.run`), зафиксированы status/traceback/логи и before/after counts таблиц.

### Доказательство отключения внешней отправки (значения В ПРОЦЕССЕ запуска)
```
database_url = postgresql://spectech:***@spectech-sched-copy:5432/spectech
EMAIL_ENABLED = False        SMTP_HOST = ''
MAX_ENABLED = False          MAX_BOT_TOKEN = <empty>
TELEGRAM_ENABLED = False     TELEGRAM_BOT_TOKEN = <empty>
FCM_CREDENTIALS_PATH = <missing>   GREENSMS_API_TOKEN → sms_service.enabled=False
DIADOC_API_KEY = <empty>     DIADOC_BOX_ID = ''   DIADOC_USE_SANDBOX = True
service.enabled: email=False max=False max_messenger=False fcm=False sms=False
SAFETY_OK: all external senders disabled, DB points to copy
```
Дополнительно — **сетевой guard**: блок публичного egress на уровне socket (private/loopback разрешён, т.е. копия БД доступна, внешние API — нет). Подтверждено фактом: gps_sync получил `Mapix auth exception: All connection attempts failed` (внешний API заблокирован). Diadoc стабится (нет ключей), email/MAX/FCM/SMS/Telegram выключены флагами. Реальные люди/внешние системы не затронуты.

### Сводная таблица (ранг по последствию)

| # | Задача | Итог | Эффект на копии | Последствие |
|---|---|---|---|---|
| 1 | **monthly_auto_acts** | **УПАЛА** (на 1-е числа) | AttributeError `planned_start` | деньги/документы: авто-акты по сменам не создаются |
| 2 | **daily_alert_check** | прошла, **email-алерты сломаны** | `User.is_active` AttributeError (ловится) | уведомления: email-алерты не шлются никогда |
| 3 | **daily_auto_match_payments** | прошла, **0 matches** | 47 unmatched TX не разнесены | деньги: авторазноска не срабатывает (требует подтверждения) |
| 4 | weekly_digest | прошла, **0 recipients** | «No accountants found» ×4 | уведомления: дайджест некому слать (требует подтверждения) |
| 5 | act_status_check | прошла, без эффекта | нет ключей Diadoc → stub | ЭДО: статусы не обновляются (ожидаемо без ключей) |
| 6 | gps_sync | прошла, external blocked | Mapix auth failed (guard) | телематика: в тест-среде API недоступен (не баг кода) |
| 7 | daily_overdue_receivables | прошла, работала | 13 просроч. актов 808100 ₽, FCM stub | функциональна |
| 8 | daily_maintenance_due_check | прошла, работала | 1 машина требует наряда (CAT 320D 760h≥750h) | функциональна |
| 9 | daily_pending_payouts_check | прошла, работала | 5 pending payouts >3 дней | функциональна |
| 10 | daily_overdue_invoices_check | прошла, работала | 22 просроч. счёта | функциональна |
| 11 | business_metrics_refresh | прошла, работала | гейджи обновлены | функциональна |
| 12 | daily_company_report | прошла, no-op | «0 shifts, 0 ₽» за 18.11 (смен вчера нет) | data-dependent no-op |
| 13 | daily_fuel_anomaly_check | прошла, no-op | аномалий нет (shift_fuel_entries пусты) | нет подходящих данных |
| 14 | auto_escalate_disputes | прошла, no-op | disputes пусты | нет подходящих данных |
| 15 | daily_session_cleanup | прошла, no-op | истёкших сессий нет | нет подходящих данных |

### Падение №1 — monthly_auto_acts (ПОЛНЫЙ TRACEBACK, доказано эмпирически)
Условие: задача имеет guard `if today.day != 1: return` (scheduler.py:347) — в обычный день мгновенный no-op. В копии есть completed-смена id=1 от 2026-10-02. Симулировал `today=2026-11-01` (прошлый месяц = октябрь) → задача нашла смену и упала:
```
❌ Auto acts generation failed: 'ShiftTask' object has no attribute 'planned_start'
Traceback (most recent call last):
  File "/usr/local/lib/python3.12/asyncio/runners.py", line 91, in run
    return self._loop.run_until_complete(task)
  File "/usr/local/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete
    return future.result()
  File "/app/app/tasks/scheduler.py", line 382, in _auto_generate_and_send_acts
    if t.planned_start and t.planned_end:
       ^^^^^^^^^^^^^^^
AttributeError: 'ShiftTask' object has no attribute 'planned_start'
```
Причина: `ShiftTask.planned_start/planned_end` не замаплены (есть только на `RequestAssignment`). Это первый баг; если его обойти, следом упадёт `Act(act_number=...)` (scheduler.py:389) — `act_number` не колонка Act (есть `document_number`), TypeError доказан ранее. Тесты задачи проходят, потому что гоняют её на пустой базе / не 1-е числа (guard или отсутствие completed-смен в прошлом месяце). **На реальных данных 1-го числа задача падает и откатывает транзакцию — авто-акты не создаются.**

### Скрытый отказ №2 — daily_alert_check: email-алерты не отправляются
Лог прогона:
```
ERROR:Failed to send alert email: type object 'User' has no attribute 'is_active'
```
Причина: `alert_service.py:98` — `User.is_active == True`. У модели `User` **нет** `is_active` (подтверждено SQL: `column "is_active" does not exist` в users; есть только `status: UserStatus`, default active; `is_active` есть лишь у `UserSession`, auth.py:131). Запрос построения падает AttributeError, ловится в `send_alert_email` → email-алерт молча не отправляется. FCM-уведомления при этом работают (stub). Последствие: email-канал алертов (простои/конфликты) мёртв. Правильное поле — `User.status == UserStatus.active`.

### «Прошла, но ничего не сделала» при подходящих данных (требует подтверждения)
- **daily_auto_match_payments**: 47 unmatched-транзакций есть, но `total_matched=0`. Сервис `BankMatchingService.match_transaction` матчит TX → **Invoice/Payout** (по document_number, amount+ИНН через Contractor.inn, либо amount-only), НЕ по актам. 0 matches может быть легитимным (нет счетов/выплат с совпадающими суммами/ИНН) либо следствием пробелов данных. Требует подтверждения: есть ли в копии invoices/payouts с совпадающими amount/ИНН. Замечание: колонка `bank_transactions.matched_act_id` (0/48) сервисом не используется (пишется `matched_invoice_id`/`matched_payout_id`) — это мёртвое поле, отдельный класс.
- **weekly_digest**: 4 компании обработаны, но «No accountants found» у каждой → 0 recipients. Требует подтверждения: есть ли пользователи с ролью бухгалтера (данных нет vs неверный запрос роли).
- **monthly_auto_acts** в день ≠1: no-op по guard (by design), но это маскирует падение 1-го числа.

### Легитимные no-op (нет подходящих данных — не баг)
auto_escalate_disputes (disputes пусты), daily_fuel_anomaly_check (shift_fuel_entries пусты), daily_session_cleanup (нет истёкших сессий), daily_company_report (смен за вчера нет).

### Функциональные задачи (отработали по данным)
daily_overdue_receivables (13 актов/808100 ₽), daily_maintenance_due_check (1 машина), daily_pending_payouts_check (5 выплат), daily_overdue_invoices_check (22 счёта), business_metrics_refresh (гейджи). Уведомления ушли в stub (внешняя отправка отключена), логика выполнена.

---

## Cleanup
Одноразовый контейнер `spectech-sched-copy` и том `spectech-sched-copy-data` удалены после прогона; отсутствие подтверждено (`docker ps -a`/`docker volume ls` — пусто). Рабочая БД не изменялась (только SELECT). Внешних отправок не было (флаги + сетевой guard, доказано).

## Итог
- **F1/F2 прежнего отчёта частично неверны**: данные созданы валидными путями (complete_request, upload_statement, seed); падают вторичные пути (shift-генерация актов, monthly_auto_acts, 1C/CSV-синхронизация).
- **Эмпирически найдено**: monthly_auto_acts падает на реальных данных 1-го числа (AttributeError planned_start → затем TypeError act_number); daily_alert_check молча не шлёт email-алерты (User.is_active фантом); daily_auto_match_payments и weekly_digest «прошли, но 0 эффекта» — требует подтверждения данных.
- Все находки — отчёт; исправление решает пользователь.
