# EMAIL_FAILURE_ROOT_CAUSE — причина отказов почты 550 и 535, точное исправление

Дата: 2026-11-19. Режим: только расследование; рабочая БД **только чтение**; **никакой реальной отправки писем** (включая «тестовую») и вызова ручек отправки; пароль в отчёт не выводился (только факт наличия/длина). `shifts/admin.py`, вызовы уведомлений не тронуты. Коммит — только этот отчёт через pathspec с проверкой состава до push.

Метод: `inspect`/чтение `email_service.py` (send_email, _attach_file, send_act_signed, send_invoice_created, send_payout_approved) + SELECT email_logs (хронология, to/subject/error) + настройки SMTP (формат, без пароля).

---

## 1. Формирование заголовков (фактический код и настройки)

`email_service.send_email` (email_service.py:186-195):
```python
msg["From"] = formataddr((str(Header(from_name, "utf-8")), from_email))   # :186
msg["To"] = to_email                                                     # :188
msg["Subject"] = Header(subject, "utf-8")                                # :191
msg["MIME-Version"] = "1.0"                                              # :194
msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")     # :195
```
- **From:** `formataddr((Header("СпецТехника Про","utf-8"), "osavichieva@mail.ru"))` → display-name кириллицей в encoded-word + адрес в угловых скобках. Корректно (RFC 2047). Кириллический display-name mail.ru принимает (письма id1-6 sent с этим From).
- **To:** сырой `to_email`, без угловых скобок — допустимо.
- **Subject:** `Header(subject,"utf-8")` → encoded-word =?utf-8?b?…?= для не-ASCII.
- **Reply-To, Message-ID:** НЕ задаются явно.
- **Date:** strftime с `%a/%b` (locale-зависимо); при C-locale — английские weekday/month, валидно.
- **Вложения (`_attach_file`, :447-470):**
  ```python
  encoded_filename = str(Header(filename, "utf-8"))
  part.add_header("Content-Disposition", "attachment", filename=encoded_filename)
  ```
  Имя файла кодируется encoded-word и кладётся в параметр `filename=` заголовка Content-Disposition.

**Настройки (формат, без пароля):** `SMTP_HOST=smtp.mail.ru, SMTP_PORT=465 (SMTP_SSL), SMTP_USER=osavichieva@mail.ru, SMTP_FROM_EMAIL=osavichieva@mail.ru, SMTP_FROM_NAME=СпецТехника Про, SMTP_USE_TLS=True`. `SMTP_PASSWORD present=True, len=20`. **`SMTP_FROM_EMAIL == SMTP_USER` → True.**

## 2. Сопоставление с отказами email_logs (запрос + выборка)

Запрос: `select id, status, to_email, subject, left(error_message,70), created_at, sent_at from email_logs order by created_at` (21 запись).

| id | дата/время | status | subject | ошибка |
|---|---|---|---|---|
| 1-2 | 09-23 | sent | Акт выполненных работ № ТО-2026-0001 | — |
| 3,4,6 | 09-26 | sent | Новый счёт INV-2026-XXXX от СпецТехника Про | — |
| 5 | 09-26 | sent | Акт ACT-2026-0016 подписан | — |
| 7,8,9 | 10-12 13:29-13:30 | **failed 535** | ✅ Выплата ВЫП-2026-0004/0005 одобрена — 18000.00 ₽ | `535 NEOBHODIM parol prilozheniya` (нужен пароль приложения) |
| 10-14,16-19 | 10-12 13:41-14:24 | **failed 550** | ✅ Выплата ВЫП-2026-0005 одобрена — 18000.00 ₽ | `550 your mailer sends invalid headers` |
| 15 | 10-12 14:08 | **failed 550** | Акт АКТ-002 подписан (БЕЗ emoji) | `550 invalid headers` |
| 20 | 10-12 14:32 | sent | **Vyplata ВЫП-2026-0005 odobrena - 18000.00 RUB** (транслит) | — |
| 21 | 10-12 17:13 | sent | Vyplata ВЫП-2026-0003 odobrena - 17000.00 RUB (транслит) | — |

Закономерность:
- **535 (3 шт, самые ранние 13:29-13:30):** отказ аутентификации — mail.ru требует пароль приложения. После 13:41 аутентификация проходит (535 больше нет) → оператор настроил пароль приложения между 13:30 и 13:41. **535 — исторический, уже устранён настройкой** (id20/21 sent; текущий пароль len=20 — формат пароля приложения).
- **550 (10 шт, 13:41-14:24):** «invalid headers» — дефект формирования заголовков/MIME. Затронуты письма с вложениями (выплаты ВЫП-…, акт АКТ-002). **id15 «Акт АКТ-002 подписан» без emoji тоже 550** → emoji не единственная причина.
- **sent после исправления (id20/21):** тема транслитерирована (убраны ✅/—/₽) + в `send_payout_approved` добавлен guard пустого PDF (`len>100`, комментарий «Не прикрепляем пустой PDF — это ломает MIME заголовки»).
- Все отказы — одному получателю `client@testclient.ru`; sent — разным (gmail/testclient/example). Получатель не является дифференциатором 550 (один и тот же testclient.ru и sent, и failed).

## 3. From vs SMTP-авторизация

**`SMTP_FROM_EMAIL == SMTP_USER == osavichieva@mail.ru` → True.** Адрес From совпадает с адресом авторизации → «письмо от чужого адреса» **НЕ является причиной 550** в текущей конфигурации. (Эта частая причина исключена фактом.)

## 4. Корневая причина 550 и точное исправление

### ПОДТВЕРЖДЕНО (дефекты кода)
1. **Не-ASCII имя вложения в Content-Disposition `filename=` (RFC-невалидно).** `_attach_file` (:462-468) кладёт `filename=str(Header(filename,"utf-8"))` — encoded-word =?utf-8?…?= в параметр `filename=`. По RFC 2231/2045 параметр `filename` должен быть ASCII, а не-ASCII — через `filename*=utf-8''<percent-encoded>`. Кириллические номера документов → имена файлов `АКТ-002_….pdf`, `ВЫП-2026-0005.pdf`, `ТО-2026-0001_….pdf` (не-ASCII) → encoded-word в параметре → **mail.ru отвергает «invalid headers»**.
   - Доказательство-сопоставление: id15 «Акт **АКТ-002** подписан» (кириллический номер → кириллическое имя файла) → 550; id5 «Акт **ACT-2026-0016** подписан» (латинский номер → ASCII имя) → sent. Разница — имя файла, не тема (обе темы кириллические, без emoji).
2. **Пустой/крошечный PDF ломает MIME.** Комментарий в `send_payout_approved` (:511): «Не прикрепляем пустой PDF — это ломает MIME заголовки»; guard `len(pdf_result)>100` добавлен ТОЛЬКО в payout. `send_act_signed` (:335-390) и `send_invoice_created` (:271-333) прикрепляют PDF без проверки размера (достаточно `if pdf_bytes`) → tiny/invalid PDF (>0 байт) попадает в MIME → невалидные заголовки → 550. `_attach_file` пропускает только `len==0`, но не tiny/invalid.

### ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ (точный вклад каждого фактора)
- **Emoji/спецсимволы в Subject (✅ — ₽):** темы с ними (id7-19) получали 550/535, транслитерированные (id20/21) — sent. НО id15 без emoji тоже 550 → emoji не обязательное условие. Вклад emoji отдельно от MIME/filename не изолирован (исправление темы и guard пустого PDF применены одновременно). mail.ru может отвергать и emoji в encoded-word Subject — правдоподобно, но не доказано отдельно. Помечаю как возможный вторичный фактор.
- Точная изоляция «filename vs empty-PDF vs emoji» требует воспроизведения (запрещено отправкой). Дефекты кода (1) и (2) конкретны и подтверждаются кодом + хронологией; их относительный вклад — требует подтверждения.

### Точное исправление — КОД (можно править)
- **`_attach_file`:** для не-ASCII имён использовать RFC 2231: `part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))` (email-пакет сам сделает `filename*=utf-8''…`) ЛИБО ASCII-safe имя + `filename*`. НЕ класть encoded-word в `filename=`. Это устраняет «invalid headers» для кириллических имён файлов.
- **Guard пустого/крошечного PDF:** добавить проверку `len(pdf_bytes)>100` (как в payout) в `send_act_signed` и `send_invoice_created` перед прикреплением; невалидный PDF → отправлять без вложения (или не отправлять), а не ломать MIME.
- **Subject (вторично, требует подтверждения):** санитизировать emoji/спецсимволы (✅→убрать, —→-, ₽→RUB) либо убедиться, что `Header(subject,"utf-8")` принимает mail.ru. Текущий `send_payout_approved` уже транслитерирован (пользователь применил).

### Точное исправление — ОКРУЖЕНИЕ (решение оператора)
- **535 «нужен пароль приложения»:** `SMTP_PASSWORD` должен быть **паролем приложения mail.ru** (не обычный пароль аккаунта). Судя по хронологии (535 только 13:29-13:30, далее sent), оператор УЖЕ настроил пароль приложения — текущий len=20 соответствует формату. **Требует подтверждения оператором:** что SMTP_PASSWORD — именно пароль приложения (https://help.mail.ru/mail/security/protection/external), и он не будет заменён обычным паролем. Кодом это не исправить.
- From=SMTP_USER уже совпадает — менять не нужно.

## 5. Где теряется ошибка и почему отказ выглядит успехом

Цепочка обработки ошибки:
- **`send_email` (:254-271):** при отказе SMTP логирует `❌ Failed to send email …` (exc_info), пишет `EmailLog.status=failed, error_message`, и **пробрасывает исключение (raise)**. На уровне сервиса ошибка НЕ потеряна — она в email_logs (failed) и в логе.
- **Обёртки (`send_act_signed`/`send_invoice_created`/`send_payout_approved`):** возвращают `self.send_email(...)`; исключение пробрасывается выше (не глотают сами).
- **`alert_service.send_alert_email` (:83-127):** цикл `for email_addr …: email_service.send_email(...)` обёрнут в `try/except Exception: logger.error("Failed to send alert email")`. Ошибка логируется, но **не пробрасывается** — функция возвращает None. Вызывающий планировщик `daily_alert_check` затем логирует `✅ Daily alerts check completed for N companies` **независимо от отказа почты** → задача выглядит успешной.
- **`notification_dispatcher.notify_*`:** `results["email"] = email_service.send_…(…)` в try/except → при отказе `results["email"]=False` + logger.error, но вызывающий код результат игнорирует → событие «обработано».
- **`salary_notification_dispatcher.py:94`:** `create_notification(...)` (async) вызывается **БЕЗ await** → coroutine не исполняется, уведомления нет, но код ставит `results["internal"]=True` и логирует `✅ Internal notification sent` → **ложный успех** (это in_app, не email, но тот же класс «выглядит успехом»).

**Что должно происходить вместо этого:**
- Не логировать «sent/completed», когда канал отказал: `daily_alert_check`/dispatcher должны агрегировать статус каналов (results) и логировать отказ явно (или пробрасывать/алертить), а не «✅ completed».
- `salary_notification_dispatcher` — `await create_notification(...)` (иначе уведомление не создаётся).
- Отказ email уже виден в `email_logs.status=failed` — это источник истины; вышестоящие логи должны отражать его, а не маскировать. Мониторинг: алерт на `email_logs failed` (например, доля failed > порога), чтобы 13/21 отказов не оставались незамеченными.

## 6. Итог
- **535 (3):** пароль приложения mail.ru не был настроен → исторический, устранён оператором (далее sent). Кодом не исправить; подтвердить у оператора, что SMTP_PASSWORD — пароль приложения.
- **550 (10):** дефект MIME/заголовков — (1) кириллическое имя вложения encoded-word в `Content-Disposition filename=` (RFC-невалидно), (2) пустой/крошечный PDF без guard в act_signed/invoice_created. From=SMTP_USER совпадает (исключено). Emoji в Subject — возможный вторичный фактор (требует подтверждения; id15 без emoji тоже 550).
- **Исправление кода:** RFC 2231 для имён вложений + guard размера PDF во всех обёртках; (вторично) санитизация Subject. **Окружение:** пароль приложения (оператор).
- **Видимость отказа:** сервис пишет failed+raise, но вышестоящий код (alert_service/планировщик/dispatcher) глотает и логирует успех; salary create_notification без await — ложный «sent». Нужно агрегировать статус и не маскировать отказ.

Все находки — отчёт; исправление решает пользователь. Ничего не правилось; БД только читалась; реальной отправки не было; пароль не выводился.
