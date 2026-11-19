# PUBLICATION_READINESS — готовность 16 неопубликованных обработчиков к публикации

Дата: 2026-11-19. Режим: только расследование; правки кода/конфигов/тестов и публикация обработчиков запрещены (публикует пользователь); рабочая БД не изменялась; внешняя отправка не выполнялась. `shifts/tasks.py`, `schemas/shift.py`, `shift_task_service.py`, `ShiftCalendarPage.tsx` читаются как есть.

## Метод
Для каждого обработчика: (1) чтения/записи полей — интроспекция `mapper.columns/relationships` (nullable/type); (2) конструкторы — kwargs против колонок + NOT NULL; (3) форма запроса — Body/Form/Query против того, что шлёт фронтенд; (4) форма ответа — поля страницы против возврата обработчика + риск response_model на nullable; (5) внешние вызовы. Фронтенд-формы сняты чтением страниц (AutoAssignRulesPage/ProfilePage/NotificationTemplatesPage/DocumentArchivePage/FinanceDashboardPage).

---

## ПОРЯДОК ПУБЛИКАЦИИ: сначала готовые (13), затем сломанные (3)

### Группа A — ГОТОВЫ к публикации (оживут сразу, без риска)

| # | Обработчик (file:line) | Вердикт | Доказательство |
|---|---|---|---|
| 1 | admin.py:442 `get_my_profile` | **готов** | читает только валидные User-поля (id/email/full_name/phone/role/is_superuser/telegram_id/max_chat_id/status/last_login_at/created_at — все в mapper); `getattr(role)` и `status.value` guarded. ProfilePage читает ровно эти поля. Внешних вызовов нет |
| 2 | admin.py:473 `update_my_profile` | **готов** | пишет full_name/phone (валидны, nullable); Body {full_name, phone} ↔ ProfilePage PUT `form={full_name,phone}` (объект). audit log_action. Внешних нет |
| 3 | admin.py:377 `list_notification_templates` | **готов** | читает NotificationTemplate.code/channel/subject/body/is_active (валидны); возврат list ↔ страница `Array.isArray`. body NOT NULL → `t.body.substring` безопасен. **Нюанс:** subject nullable — не добавлять response_model с обязательным subject:str |
| 4 | admin.py:402 `update_notification_template` | **готов** | Body {subject, body, is_active} ↔ страница PUT `editForm={subject,body}` (is_active default None → не меняется); пишет валидные поля; RBAC require. Внешних нет |
| 5 | admin.py:429 `init_defaults` | **готов** | вызывает notification_template_service.init_default_templates: `NotificationTemplate(code=, channel=, body=)` — NOT NULL code/channel/body заполнены (service:110-114), is_active model default. Возврат {created} ↔ страница |
| 6 | templates.py:315 `list_auto_assign_rules` | **готов** | читает AutoAssignRule (валидны), config_json→json.loads guarded; возврат list {id,name,priority,rule_type,config,is_active} ↔ страница. Внешних нет |
| 7 | templates.py:348 `create_auto_assign_rule` | **готов** | `AutoAssignRule(company_id,name,rule_type,priority,config_json,is_active,created_by)` — все kwargs валидны; NOT NULL company_id/name/rule_type/priority/is_active заполнены (name/rule_type Body(...), priority default 0, is_active=True). Body-объект {name,rule_type,priority,config} ↔ страница POST `{...form, config:configObj}`. Внешних нет |
| 8 | templates.py:377 `delete_auto_assign_rule` | **готов** | db.get + company_id check + db.delete; валидно. ↔ страница DELETE. Внешних нет |
| 9 | documents.py:23 `search_document_archive` | **готов** | читает DocumentArchive (валидны), Query все optional; возврат {items,total,page,per_page,pages} ↔ страница. **Нюанс:** doc_number/file_path/related_act_id nullable — не требовать их в response_model |
| 10 | documents.py:136 `auto_index_acts` | **готов** | читает Act.vehicle_id/hours_worked/total_amount/act_date/document_number (валидны, getattr-safe); `DocumentArchive(...)` kwargs валидны, NOT NULL company_id/doc_type/title заполнены. Возврат {indexed,message} ↔ страница. Внешних нет |
| 11 | shifts/finance.py:17 `get_finance_dashboard` | **готов** | читает Act.total_amount/act_date, ShiftFuelEntry.quantity_liters, CompanyCostRates (валидны); Query year optional; возврат {year,summary{total_revenue,total_expenses,total_margin,total_margin_pct},months[...]} ↔ FinanceDashboardPage читает ровно эти ключи. Внешних нет |
| 12 | shifts/finance.py:164 `export_finance_dashboard_excel` | **готов** | вызывает get_finance_dashboard напрямую (Python, не HTTP) → работает даже до публикации dashboard; ключи report['summary']/['months'] совпадают с возвратом (finance.py:148-160); openpyxl ImportError guarded→500; StreamingResponse. ↔ страница Excel `/shifts/stats/finance-dashboard/export`. Внешних нет |
| 13 | mobile.py:289 `sync_fuel_card_transactions` | **готов (с оговоркой)** | fuel_card_service.fetch_transactions: `enabled=bool(FUEL_CARD_API_KEY)`; **FUEL_CARD_API_KEY пуст (проверено в settings) → STUB, внешнего вызова нет**. Body {date_from,date_to,card_numbers}. **Риск:** при настройке FUEL_CARD_API_KEY пойдёт внешний httpx (gpnbonus.ru/lukoil-card.ru) при первом запросе. sync_to_shift_entries на stub-данных пуст → безопасно |

### Группа B — СЛОМАНЫ / требуют починки ДО публикации (404 → 500/422/неверные данные)

| # | Обработчик | Вердикт | Где сломается (доказательство) |
|---|---|---|---|
| 14 | documents.py:92 `add_to_archive` | **сломается: 422 (форма запроса)** | `title: str = Body(...)`, doc_type/doc_number/content_text = `Body(...)`, file = `File(...)`. Фронтенд DocumentArchivePage шлёт **multipart FormData** (title/doc_type/... как form-поля). `Body(...)` ожидает JSON-тело, а не form-поля multipart → title не извлекается → **422 field required**. Нужно `Form(...)` для текстовых полей (как сделано в driver.py start_shift). Конструктор DocumentArchive и NOT NULL — в порядке; проблема только в форме запроса |
| 15 | bank.py:25 `import_bank_payments` | **сломается: 500 (конструктор в сервисе)** | вызывает `bank_integration_service.sync_payments_to_db` → `BankTransaction(doc_number=, doc_date=, payer_inn=, payer_name=, payer_account=, payee_inn=, payee_name=, payee_account=, status=)` — **9 неверных kwargs** (mapper: document_number/document_date/counterparty_inn/counterparty_name/counterparty_account/match_status; payee_* нет) → TypeError (доказано конструированием в памяти, PHANTOM_READS/SILENT_NOOP). Публикация import без починки sync_payments_to_db = 500 |
| 16 | bank.py:63 `auto_match_payments` | **сломается: неверная разноска денег (логика)** | фантомные чтения ИСПРАВЛЕНЫ пользователем (match_status:75, counterparty_inn:108 — валидны). НО `purpose_match` (bank.py:113-125): из-за приоритета операторов `getattr(act,"document_number",None) or (... in payment.purpose...)` → document_number NOT NULL всегда truthy → **purpose_match = строка document_number (всегда truthy)**, ветка `in payment.purpose` не вычисляется. Условие `amount_match and (inn_match or purpose_match or ...)` → matches **по одной сумме (±1%), игнорируя ИНН/назначение**. Риск: платёж разносится на чужой акт, act.paid_amount/payment_status=paid неверно. **Требует подтверждения** замысла; это не 500, а неверные деньги. publicar только после починки purpose_match |

---

## response_model: предостережение (паттерн пользователя ShiftTaskRead.operator_id)
Все 16 сейчас возвращают dict/list **без response_model** (декораторов нет). При публикации НЕ добавлять строгий response_model с обязательными полями на nullable-колонках — иначе ResponseValidationError (как ShiftTaskRead.operator_id:int при nullable operator_id). Nullable-поля, возвращаемые обработчиками: `subject` (NotificationTemplate), `doc_number/file_path/related_act_id` (DocumentArchive), `phone/telegram_id/max_chat_id/last_login_at` (User), `config` (AutoAssignRule.config_json nullable). Либо делать поля схемы Optional, либо не задавать response_model.

## Внешние вызовы при первом запросе
- **mobile.sync_fuel_card_transactions** → fuel_card_service.fetch_transactions → внешний httpx (gpnbonus/lukoil) **только если FUEL_CARD_API_KEY задан** (сейчас пуст → stub). Единственный внешний риск среди 16.
- bank.import (парсинг файла), bank.auto_match (DB-матчинг), documents (локальная запись файла uploads/archive / DB), admin/templates/finance — **внешних вызовов нет** (Diadoc/MAX/email/FCM не задействованы).
- (ProfilePage отдельно зовёт зарегистрированный `/shifts/max/test-webhook` — он вне 16 и шлёт MAX; к публикации этих 16 не относится.)

## Что проверено и проблем НЕ найдено (охват)
- 13 обработчиков группы A: чтения/записи полей валидны (mapper), конструкторы заполняют NOT NULL, форма запроса совпадает с фронтендом (Body-объекты ↔ объект, Query optional), форма ответа совпадает с полями страниц, внешних вызовов нет.
- Фантомные ПРИСВАИВАНИЯ немаппленных полей (тише падения) среди 16 **не обнаружены** (в отличие от task.planned_start в tasks.py, который пользователь правит сам): auto_match пишет matched_act_id/paid_amount/payment_status (валидны), create_auto_assign_rule/create DocumentArchive — валидные kwargs.
- bank.py auto_match: фантомные ЧТЕНИЯ (status/payer_inn) уже исправлены пользователем на match_status/counterparty_inn.

## Итог
- **Публиковать сразу (13):** admin profile (2) + notification templates (3), templates auto-assign (3), documents search/auto-index (2), finance dashboard/export (2), mobile fuel-card sync (1, stub).
- **Чинить до публикации (3):** documents.add_to_archive (Body→Form, 422), bank.import_bank_payments (sync_payments_to_db kwargs, 500), bank.auto_match_payments (purpose_match логика, неверные деньги).
- Не добавлять строгий response_model на nullable; mobile sync — внешний риск при настройке FUEL_CARD_API_KEY.

Все находки — отчёт; публикацию и починку выполняет пользователь. Ничего не правилось.
