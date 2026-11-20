# DEFECT_BACKLOG — сводный приоритизированный список дефектов по шести аудитам

Дата: 2026-11-20 (обновление). Режим: расследование + один документ; в этой партии разрешены публикация `import_bank_payments` (shifts/bank.py) и обновление бэклога; auto_match — только расследование (семантика денег не менялась). Запись в рабочую БД и внешние отправки не выполнялись (чтение рабочей БД — SELECT). Запрещённые файлы (`shifts/diadoc.py`, `shifts/tasks.py`, `shifts/templates.py`, `shift_task_service.py`, `finance.py`) не редактировались агентом; правки пользователя в них учтены как FIXED (рабочее дерево).

**Источники (6 отчётов):** PHANTOM_READS (4f18c1d), FRONTEND_RENAME_PLAN (4cd44d1), NOTIFICATION_DELIVERY (e146f1e), EMAIL_FAILURE_ROOT_CAUSE (e76fbee), MODEL_KWARGS (8e8d972), RESPONSE_CONTRACT (8d3757a). Смежные: SILENT_NOOP (ecd7252), SCHEDULER_JOB (fad833c), API_CONTRACT (e12a77c), UNPUBLISHED_HANDLERS (e3114e6), PUBLICATION_READINESS (d04cf17), AUTOMATCH_RISK (d40db07).

**Как проверены статусы:** текущее дерево + `git log`/`git show --stat` + наличие закрепляющего теста; для данных — read-only SELECT к рабочей БД. HEAD = `1303aca` (публикация импорта), предыдущие фиксы: `92d5560`, `f3eec50`, `5bcb5bf`, `ac59018`, `1ca407a` и более ранние. Часть фиксов пользователя (PR-1, MK-2, RC-3/RC-6, templates-422) находится в **незакоммиченном рабочем дереве** — помечены FIXED (дерево) с оговоркой.

**Легенда:** **FIXED** — починено (хеш коммита И тест, либо честная оговорка). **OPEN** — дефект на месте, чинится кодом; приоритет P1 ложные данные → P2 падающие обработчики → P3 тихие потери → P4 пустые поля. **DECISION** — решение оператора (конфиг/продуктовая семантика, деньги). **OBSERVATION** — не дефект (мёртвый код, объект иной природы, покрыто иным механизмом).

Префиксы: RC=RESPONSE_CONTRACT, PR=PHANTOM_READS, MK=MODEL_KWARGS, ND=NOTIFICATION_DELIVERY, EF=EMAIL_FAILURE, FR=FRONTEND_RENAME, AM=AUTOMATCH, NEW=новые находки этой партии.

---

## 1. OPEN — приоритизировано

### P1–P3 — не осталось (все ложные данные / падающие / тихие потери из аудитов закрыты)

RC-1 (фейковый тренд), RC-2 (counterparty), MK-1 (импорт), MK-2 (шаблоны), PR-1 (driver_name), PR-2 (marketplace), RC-8 (1С), MK-3 (геозона), PR-3 (MAX-статус) → FIXED (§2). Тихие потери auto_match вынесены в DECISION (деньги, §3 AM-2/AM-3).

### P4. Пустые поля интерфейса / незаполненный источник

| ID | Суть | Файл:строка | Последствие для пользователя | Доказательство |
|---|---|---|---|---|
| **NEW-1 / ACTS-NULL** | У всех 19 актов рабочей БД `driver_id/hours_worked/vehicle_id/signature` = NULL | создание актов (`finance.py`/`act_service.py` — правит пользователь); реестр `shifts/diadoc.py:301-325` | Реестр показывает **пустые колонки техники, водителя, часов**; KEP-бейдж не появляется (поля возвращаются, но данных нет) | read-only SQL: `acts_total=19, driver_null=19, hours_null=19, vehicle_null=19, sig_null=19`. Реестр теперь возвращает vehicle_id/signature/signed_at (RC-3 FIXED), но значения NULL. Корень — генерация актов не заполняет поля; пользователь работает над созданием актов |
| **NEW-2 / GPS-SYNC** | Журнал `gps_sync_logs` никто не наполняет: активный sync обходит писателя | `backend/app/tasks/mapix_sync_task.py:177` (`adapter.get_all_positions_sync()`); писатель `gps_providers/base.py:156 log_gps_sync` вызывается только через `_logged_call` (:113/127) | Виджет «Здоровье GPS» (расчёт добавлен ac59018, `shift_stats_service.py:1366`) **всегда пуст/нули** — источник не наполняется | read-only SQL: `gps_sync_logs=0`; `vehicles with gps_provider=3`. `get_all_positions_sync` (wialon.py:117, mapix.py:328) НЕ вызывает log_gps_sync; `_logged_call` обёрнут вокруг async-методов, которые sync-задача не использует. Писатель существует, но активный путь его обходит |

---

## 2. FIXED — подтверждено коммитом и тестом

| ID | Суть | Коммит | Закрепляющий тест |
|---|---|---|---|
| **RC-1** | PlatformOverview: выдуманный тренд выручки `[65,45,80,…]` под видом факта | `ac59018` | `tests/integration/test_platform_overview_real_data.py`; теперь `shift_stats_service.py:1349` реальный `revenue_trend`, fallback фронта — `[]` (PlatformOverviewPage:98) |
| **RC-4 (поле)** | `gps_health` не возвращался обзором платформы | `ac59018` | `test_platform_overview_real_data.py`; `shift_stats_service.py:1366/1389` возвращает gps_health. **Данные пусты → NEW-2 (OPEN)** |
| **RC-2** | Дебиторка: `counterparty` захардкожен "" | `5bcb5bf` | `tests/integration/test_receivables_counterparty.py`; `bank.py` counterparty = `act.counterparty_name or Contractor.name` |
| **MK-1** | Импорт выписки: `app.models.bank` не существует + неверные kwargs | `5bcb5bf` | `tests/unit/test_bank_integration_service_coverage.py` (sync на реальной модели); `bank_integration_service.sync_payments_to_db` → `bank_statement`, реальная BankStatement, direction по счёту |
| **MK-1 (публикация)** | `import_bank_payments` без декоратора → 404 | `1303aca` | `tests/integration/test_bank_import_api.py` (CSV создаёт записи, 401 без auth, изоляция по компании); POST `/shifts/bank/import`, File+Form, доступ get_current_user/get_current_company_id по образцу upload_bank_statement. Вызова во фронтенде нет — путь по конвенции соседних ручек |
| **RC-5** | FuelDashboard `summary:{}` → undefined/NaN | `f3eec50` | `tests/integration/test_fuel_dashboard_summary.py`; нулевая форма той же структуры |
| **RC-8** | Кнопка «Выгрузка 1С» → 404 (`/shifts/export/1c-acts`) | `f3eec50` | `frontend/src/__tests__/UtilizationPage.export1c.test.tsx`; путь `/shifts/acts/export/1c` + период страницы |
| **RC-7** | verifyUpdSignature тип `{valid,xml_size,sig_size}` vs ответ `{valid,provider,signed_at}` | `f3eec50` | `frontend/src/__tests__/financeVerifySignature.test.ts`; тип приведён к ответу, поля размеров не добавлены |
| **MK-3** | Геозона писала `task.actual_start/end` (нет полей у ShiftTask) | `92d5560` | `tests/integration/test_geofence_actual_time.py`; время пишется в `RequestAssignment.actual_start/end` через `assignment_id`, guard для смены без назначения |
| **PR-2** | marketplace `Rental.vehicle_id` (фантом, техника в RentalItem) | `92d5560` | `tests/integration/test_marketplace_availability.py`; фильтр `Rental.items.any(RentalItem.vehicle_id==…)`, техника не теряется |
| **PR-3** | MAX-бот `Vehicle.status=="available"` (литерал не существует) | `92d5560` | `tests/integration/test_max_messenger_free_status.py` + `test_max_webhook_security.py` (данные фикстуры исправлены на "free"); канонический статус — "free" (catalog.py:107 default, telegram_bot.py:235) |
| **PR-1** | `emp.first_name/last_name` (у Employee нет полей) → AttributeError | **дерево пользователя (не закоммичено)** | `tests/integration/test_driver_name_resolution.py` (untracked); `tasks.py:163/570`, `diadoc.py:490`, `shift_task_service.py:258` → `emp.contractor.name if emp and emp.contractor else ""` |
| **MK-2** | `ShiftTask(planned_start/planned_end)` → TypeError | **дерево пользователя (не закоммичено)** | `tests/integration/test_templates_apply.py` (untracked); `templates.py:201-235` создаёт Request+RequestAssignment (planned_start валиден там), ShiftTask без planned_start |
| **NEW-3 / TEMPLATES-422** | Применение шаблонов: `week_start` Body без embed → 422 при объекте от страницы | **дерево пользователя (не закоммичено)** | `tests/integration/test_templates_apply.py`; `templates.py:128` `Body(..., embed=True)` |
| **RC-3 / RC-6** | Реестр актов не возвращал `signature`/`vehicle_id` (KEP-бейдж, fallback) | **дерево пользователя (не закоммичено)** | `shifts/diadoc.py:313/322/323` возвращает vehicle_id/signature/signed_at (null если нет, не вымысел). **Данные NULL → NEW-1 (OPEN)** |
| **RC-9 / PR / MK** | PnL/utilization/cost-forecast: часы всегда 0 | `ed3b51f` | `tests/integration/test_pnl_hours.py` |
| **PR / ND** | Alert-email: фильтр `User.is_active` (поля нет) | `49a6cde` | `tests/integration/test_alert_email_dispatch.py` |
| **MK / PR** | `monthly_auto_acts` падал + выдуманные цены | `ac4f54b` | `tests/integration/test_monthly_auto_acts.py` |
| **PR** | Реестр банк-транзакций: фантомные `status/payer_*` | `f2a2a15` | `tests/integration/test_bank_transactions_page.py` |
| **FR** | 10 frontend-вызовов на несуществующие маршруты | `4eadffc` | unit-теста нет (frontend); проверка typecheck/build. Исключение 1c-acts → закрыто RC-8 (f3eec50) |
| **ND** | Role-change email ImportError | `1ca407a` | прямого теста нет; смежное `test_response_chain.py`/`test_email_attachment_headers.py`; admin.py зовёт email_service.send_email(body валиден), role_change в DEFAULT_TEMPLATES |
| **MK / ND** | Salary dispatcher: create_notification без await + send_email(to=) | `1ca407a` | `tests/integration/test_payslip_delivery.py` |
| **EF / ND** | Email 550: кириллический filename + пустой PDF ломал MIME | `1ca407a` | `tests/unit/test_email_attachment_headers.py`; RFC2231 filename* + guard len<100 для всех PDF |
| **MK / ND** | Подмена ID: operator_id=User.id; у отклика не было автора | `1ca407a` | `tests/integration/test_response_chain.py`; operator_id=assigned_driver_id + created_by_user_id |
| **MK** | assigned_by — немаппленное присваивание | `1ca407a` (+ миграция d9e3f4a5b6c7) | `test_response_chain.py`; created_by_user_id/assigned_by_user_id |
| **ND** | Не опубликованы ProfilePage / NotificationTemplates | `9345b07` | `tests/integration/test_profile_and_templates_pages.py` |
| **ND** | Не опубликованы DocumentArchive / AutoAssignRules / FinanceDashboard | `5d60c24` | `tests/integration/test_archive_rules_finance_pages.py` |
| **PR / FR** | Календарь смен сломан на 4 слоях | `5d5840e` | `tests/integration/test_shift_calendar_page.py` |
| **PR / RC** | Top-equipment chart: выдуманные нули (фантом Rental.moto_hours) | `ae25c22` | `tests/integration/test_revenue_by_vehicle.py` |
| **MK** | Показания счётчиков смен не доходили до БД | `759cecb` | `test_shift_meter_readings.py` + `test_driver_readings_api.py` |
| **MK** | Массовая генерация актов дублировала pricing | `2939f39` | `test_monthly_auto_acts.py` (доп. кейсы) |
| **MK** | Пустой отчёт о смене отвергался после lookup | `82dee56` | отдельного теста нет (driver.py) |
| **MK** | Расчёт ТО читал дневную выработку как пожизненный счётчик | `6aaa14c` | `test_maintenance_due_service.py` |
| **NEW-4 / revenue-by-vehicle test** | test_revenue_by_vehicle падал: фикстура без смен | `92d5560` | `test_finance_dashboard_api.py` — добавлена цепочка заявка→смена→отчёт→акт, ассерт moto_hours==8.0 (обработчик не менялся) |

---

## 3. DECISION — вопрос оператору + варианты

| ID | Вопрос оператору | Варианты | Доказательство/контекст |
|---|---|---|---|
| **AM-2** | Активный разносчик `BankMatchingService.match_transaction` сравнивает `tx.document_type` с `TransactionDirection` (разные enum) — стратегии «сумма+ИНН» и «только сумма» мертвы; чинить ли (это двигает деньги)? | (а) заменить на `tx.direction` и покрыть тестами; (б) оставить только стратегию по номеру счёта; (в) ручной разбор | `bank_matching_service.py:116/148/176` `tx.document_type == TransactionDirection.incoming/outgoing` — document_type это TransactionType (payment_order), всегда False. Работает только стратегия 1 (номер счёта в назначении, :78). Scheduler `_auto_match_payments` (scheduler.py:627) зовёт именно этот сервис. Семантику не менял — решение оператора |
| **AM-3** | У всех 19 актов `counterparty_inn` NULL, суммы платежей не пересекаются с остатками актов — разноска по ИНН невозможна, по сумме 0 совпадений; заполнять ли ИНН актов? | (а) заполнять counterparty_inn при создании актов; (б) разносить вручную; (в) оставить | read-only SQL: acts counterparty_inn 19/19 NULL; 30 неразнесённых платежей (4 incoming/26 outgoing), 13 неоплаченных актов; репликация as-code → 0 совпадений (латентно). AUTOMATCH_RISK d40db07 |
| **D-1** | Подтверждён ли app-password mail.ru для SMTP? | (а) app-password в .env.prod + up -d; (б) сменить провайдера; (в) email выкл | EMAIL_FAILURE: 535 app-password (исторически разрешён — подтвердить); 550 MIME починен |
| **D-2** | Включать ли MAX/FCM/Telegram и заполнить получателей (max_chat_id 0/12, telegram_id 0/12, device_tokens 0)? | (а) MAX+max_chat_id; (б) FCM+устройства; (в) Telegram+telegram_id; (г) только email/in_app | NOTIFICATION_DELIVERY: каналы мертвы (нет получателей + флаги) |
| **D-3** | Засеять ли notification_templates для кодов вне 4 DEFAULT_TEMPLATES? | (а) init_default_templates+коды; (б) расширить DEFAULT_TEMPLATES; (в) fallback 4 кода | таблица 0 строк; DEFAULT_TEMPLATES = role_change/overdue_acts/act_signed/act_rejected |
| **D-4** | Кто получатель weekly digest (фильтр accountant/admin/manager/owner, в БД driver/operator)? | (а) назначить роли; (б) изменить аудиторию; (в) отключить | weekly_digest_service.py:362 |
| **D-5** | Зависшие выплаты (>3 дней) только логируются — слать ли уведомление? | (а) email/in_app; (б) метрика+панель; (в) лог | scheduler.py:724 _check_pending_payouts |
| **D-6** | Задеплоить ли Celery-воркер (.delay без воркера латентен)? | (а) воркер; (б) APScheduler; (в) удалить .delay | Celery-worker-not-deployed |
| **D-7** | Публиковать ли репозиторий и в какой видимости? | (а) private; (б) public; (в) mirror | решение оператора |

---

## 4. OBSERVATION — не дефекты

| ID | Суть | Файл:строка | Почему не дефект |
|---|---|---|---|
| **PR-4 (исправление)** | `telegram_bot user.first_name` — НЕ дефект платформы | `backend/app/services/telegram_bot.py:38,66,73` | `user = update.effective_user` — объект **Telegram API** (у него есть first_name), а не User платформы. `linked_user.full_name or user.first_name` — корректный fallback. Прежняя пометка OPEN (AttributeError) была ошибочной: сравнивался не тот объект. Доказательство: telegram_bot.py:38 `user = update.effective_user` |
| **AM-1** | `auto_match_payments` в bank.py — мёртвый неопубликованный обработчик с дефектами | `backend/app/api/routes/shifts/bank.py:64-150` | Без декоратора (не опубликован), scheduler его НЕ зовёт (использует BankMatchingService, scheduler.py:627). Дефекты внутри: purpose_match всегда truthy (amount-only), нет фильтра direction (26 outgoing eligible), `remaining*0.01` Decimal×float → TypeError на первой паре, match_status не обновляется (повторная разноска). Мёртвый код — удаление на решение пользователя; активный путь — AM-2 |
| **O-1** | rbac_email_service.send_role_change_email с битым импортом | `rbac_email_service.py:10,33` | Не вызывается (admin.py использует email_service напрямую). Мёртвый код |
| **O-2** | driver_name в реестре всегда "" | `shifts/diadoc.py:315` | `getattr(a,"driver_name")` — у Act нет driver_name; недоделанная колонка. Данные водителя → NEW-1 |
| **O-3** | maintenance_due только лог + метрика | `scheduler.py:681`, gauge :921 | Покрыто метрикой/панелью Grafana |
| **O-4** | Поля возвращаются, но не читаются фронтом | get_driver_kpi active_days/total_days и др. | RESPONSE_CONTRACT §2 — не дефект |
| **O-5** | Калибровка Request.status=='new' | PHANTOM_READS Class 2 | Литерал совпадает с enum, работает |
| **O-6** | finance_reports.py:254 r.moto_hours | `finance_reports.py:254` | После ae25c22 — агрегат ShiftDataReconciliation, не фантом |
| **O-7** | Чтение ShiftTask.planned_start через getattr | `shifts/tasks.py:165` | Guarded fallback (5d5840e); запись в конструктор закрыта MK-2 |

---

## 5. Дубликаты и противоречия между отчётами

- **Нулевые часы** — PHANTOM_READS + MODEL_KWARGS + RESPONSE_CONTRACT → один корень, FIXED ed3b51f.
- **User.is_active** — SCHEDULER_JOB + NOTIFICATION_DELIVERY → FIXED 49a6cde.
- **Неопубликованные обработчики** — API_CONTRACT + UNPUBLISHED + PUBLICATION_READINESS → FIXED 9345b07/5d60c24; import_bank_payments → FIXED 1303aca (эта партия).
- **Переименования фронта** — API_CONTRACT + FRONTEND_RENAME → FIXED 4eadffc; 1c-acts → RC-8 FIXED f3eec50.
- **verify-signature** — FRONTEND_RENAME + RESPONSE_CONTRACT → RC-7 FIXED f3eec50 (форма приведена к ответу).
- **counterparty** — AUTOMATCH_RISK + RESPONSE_CONTRACT → RC-2 FIXED 5bcb5bf.
- **Подмена ID / salary / email MIME** — MODEL_KWARGS + NOTIFICATION_DELIVERY + EMAIL_FAILURE → FIXED 1ca407a.
- **bank-дефекты** — РАЗНЫЕ: `list_bank_transactions` (фантомные поля) FIXED f2a2a15; `sync_payments_to_db` (битый импорт) FIXED 5bcb5bf; `import_bank_payments` (публикация) FIXED 1303aca; `auto_match_payments` (мёртвый) AM-1 OBSERVATION. Не объединять.
- **PR-4 исправление** — PHANTOM_READS пометил `telegram_bot user.first_name` фантомом User; фактически объект Telegram API → OBSERVATION (доказательство telegram_bot.py:38). Противоречие resolved: аудит ошибся в природе объекта.
- **RC-3 vs NEW-1** — RC-3 (контракт реестра: поля signature/vehicle_id) FIXED в дереве пользователя; NEW-1 (данные актов NULL) OPEN. Разные слои: поле возвращается, но значение NULL.
- **RC-4 vs NEW-2** — RC-4 (поле gps_health) FIXED ac59018; NEW-2 (журнал-источник пуст) OPEN. Расчёт есть, данных нет.

---

## 6. Новые находки этой партии (подробно)

### NEW-1 / ACTS-NULL (OPEN, P4)
read-only SQL рабочей БД: `SELECT count(*) … FROM acts` → 19 актов; `driver_id IS NULL`=19, `hours_worked IS NULL`=19, `vehicle_id IS NULL`=19, `signature IS NULL`=19. Реестр (diadoc.py:301-325) теперь возвращает vehicle_id/signature/signed_at, но значения NULL → пустые колонки техники/водителя/часов, KEP-бейдж не появляется. Корень — генерация актов не заполняет эти поля (пользователь работает над созданием актов, finance.py запрещён агенту). Не выдумывать значения; заполнять из фактических связей смены/назначения.

### NEW-2 / GPS-SYNC (OPEN, P4)
`gps_sync_logs`=0 строк (read-only). Писатель `log_gps_sync` (base.py:156) существует и вызывается через `_logged_call` (base.py:113/127), обёрнутый вокруг async-методов провайдеров. Но scheduler `sync_gps_positions` (mapix_sync_task.py:128) вызывает `adapter.get_all_positions_sync()` (:177; wialon.py:117, mapix.py:328), который НЕ использует `_logged_call`/log_gps_sync → журнал не пишется. 3 техники с gps_provider настроены, но журнал пуст. Расчёт gps_health добавлен пользователем (ac59018, shift_stats_service.py:1366) — источник не наполняется → виджет пуст. Фикс: логировать в sync-пути (get_all_positions_sync) либо перевести sync на _logged_call. Уточнение формулировки «есть только читатель»: писатель есть, но активный путь его обходит.

### NEW-3 / TEMPLATES-422 (FIXED, дерево пользователя)
`apply_shift_templates` принимал `week_start: str = Body(...)` без embed → страница шлёт объект `{week_start: …}` → 422. Исправлено пользователем: `Body(..., embed=True)` (templates.py:128). Тест `test_templates_apply.py` (untracked). Не закоммичено.

### AM-1 / AM-2 / AM-3 — auto_match (расследование, семантика не менялась)
**Что не работает (bank.py auto_match_payments, мёртвый код):**
- `purpose_match` всегда truthy: условие `… or f"ACT-{act.id}"` всегда истинно; тело `purpose_match = act.document_number or …` — document_number NOT NULL → всегда truthy для любой пары. Проверка вхождения номера в purpose не вычисляется.
- Нет фильтра direction: выборка платежей берёт и incoming (4), и outgoing (26) → исходящие (наши платежи) могли бы разноситься на акты-дебиторку.
- `amount_match = abs(payment.amount - remaining) < max(remaining*0.01, 1)` — `remaining` Decimal, `*0.01` float → **TypeError на первой паре** (обработчик падает, если бы был вызван).
- `match_status` не обновляется (пишется только matched_act_id) → повторный запуск разносит тот же платёж снова (двойной учёт paid_amount).
**Активный путь:** scheduler `_auto_match_payments` (scheduler.py:627) зовёт `BankMatchingService.match_transaction`, НЕ мёртвый обработчик. В сервисе стратегия 1 (номер счёта в назначении) работает; стратегии 2/3 сравнивают `tx.document_type` с `TransactionDirection` (разные enum → всегда False) → «сумма+ИНН» и «только сумма» мертвы (AM-2, DECISION).
**Сколько в рабочей БД (read-only):** 30 неразнесённых (incoming 4: 70700/16000/26000/16000; outgoing 26), 13 неоплаченных актов (остатки: 62900.00×5, 62900.01×2, 62900.02×2, 40000.01×2, 40000.02×1, 122000.00×1), counterparty_inn актов 19/19 NULL. Репликация as-code (Decimal-арифметика) → **0 совпадений по сумме** (суммы платежей не попадают в ±1% остатков актов). Риск латентный: при совпадении суммы мёртвый обработчик разнёс бы произвольно (первый акт по порядку, без ИНН/назначения/direction), но он не опубликован и не вызывается. Активный сервис ограничивает риск (стратегия 1 по номеру), но AM-2 требует решения оператора (деньги).

---

## 7. Сводка

- **OPEN: 2** — P4: NEW-1 (ACTS-NULL), NEW-2 (GPS-SYNC). P1–P3 из аудитов закрыты.
- **FIXED: 31** находка (§2): коммиты ac59018/5bcb5bf/1303aca/f3eec50/92d5560/1ca407a/ed3b51f/49a6cde/ac4f54b/f2a2a15/4eadffc/9345b07/5d60c24/5d5840e/ae25c22/759cecb/2939f39/82dee56/6aaa14c + дерево пользователя (PR-1, MK-2, NEW-3, RC-3/RC-6 — не закоммичены, тесты untracked). Оговорки без отдельного теста: FR 4eadffc (typecheck), 82dee56, ND role-change.
- **DECISION: 9** — AM-2, AM-3 (деньги/данные) + D-1…D-7.
- **OBSERVATION: 9** — PR-4 (исправление: Telegram API), AM-1 (мёртвый обработчик) + O-1…O-7.

Первоочередное: **NEW-1** (заполнение актов при создании — пользователь работает над этим) и **NEW-2** (логирование GPS-sync). **AM-2/AM-3** — разбор оператора (разноска двигает деньги; семантика агентом не менялась). Каналы уведомлений разблокируют D-1/D-2/D-3.
