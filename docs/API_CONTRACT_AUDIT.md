# API_CONTRACT_AUDIT — сплошная сверка frontend ↔ API

Дата: 2026-11-19. Режим: только расследование; правки кода/конфигов/тестов запрещены и не выполнялись; рабочая БД не изменялась; внешняя отправка не выполнялась. `backend/app/api/routes/shifts/bank.py` и `finance.py` читаются как есть (пользователь правит их сам) — дефекты описаны, не исправлены.

## Метод и источники истины
- **Маршруты:** перечислены `app.routes` В ПРОЦЕССЕ (импорт `app.main`, `APIRoute.methods/path`, включая `include_in_schema=False`) — **431 маршрут**. Не чтение декораторов (декоратора может не быть → функция не зарегистрирована → 404).
- **Вызовы фронтенда:** AST/regex по `frontend/src` (144 ts/tsx), `apiClient.{get,post,put,patch,delete}(path)` — **262 вызова**; `baseURL = …/api/v1` (client.ts:8), пути фронтенда без префикса. Нормализация `${…}` ↔ `{param}`, сопоставление метод+путь.
- Результат матчинга: **226 OK, 31 NOT_FOUND, 5 METHOD_MISMATCH**. Каждый NOT_FOUND/MISMATCH сверен с полным списком маршрутов (ложные артефакты матчера отброшены).
- Форма запроса (C) и поля ответа (D) проверены детально в калибровочной зоне bank/finance и точечно; сплошной D-проход по всем 226 совпавшим маршрутам не выполнялся (охват указан ниже).

---

## TIER 1 — страница не открывается / действие не выполняется (404/405/500)

Доказательство для всех: путь отсутствует в `app.routes` (431) либо метод не совпадает; указан реальный маршрут, если есть.

### ShiftCalendarPage (несколько независимых расхождений)
| Фронтенд | Вызов | Реальный маршрут | Итог |
|---|---|---|---|
| ShiftCalendarPage.tsx:127 | `GET /shifts` | `GET /shifts/tasks` (list_shift_tasks) | 404 — календарь не грузится |
| ShiftCalendarPage.tsx:155 | `POST /shifts/tasks/bulk-auto-assign` | `POST /shifts/bulk-auto-assign` | 404 — массовое автоназначение не работает |
| ShiftCalendarPage.tsx:146 | `POST /shifts/tasks/${taskId}/auto-assign-driver` | `POST /shifts/{task_id}/auto-assign` | 404 — автоназначение водителя не работает |
| ShiftCalendarPage.tsx:185 | `PUT /shifts/${draggedShift}` | `PUT /shifts/tasks/{task_id}` | 404 — drag-drop перенос смены не работает |

### Страницы, целиком не работающие (маршрутов нет)
| Страница | Вызовы (file:line) | Доказательство |
|---|---|---|
| ProfilePage | `GET/PUT /shifts/profile/me` (ProfilePage.tsx:14,27,30,47) | в app.routes есть только `/shifts/profile/notification-settings`, `/shifts/profile/unbind-max`; `/shifts/profile/me` нет → 404, профиль пуст |
| DocumentArchivePage | `GET/POST /shifts/documents/archive`, `POST …/auto-index-acts` (DocumentArchivePage.tsx:20,37,49) | маршрутов `/shifts/documents/*` нет → 404 |
| NotificationTemplatesPage | `GET /shifts/notification-templates`, `POST …/init-defaults`, `PUT …/${id}` (NotificationTemplatesPage.tsx:13,22,30) | маршрутов нет → 404 |
| AutoAssignRulesPage | `GET/POST /shifts/auto-assign/rules`, `DELETE …/${id}` (AutoAssignRulesPage.tsx:12,23,31) | маршрутов `/shifts/auto-assign/rules` нет → 404 |
| FinanceDashboardPage | `GET /shifts/stats/finance-dashboard` (FinanceDashboardPage.tsx:12) | есть `/shifts/stats/fuel-dashboard`, `/finance/dashboard`, но не `finance-dashboard` → 404 |
| PnLPerVehiclePage | `GET /shifts/stats/pnl-per-vehicle` (PnLPerVehiclePage.tsx:13) | реальный `GET /shifts/stats/pnl` (get_pnl_per_vehicle) → 404 (wrong path) |
| CostPerHourPage / OnboardingWizardPage | `GET /shifts/cost-rates` (CostPerHourPage.tsx:25), `PUT /shifts/cost-rates` (CostPerHourPage.tsx:31, OnboardingWizardPage.tsx:20) | реальный `GET/PATCH /shifts/stats/cost-rates` → 404 (пропущен `/stats`) + PUT vs PATCH |
| DispatcherDashboard | `POST /shifts/alerts/check-idle` (DispatcherDashboard.tsx:19), `POST /shifts/alerts/check-conflicts` (:26) | реальные `GET /shifts/alerts/idle-vehicles`, `GET /shifts/alerts/conflicts` → 404 (path+method) |
| DriverAppPage | `POST /drivers/shifts/${taskId}/start` (DriverAppPage.tsx:46) | маршрута `/drivers/shifts/{id}/start` нет в app.routes → 404. **Требует подтверждения:** driver.py содержит `start_shift` (`/shifts/{task_id}/start`), уточнить префикс монтирования drivers-роутера |

### Действия с актами / счетами / отзывами (finance.ts, client.ts)
| Фронтенд | Вызов | Доказательство |
|---|---|---|
| finance.ts:314 | `DELETE /finance/invoices/${id}` | есть только `GET /finance/invoices/{invoice_id}` (+pdf/resend); DELETE не зарегистрирован → 404, удаление счёта не работает |
| finance.ts:374 | `DELETE /acts/${id}` | маршрута `DELETE /acts/{id}` нет → 404 |
| finance.ts:525 | `GET /acts/${actId}/xml` | нет → 404 |
| finance.ts:530 | `GET /acts/${actId}/signed-xml` | нет → 404 |
| finance.ts:535 | `GET /acts/${actId}/signature` | нет (есть `GET /shifts/acts/{act_id}/verify-signature`) → 404 |
| finance.ts:540 | `POST /acts/${actId}/verify-signature` | реальный `GET /shifts/acts/{act_id}/verify-signature` → 404 (prefix+method) |
| finance.ts:558 | `POST /acts/${actId}/reject` | нет → 404 |
| client.ts:227 | `POST /reviews/${reviewId}/respond` | есть `POST /reviews`, `PATCH/DELETE /reviews/{id}`; `/respond` нет → 404, ответ на отзыв не работает |
| RequestDetailPage.tsx:273 | `POST /requests/bulk-responses` | реальный `POST /requests/responses/bulk-action` → 404 (wrong path; артефакт матчера METHOD_MISMATCH снят) |
| UserRolesPage.tsx:31 | `PUT /shifts/users/bulk-role` | реальный `POST /shifts/users/bulk-role` → **405** (method mismatch) |

### BankTransactionsPage — 500 из-за фантомных полей (зона правки пользователя)
- `GET /shifts/bank/transactions` (BankTransactionsPage.tsx:21) → маршрут ТЕПЕРЬ зарегистрирован (bank.py:252), но обработчик `list_bank_transactions` читает `t.payer_name / t.payer_inn / t.payee_name / t.status` (bank.py:295-300). У `BankTransaction` этих полей НЕТ (есть `counterparty_name/counterparty_inn`, `match_status`) → **AttributeError → 500**. Страница не открывается.
- Фронтенд читает `t.payer_name`, `t.payer_inn` (BankTransactionsPage.tsx:109) — даже после устранения краха поля будут `undefined`, пока backend не отдаст их (маппинг counterparty_* → payer_*). **Неверные данные / пусто.**

---

## Калибровка BankTransactionsPage: статус трёх исходных расхождений (bank.py читается как есть)
1. **Не опубликованы (декораторов нет):** `GET /bank/transactions` и `POST …/{txn_id}/match` ТЕПЕРЬ опубликованы (bank.py:252, 333). **Остаются без декораторов:** `auto_match_payments` (bank.py:63) и `import_bank_payments` (bank.py:25) — не зарегистрированы (если фронтенд их вызовет → 404; текущий фронтенд auto-match/import не вызывает).
2. **Фантомные поля в обработчике:** `list_bank_transactions` читает payer_name/payer_inn/payee_name/status (bank.py:295-300) → 500. **ЕЩЕ ПРИСУТСТВУЕТ.** `auto_match_payments` также читает `BankTransaction.status=="processed"` и `payment.payer_inn` (bank.py:77,108) → фантом.
3. **Scalar Body vs объект:** `manual_match_transaction` теперь `act_id: int = Body(..., embed=True)` (bank.py:338), фронтенд шлёт `{ act_id: Number(selectedActId) }` (BankTransactionsPage.tsx:41) → **ИСПРАВЛЕНО**, контракт совпадает.

---

## TIER 2 — неверные данные (поля ответа, которых нет)
- BankTransactionsPage.tsx:109 `t.payer_name / t.payer_inn` — backend не возвращает (фантомные поля модели, см. Tier 1). Пользователь видит «—» вместо плательщика/ИНН.
- **Требует подтверждения (сплошной D-проход не выполнен):** для остальных 226 совпавших маршрутов поля ответа точечно не сверялись; потенциальные undefined-поля возможны в других страницах. Калибровочная зона bank/finance проверена детально.

---

## Что проверено и проблем НЕ найдено (охват)
- **226 из 262 apiClient-вызовов** совпали с зарегистрированными маршрутами по методу+пути (полный список — `/tmp/contract_match.json`, статус OK).
- **files.ts:91 `GET /files/${query}`** — ложное срабатывание матчера: `query` = строка `?params`, реальный путь `/files/` → `GET /files/` (list_files) существует. OK.
- **bank transactions/match пути** теперь совпадают; **match Body** (embed=True + `{act_id}`) — контракт совпадает.
- WS-ticket (`POST /ws/ticket`, `/chat/ws-ticket`), pricing (`/requests/pricing/*`), edo-settings (`/edo-settings`) — зарегистрированы и соответствуют вызовам (подтверждено ранее, память ws-ticket/edo-settings/pricing).
- Артефакты матчера METHOD_MISMATCH для `/requests/bulk-responses` и `/shifts/tasks/bulk-auto-assign` переквалифицированы в NOT_FOUND (статический путь не должен матчиться с `{param}`); реальные альтернативные маршруты указаны.

## Сводка приоритетов
1. **Целиком сломанные страницы:** ShiftCalendarPage (4 расхождения), ProfilePage, DocumentArchivePage, NotificationTemplatesPage, AutoAssignRulesPage, FinanceDashboardPage, PnLPerVehiclePage, CostPerHourPage, DispatcherDashboard, DriverAppPage(start), BankTransactionsPage (500).
2. **Неработающие действия:** удаление счёта/акта, XML/подпись/отклонение акта, ответ на отзыв, bulk-responses, bulk-role (405), автоназначение.
3. **Неверные данные:** payer_name/payer_inn в BankTransactionsPage.
4. **Калибровка bank.py:** #3 исправлено, #1 частично (auto_match/import без декораторов), #2 ещё есть (фантомные поля → 500).

Все находки — отчёт; исправление решает пользователь (bank.py/finance.py пользователь правит сам). Ничего не правилось.
