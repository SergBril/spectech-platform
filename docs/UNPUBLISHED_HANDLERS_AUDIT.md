# UNPUBLISHED_HANDLERS_AUDIT — обработчики написаны, но не опубликованы

Дата: 2026-11-19. Режим: только расследование; правки кода/конфигов/тестов запрещены и не выполнялись; рабочая БД не изменялась; внешняя отправка не выполнялась. `shifts/tasks.py`, `shift_task_service.py`, `ShiftCalendarPage.tsx` читаются как есть (пользователь правит сам).

## Метод
1. **Источник истины:** `app.routes` в процессе (импорт `app.main`) — **428 зарегистрированных маршрутов** (было 431 в прошлом аудите; пользователь правит tasks.py).
2. **AST по `app/api/routes/**`:** топ-level функции с handler-сигнатурой (`Depends/Body/Query/File/Form/UploadFile` в параметрах) ИЛИ с декоратором `@router.*`. Сопоставление с зарегистрированными по `(endpoint.__module__, endpoint.__name__)`.
3. Результат: **424 обработчика совпали** (зарегистрированы), **17 не опубликованы**: 16 без декоратора + 1 с декоратором, но роутер не подключён.

---

## Раздел 1. Обработчики БЕЗ декоратора (написаны, не опубликованы) — 16

Все — реальные обработчики (Depends(get_db/get_current_user), Body/Query, возврат данных/HTTPException). Префикс shifts-роутеров `/api/v1/shifts` (main.py:241). Предполагаемый путь — по имени/телу и совпадающему вызову фронтенда.

### Целые страницы не работают (обработчик есть → опубликовать)
| Файл:строка | Функция | Метод/путь (предполаг.) | Вызов фронтенда | Что видит пользователь |
|---|---|---|---|---|
| shifts/admin.py:442 | `get_my_profile` | GET /shifts/profile/me | ProfilePage.tsx:14,30,47 | профиль пуст (404) |
| shifts/admin.py:473 | `update_my_profile` | PUT /shifts/profile/me | ProfilePage.tsx:27 | сохранение профиля не работает |
| shifts/admin.py:377 | `list_notification_templates` | GET /shifts/notification-templates | NotificationTemplatesPage.tsx:13 | список шаблонов пуст |
| shifts/admin.py:402 | `update_notification_template` | PUT /shifts/notification-templates/{tmpl_id} | NotificationTemplatesPage.tsx:30 | правка шаблона не работает |
| shifts/admin.py:429 | `init_defaults` | POST /shifts/notification-templates/init-defaults | NotificationTemplatesPage.tsx:22 | кнопка «создать стандартные» не работает |
| shifts/documents.py:23 | `search_document_archive` | GET /shifts/documents/archive | DocumentArchivePage.tsx:20 | архив документов пуст |
| shifts/documents.py:92 | `add_to_archive` | POST /shifts/documents/archive | DocumentArchivePage.tsx:37 | добавление в архив не работает |
| shifts/documents.py:136 | `auto_index_acts` | POST /shifts/documents/archive/auto-index-acts | DocumentArchivePage.tsx:49 | авто-индексация актов не работает |
| shifts/templates.py:315 | `list_auto_assign_rules` | GET /shifts/auto-assign/rules | AutoAssignRulesPage.tsx:12 | правила авто-назначения пусты |
| shifts/templates.py:348 | `create_auto_assign_rule` | POST /shifts/auto-assign/rules | AutoAssignRulesPage.tsx:23 | создание правила не работает |
| shifts/templates.py:377 | `delete_auto_assign_rule` | DELETE /shifts/auto-assign/rules/{rule_id} | AutoAssignRulesPage.tsx:31 | удаление правила не работает |
| shifts/finance.py:17 | `get_finance_dashboard` | GET /shifts/stats/finance-dashboard | FinanceDashboardPage.tsx:12 | финансовый дашборд пуст |
| shifts/finance.py:164 | `export_finance_dashboard_excel` | GET /shifts/stats/finance-dashboard/export | требует подтверждения | экспорт дашборда не работает |

Модели/сервисы для всех существуют: NotificationTemplate, DocumentArchive, AutoAssignRule, CompanyCostRates/ShiftFuelEntry/Act; notification_template_service.init_default_templates. **Решение: опубликовать (добавить декораторы), не писать с нуля.**

### Действия (обработчик есть, фронтенд может не вызывать)
| Файл:строка | Функция | Метод/путь | Вызов фронтенда | Примечание |
|---|---|---|---|---|
| shifts/bank.py:25 | `import_bank_payments` | POST /shifts/bank/import | не найден | калибровка: без декоратора; Body format. Также читает фантомные поля (см. PHANTOM_READS) |
| shifts/bank.py:63 | `auto_match_payments` | POST /shifts/bank/auto-match | не найден | калибровка: без декоратора; читает BankTransaction.status/payer_inn (фантом) → при публикации упадёт 500 |
| shifts/mobile.py:289 | `sync_fuel_card_transactions` | POST /shifts/mobile/fuel-card/sync | требует подтверждения | fuel_card_service существует; Body date_from/date_to/card_numbers |

Калибровка bank.py: из 4 исходных функций без декораторов `list_bank_transactions` и `manual_match_transaction` ТЕПЕРЬ опубликованы (пользователь добавил декораторы, bank.py:252,333); `import_bank_payments` и `auto_match_payments` остаются без декораторов.

---

## Раздел 2. С декоратором, но НЕ в app.routes (роутер не подключён) — 1

| Файл:строка | Функция | Декоратор | Причина | Вызов фронтенда |
|---|---|---|---|---|
| storage.py:13 | `upload_file` | `@router.post("/upload")` | `storage.router` НЕ импортируется и НЕ подключён через `include_router` в main.py (есть только `storage_service`, main.py:84) | фронтенд использует `/files/upload` (files_route подключён, main.py:259), не storage |

Тот же 404, но причина — не подключённый роутер. **Требует подтверждения:** storage-роутер намеренно не смонтирован (ранее отмечено как решение пользователя); фронтенд обслуживается files-роутером, поэтому видимого последствия нет. Решение: подключить роутер либо удалить orphan-модуль.

---

## Раздел 3. Вердикт по страницам прошлого отчёта (где маршрута нет)

| Страница / вызов | Вердикт | Доказательство / что делать |
|---|---|---|
| ProfilePage `/shifts/profile/me` | **существует, не опубликован** | admin.py:442 get_my_profile / :473 update_my_profile без декораторов → опубликовать |
| DocumentArchivePage `/shifts/documents/*` | **существует, не опубликован** | documents.py:23/92/136 без декораторов → опубликовать |
| NotificationTemplatesPage | **существует, не опубликован** | admin.py:377/402/429 без декораторов → опубликовать |
| AutoAssignRulesPage | **существует, не опубликован** | templates.py:315/348/377 без декораторов → опубликовать |
| FinanceDashboardPage `/shifts/stats/finance-dashboard` | **существует, не опубликован** | shifts/finance.py:17 get_finance_dashboard без декоратора → опубликовать (отдельный от зарегистрированного `/finance/dashboard`) |
| `/drivers/shifts/{id}/start` (DriverAppPage:46) | **существует под ДРУГИМ путём** | driver.py:107 `@router.post("/shifts/{task_id}/start")`, роутер на `/api/v1/driver` (main.py:319, ед.ч.) → зарегистрирован `/api/v1/driver/shifts/{task_id}/start`. Фронтенд зовёт `/drivers/` (мн.ч.) → 404. **Решение: переименовать путь фронтенда на `/driver/shifts/{id}/start`** |
| `DELETE /finance/invoices/{id}` | **отсутствует вовсе** | finance.py: только GET /invoices/{id} (:85), pdf (:721), resend-email (:753); DELETE-обработчика нет. Invoice-модель есть → можно написать delete |
| `DELETE /acts/{id}` | **отсутствует вовсе** | acts.py: только 4 GET PDF (pdf/invoice-facture/upd/torg12); delete нет. Act-модель/act_service есть → можно написать |
| `/acts/{id}/xml` | **отсутствует вовсе** | acts.py нет xml-роута. Генератор `generate_upd_xml` существует (shifts/diadoc send-act) → можно построить GET на нём |
| `/acts/{id}/signed-xml` | **отсутствует вовсе** | обработчика нет; требует подтверждения источник signed-XML (КЭП sign есть в shifts/diadoc) |
| `/acts/{id}/signature` | **отсутствует под этим путём** | есть `GET /shifts/acts/{act_id}/verify-signature` и `POST /shifts/acts/{act_id}/sign` (shifts/diadoc). Отдельного `/acts/{id}/signature` нет → переименовать/построить |
| `/acts/{id}/reject` | **отсутствует вовсе** | обработчика нет; Act.status имеет rejected/rejected_by_client → можно написать |
| `/reviews/{id}/respond` | **отсутствует вовсе** | reviews.py:416 — это `mark_review_helpful` (`/public/reviews/{id}/helpful`), не respond. Respond-обработчика нет. Review-модель есть; поле response — требует подтверждения → можно написать |

---

## Что проверено и проблем НЕ найдено (охват)
- **424 обработчика** в `app/api/routes/**` совпали с зарегистрированными маршрутами (module+name) — опубликованы корректно.
- `driver.py start_shift` зарегистрирован (под `/api/v1/driver/...`, ед.ч.) — не unpublished, а расхождение префикса с фронтендом.
- `list_bank_transactions`, `manual_match_transaction` (bank.py) теперь опубликованы (декораторы добавлены пользователем).
- Ложных срабатываний «handler-like helper без регистрации» среди 17 кандидатов не обнаружено — все 16 NO_DECORATOR являются реальными обработчиками (сигнатура + тело подтверждены чтением).

## Сводка: что делать
1. **Опубликовать (добавить декораторы):** ProfilePage, DocumentArchivePage, NotificationTemplatesPage, AutoAssignRulesPage, FinanceDashboardPage (+export), bank import/auto-match (сначала починить фантомные поля), mobile fuel-card sync. Обработчики и модели уже есть.
2. **Переименовать путь:** DriverAppPage start `/drivers/` → `/driver/`; `/acts/{id}/signature` → существующий `/shifts/acts/{id}/verify-signature`.
3. **Написать с нуля:** DELETE /finance/invoices/{id}, DELETE /acts/{id}, /acts/{id}/xml (на generate_upd_xml), /acts/{id}/signed-xml, /acts/{id}/reject, /reviews/{id}/respond. Модели есть; функциональность в бэкенде отсутствует.
4. **Подключить/удалить роутер:** storage.py (не смонтирован; фронтенд использует files).

Все находки — отчёт; исправление решает пользователь. Ничего не правилось.
