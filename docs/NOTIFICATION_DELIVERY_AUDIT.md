# NOTIFICATION_DELIVERY_AUDIT — уведомления, которые молча не доходят

Дата: 2026-11-19. Режим: только расследование; рабочая БД **только чтение** (SELECT); правки кода/конфигов/тестов запрещены; **никакой реальной отправки** (MAX/email/push/Diadoc) и вызова ручек отправки не выполнялось. `shift_stats_service.py`, тест pnl не тронуты. Коммит — только этот отчёт через pathspec с проверкой состава до push.

Метод: данные рабочей БД (получатели/шаблоны/журналы) + флаги каналов в процессе + `inspect.getsource` цепочек отправки (email_service.send_email, max_messenger.notify_user/notify_company_dispatchers, fcm_service.send_to_user, alert_service, notification_dispatcher, notification_service.create_notification, render_template) + вызовы в коде/планировщике.

---

## 1. Данные рабочей базы (запросы, read-only)

| Метрика | Значение | Запрос |
|---|---|---|
| users всего | 12 | `select count(*) from users` |
| users с max_chat_id | **0** | `… where max_chat_id is not null and max_chat_id<>''` |
| users с telegram_id | **0** | `… where telegram_id is not null` |
| users с email | 12 | `… where email is not null and email<>''` |
| device_tokens (FCM) всего | **0** | `select count(*) from device_tokens` |
| notification_templates | **0** (пусто) | `select count(*) from notification_templates` |
| notifications (in_app журнал) | 15 (in_app; is_read False 10 / True 5; sent_at null 0; user_id 1→13, 2→2, null 0) | `select channel/is_read/user_id, count(*) … group by` |
| email_logs | 21: **sent 8 / failed 13** | `select status, count(*) from email_logs group by status` |
| email_logs отказы | 10× `(550, your mailer sends invalid headers)`; 3× `(535, NEOBHODIM parol prilozheniya …)` | `select status, left(error_message,90), count(*) … group by` |
| user_companies | 7 | `select count(*) from user_companies` |
| user_notification_preferences | 1 (uid=1, все notify_* True) | `select … from user_notification_preferences` |

**Флаги каналов (в процессе, без отправки):** `EMAIL_ENABLED=True, SMTP_HOST=smtp.mail.ru, SMTP_USER=<set>, SMTP_PASSWORD=<set>`; `MAX_ENABLED=False, MAX_BOT_TOKEN=<empty>`; `TELEGRAM_ENABLED=False, TELEGRAM_BOT_TOKEN=<empty>`; `FCM_CREDENTIALS_PATH=<missing>`. `email_service.enabled=True; max_service.enabled=False; max_messenger.enabled=False; fcm.enabled=False`. `should_notify(uid, role_change/overdue, email/max)=True` (default True).

---

## 2. Статус каналов (сквозной)

| Канал | Статус | Где обрыв (глобально) | Доказательство |
|---|---|---|---|
| **MAX** | **МЁРТВ** | (1) `max_chat_id` нет ни у одного пользователя (0/12) → `notify_user` возвращает `skipped:no_max_chat_id` ДО отправки; (2) `MAX_ENABLED=False`/`MAX_BOT_TOKEN` пуст → `send_message` stub | max_messenger_service.notify_user (getattr max_chat_id → skip); settings; users 0/12 |
| **FCM/push** | **МЁРТВ** | `FCM_CREDENTIALS_PATH` missing → `enabled=False` → `send_to_user` логирует «FCM STUB» и **возвращает True** (ложный успех); device_tokens 0/12 → даже при enabled токенов нет | fcm_service.send_to_user (if not enabled: stub return True); device_tokens 0 |
| **Telegram** | **МЁРТВ** | `TELEGRAM_ENABLED=False`/BOT_TOKEN пуст → `telegram_service.is_available()=False` → skip; telegram_id 0/12 | alert_service.send_telegram_alert (is_available → return); settings |
| **Email** | **ЧАСТИЧНО жив, большинство отказов** | настроен (mail.ru, credentials), но 13/21 failed: 10× SMTP 550 «invalid headers», 3× 535 «нужен пароль приложения mail.ru». 8 sent. Вызывающий код (alert_service) глотает исключение → пользователь ничего не видит | email_logs status/error_message; email_service.send_email (SMTP login/send, raise→EmailLog failed) |
| **WebSocket / in_app журнал** | **РАБОТАЕТ** (для валидного user_id) | `create_notification` commit-ит Notification + `broadcast_to_company`; real-time только при подключённом WS; журнал виден при загрузке. Ломается точечно: salary-dispatcher без await; bulk-response получатель phantom | notification_service.create_notification (db.commit + broadcast); notifications 15 записей user_id 1/2 |

**Шаблоны:** таблица `notification_templates` пуста (0), НО `render_template` имеет **fallback на DEFAULT_TEMPLATES** для кодов `role_change/overdue_acts/act_signed/act_rejected` (max/email/fcm). Поэтому для этих 4 кодов шаблон НЕ None (берётся default). Для прочих кодов (нет в DEFAULT_TEMPLATES) → None. Утверждение «пустая таблица → render_template всегда None» **частично неверно** — для 4 дефолтных кодов fallback работает.

---

## 3. Событие → канал → где обрыв → что увидит пользователь → доказательство

### ПОДТВЕРЖДЕНО

| Событие | Канал(ы) в коде | Где обрыв | Пользователь видит | Доказательство (file:line) |
|---|---|---|---|---|
| **Смена роли** | email + MAX | email: `from app.services.email_service import send_email` — **module-level send_email НЕ существует** (hasattr=False) → ImportError → `except: pass`. MAX: notify_user → max_chat_id=0 → skipped | **ничего** | admin.py:150-153 (import send_email), :163-176 (MAX); email_service module has no send_email; users max_chat_id 0 |
| **Просроченные акты** | FCM + MAX | FCM send_to_user → stub True (ничего). MAX notify_user → max_chat_id=0 → skipped. email/in_app НЕ используются | **ничего** (job логирует «Overdue alert sent») | scheduler.py:580 (fcm), :598 (max); fcm stub; users 0 |
| **Акт подписан/отклонён** | FCM | FCM send_to_user → stub True (ничего). email/MAX/in_app НЕ используются | **ничего** | scheduler.py:463 (fcm send_to_user); fcm stub |
| **Приближение ТО** | (нет канала) | `_check_maintenance_due` только `logger.warning`/`info` + гейдж (business_metrics_refresh). Уведомлений НЕТ | **ничего** (только лог/гейдж) | scheduler.py:693-714 (log only), :956 (gauge) |
| **Зависшие выплаты** | (нет канала) | `_check_pending_payouts` только `logger.warning`. Уведомлений НЕТ | **ничего** | scheduler.py:722-757 (log only) |
| **Расчётный листок (зарплата)** | in_app + email | in_app: `create_notification(...)` **БЕЗ await** (async) → coroutine не выполняется → журнал НЕ пишется, но лог «Internal notification sent» и results.internal=True. email: `send_email(to=…)` — параметр `to_email`, не `to` → TypeError → except | **ничего** (ложный лог успеха) | salary_notification_dispatcher.py:94 (create_notification без await), :113 (send_email to=); email_service.send_email sig to_email |
| **Простой техники** | email + telegram + FCM | email: send_alert_email → SMTP 550/535 отказы (email_logs), исключение проглочено. telegram: is_available False → skip. FCM: stub. in_app НЕ создаётся | **ничего** | alert_service.py:43/45/139; email_logs 550/535; send_telegram_alert stub |
| **Конфликт смен** | email + telegram + FCM | то же: email SMTP отказы, telegram skip, FCM stub; in_app нет | **ничего** | alert_service.py:75/76 |
| **Аномалии топлива** | email + telegram | email SMTP отказы, telegram skip | **ничего** | scheduler.py:313/314 |
| **Ответ на заявку (bulk approve/reject)** | in_app | `create_notification(user_id=assignment.assigned_by)` — `assigned_by` **phantom** (RequestAssignment без колонки) → AttributeError → `except: pass` → уведомление НЕ создано | **ничего** | request_service.py:654/671 (bulk_response_action); RequestAssignment mapper без assigned_by; notifications user_id null=0 (не создались) |
| **MAX-уведомления диспетчерам** (заявки/геозоны/выплаты) | MAX | notify_company_dispatchers → UserCompany (7) → notify_user → max_chat_id=0 → skipped у всех | **ничего** | request_service.py:573, geofence.py:141, salaries.py:322, payments_service.py:317; notify_user skip |

### ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ

| Событие | Канал | Что проверить | Почему неоднозначно |
|---|---|---|---|
| **Акт подписан/отклонён — детекция** | Diadoc polling | act_status_check опрашивает статусы Diadoc; компании без ключей (companies.diadoc_api_key 0/4) → stub. Меняется ли статус вообще без ключей? | Если статусы не детектятся, ветка уведомления не достигается (обрыв ещё раньше FCM) |
| **Назначение смены** | in_app | shift_task_service.py:115 create_notification — валидность получателя (user_id) | Журнал содержит записи (user_id 1/2), но конкретный получатель назначения не сверен |
| **Ответ на заявку (не bulk)** | in_app | request_service.py:81/214/553/772/824/1150/1179/1234 create_notification — получатели (client_id/operator) | Часть уведомлений создаётся (журнал 15), но не все получатели сверены; возможны phantom-получатели |
| **Email 550 «invalid headers»** | email | Какой именно заголовок отвергает mail.ru (10 отказов) | Причина 550 не локализована (From/Subject/Date кодировка); 8 писем всё же sent |
| **Dispute/escalation/rental/payout** | email+telegram+max+in_app | notification_dispatcher: email (файловые шаблоны) может уходить (8 sent), telegram/max мертвы, in_app при user_id | Смешанный результат: email частично жив, остальные каналы мертвы; итог по событию зависит от email-доставки |

---

## 4. Планировщик: регулярные рассылки — запускаются, но вхолостую

Задачи запускаются (подтверждено прогоном на копии, SCHEDULER_JOB_AUDIT), НЕ выходят вхолостую на первом шаге (кроме monthly_auto_acts с day-guard), но **уведомления не доставляются**:
- `daily_alert_check` (простой/конфликт): email SMTP отказы + telegram/FCM мертвы → ничего.
- `daily_overdue_receivables`: FCM stub + MAX no chat_id → ничего (лог «sent»).
- `act_status_check`: FCM stub → ничего (+ детекция под вопросом без Diadoc-ключей).
- `daily_maintenance_due_check`: только лог/гейдж, уведомлений нет by design.
- `daily_pending_payouts_check`: только лог, уведомлений нет by design.
- `daily_company_report`, `weekly_digest`: email (weekly_digest ищет бухгалтера — role_in_system accountant/admin/manager/owner, в БД driver/operator → 0 recipients, PHANTOM_READS S1).

Итог: планировщик «работает» (логирует успех), но пользователь не получает ни push, ни MAX, ни telegram; email — частично (8/21), остальное SMTP-отказы.

---

## 5. Что проверено и РАБОТАЕТ (охват)
- **in_app журнал + WebSocket**: `create_notification` commit-ит Notification и шлёт `broadcast_to_company`; 15 записей (user_id 1/2, null 0), sent_at заполнен. Для валидного получателя in_app доходит (при подключённом WS — real-time, иначе при загрузке).
- **render_template fallback**: для role_change/overdue_acts/act_signed/act_rejected шаблон берётся из DEFAULT_TEMPLATES даже при пустой таблице (не None).
- **email настроен и частично доставляет**: 8 sent в email_logs; EmailLog пишется (pending→sent/failed) с commit.
- **should_notify**: default True (prefs uid=1 все True) — не блокирует отгрузку.

## 6. Сводка обрывов (ранг по последствию)
1. **Деньги/документы:** расчётный листок (create_notification без await + email to= TypeError) → сотрудник не получает листок; просроченные акты/выплаты → никто не уведомлён (FCM stub/MAX dead/log-only); акт подписан/отклонён → FCM stub.
2. **Безопасность/операции:** простой техники/конфликт смен/аномалии топлива → email SMTP отказы (550/535) + telegram/FCM мертвы → диспетчер ничего не видит.
3. **Смена роли:** email ImportError (send_email module-level нет) + MAX dead → пользователь не узнаёт о смене роли.
4. **Глобально мертвые каналы:** MAX (0 chat_id + disabled), FCM (0 токенов + stub True), Telegram (0 telegram_id + disabled) — любое событие через них не доходит.
5. **Email-инфраструктура:** mail.ru требует пароль приложения (535) и отвергает заголовки (550) → 13/21 отказов; нужно исправить SMTP-аутентификацию/заголовки.

Все находки — отчёт; исправление решает пользователь. Ничего не правилось; БД только читалась; реальной отправки не было.
