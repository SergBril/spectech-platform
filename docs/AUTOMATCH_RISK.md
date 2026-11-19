# AUTOMATCH_RISK — риск автосопоставления платежей (bank.auto_match_payments)

Дата: 2026-11-19. Режим: только расследование; рабочая БД **только чтение** (SELECT); правки кода/конфигов/тестов, запись в БД, внешняя отправка и публикация обработчиков запрещены и не выполнялись. `shifts/tasks.py`, `schemas/shift.py`, тест календаря не тронуты.

Объект: `backend/app/api/routes/shifts/bank.py:63 auto_match_payments` (не опубликован, без декоратора).

## Вердикт (кратко)
**Риск ПОДТВЕРЖДЁН структурно, но на ТЕКУЩИХ данных латентный (0 совпадений).** `purpose_match` мёртв (всегда truthy) → сопоставление идёт **только по сумме ±1%**, ИНН и назначение игнорируются; нет защиты от исходящих и от повторной привязки. Однако на текущих данных **ни одна транзакция не имеет ни одного кандидата** (суммы не пересекаются) → сейчас авто-разноска не сделает ничего. «Тихо неверные деньги» проявятся, когда суммы совпадут (особенно при нескольких кандидатах с одинаковой суммой — такие есть). Это уточняет прежнюю находку PUBLICATION_READINESS: дефект реален, немедленное воздействие на текущих данных = 0.

---

## 1. Разбор purpose_match по шагам (bank.py:113-125)

Код:
```python
purpose_match = False
if (payment.purpose and getattr(act, "document_number", None) or f"ACT-{act.id}"):
    purpose_match = getattr(act, "document_number", None) or \
        f"ACT-{act.id}".replace("-", "") in payment.purpose.replace("-", "").replace(" ", "")
```

Шаги:
1. Условие `if`: `(payment.purpose and act.document_number) or f"ACT-{act.id}"`. Правый операнд `f"ACT-{act.id}"` — непустая строка, **всегда truthy**. `X or "ACT-{id}"` всегда truthy → тело `if` выполняется для ЛЮБОЙ пары (платёж, акт), даже если `payment.purpose is None`.
2. Тело: `purpose_match = act.document_number or (… in payment.purpose.…)`. `Act.document_number` — **NOT NULL** (интроспекция mapper), всегда непустая строка → truthy. Оператор `or` коротко замыкается: `purpose_match = act.document_number` (строка), а проверка `in payment.purpose` **никогда не вычисляется** (поэтому и нет AttributeError при purpose=None).
3. Итог: `purpose_match` = строка номера акта, **truthy для любой пары**, независимо от содержания назначения (нет назначения / чужой номер — всё равно truthy).

Доказательство на РЕАЛЬНЫХ значениях (назначения содержат номера СЧЕТОВ, не актов; exact-выражение кода):
```
tx#61 purpose='Частичная оплата по счету № 26 …' | act#8 doc='ACT-2026-0005' => purpose_match='ACT-2026-0005' truthy=True
tx#61 purpose='…по счету № 26…'                  | act#9 doc='ACT-2026-0006' => purpose_match='ACT-2026-0006' truthy=True
tx#63 purpose='Оплата по счету № 326 …'          | act#8 doc='ACT-2026-0005' => purpose_match='ACT-2026-0005' truthy=True
tx#64 purpose='Оплата по счету № 656 …'          | act#9 doc='ACT-2026-0006' => purpose_match='ACT-2026-0006' truthy=True
```
Назначение ссылается на счёт №26/326/656 (чужой номер, не акт), но purpose_match = номер акта (truthy). Synthetic `purpose=None`: `if-cond=True, purpose_match='ACT-2026-0005', truthy=True` (в БД все 48 tx имеют purpose, поэтому None-случай показан синтетически; логика от этого не меняется).

Следствие для условия привязки `if amount_match and (inn_match or purpose_match or not act.counterparty_inn)`:
- `purpose_match` всегда truthy → скобка всегда True → условие сводится к **`amount_match`** = `abs(payment.amount - remaining) < max(remaining*0.01, 1)` (±1%,_floor 1 ₽).
- ИНН и назначение НЕ влияют. `best_act` = первый акт в порядке выборки, попавший в ±1% → **произвольный выбор** при нескольких кандидатах.

---

## 2. Масштаб на реальных данных (SQL, read-only)

Запрос (кандидаты по сумме ±1%, та же компания, КАК В КОДЕ — без фильтра direction):
```sql
WITH tx AS (SELECT id, company_id, amount, direction FROM bank_transactions
            WHERE match_status='unmatched' AND matched_invoice_id IS NULL),
acts AS (SELECT id, company_id, total_amount - COALESCE(paid_amount,0) AS remaining FROM acts
         WHERE status IN ('draft','sent_to_edo','signed') AND COALESCE(paid_amount,0) < total_amount)
SELECT tx.id, tx.direction, COUNT(acts.id) AS candidates
FROM tx LEFT JOIN acts ON acts.company_id=tx.company_id
  AND ABS(tx.amount - acts.remaining) < GREATEST(acts.remaining*0.01, 1)
GROUP BY tx.id, tx.direction ORDER BY candidates DESC, tx.id;
```
Результат: **TOTAL_UNMATCHED_TX=30 (incoming 4 + outgoing 26), multi_candidate=0, single=0, zero=30.**
→ На текущих данных **0 транзакций с >1 кандидатом и вообще 0 кандидатов**: ни одна сумма не попадает в ±1% ни одного неоплаченного акта. Число случаев произвольного выбора СЕЙЧАС = **0**.

Почему 0 (фактические суммы):
- Остатки неоплаченных актов (13 шт): 62900.00 (акты 8,9,10,14,16 — **5 одинаковых**), 62900.01 (11,17), 62900.02 (15,18), 40000.01 (12,19), 40000.02 (13), 122000.00 (20).
- Суммы неразнесённых входящих tx: 70700 (tx72), 16000 (tx80), 26000 (tx81), 16000 (tx83). Ни одна не в диапазонах ±1% актов (62900±629, 40000±400, 122000±1220).

**Латентный произвол:** 5 актов имеют идентичный остаток 62900.00. Если поступит платёж ~62900, кандидатов будет **5** → выбор первого по порядку выборки произволен. То есть риск произвольного выбора структурно присутствует (одинаковые суммы актов), просто текущие платежи не совпадают.

---

## 3. Что происходит при привязке и защиты (bank.py:131-143, чтение кода)

При `best_act`:
```python
payment.matched_act_id = best_act.id
best_act.paid_amount = (best_act.paid_amount or 0) + payment.amount
best_act.payment_status = "paid" if best_act.paid_amount >= best_act.total_amount else "partial"
```
- **Защита от повторной привязки: НЕТ.** Выборка платежей фильтрует `matched_invoice_id IS NULL AND match_status='unmatched'`. Привязка пишет `matched_act_id` (НЕ `matched_invoice_id`) и **НЕ обновляет `match_status`** (остаётся 'unmatched'). → привязанный платёж снова попадает в выборку при следующем запуске → повторная привязка / двойное увеличение `paid_amount`. Фильтр смотрит не на то поле (`matched_invoice_id` вместо `matched_act_id`).
- **Защита от исходящих: НЕТ.** В выборке нет `direction == 'incoming'` (docstring говорит «incoming», но запрос не фильтрует). 26 из 30 неразнесённых — **outgoing**; код попытался бы разносить исходящие платежи как оплаты актов (неверно). Сейчас спасает только 0 кандидатов.
- **Переплата:** `paid_amount += amount` без ограничения сверху → может превысить `total_amount`; статус 'paid' при `>= total`. Переплата не обрабатывается.
- Факт: `bank_transactions.matched_act_id` сейчас 0/48 (авто-разноска не запускалась) — повторных привязок в данных нет, риск доказан логикой кода.

---

## 4. Предлагаемое правило сопоставления (обоснование)

Обязательные условия (все должны выполняться):
1. **Направление:** только `direction == 'incoming'` (исходящие — не оплаты актов). Поле есть: `BankTransaction.direction` (String; DB: incoming 22 / outgoing 26).
2. **ИНН плательщика:** `tx.counterparty_inn == act.counterparty_inn` (строгое равенство, не «еслиavailable»). Поля есть: `BankTransaction.counterparty_inn` (заполнен у tx), `Act.counterparty_inn` (nullable). **Пробел данных: `acts.counterparty_inn` 0/19 заполнен** → ИНН-матчинг на текущих данных невозможен; нужно заполнить ИНН контрагента в актах (из client/contractor). Без ИНН — не разносить автоматически.
3. **Номер документа в назначении:** `act.document_number` должен встречаться в `tx.purpose` (нормализованное вхождение). Поля есть: `tx.purpose` (48/48 заполнен), `act.document_number`. **Нюанс:** текущие назначения ссылаются на номера СЧЕТОВ («по счету № N»), не актов → назначение матчит счёт, а не акт. Естественная сущность для разноски по назначению — **Invoice** (это делает `BankMatchingService.match_transaction`: document_number/amount+ИНН → invoice/payout). Разноска напрямую в акт по назначению требует, чтобы назначение содержало номер акта, либо связи акт↔счёт.
4. **Сумма:** точное равенство `tx.amount == remaining` как основной критерий; допуск ±1% (или фикс. ±1 ₽) — только как вторичный и ТОЛЬКО при совпадении ИНН+номера. Одна сумма без ИНН/номера — не основание.
5. **Несколько кандидатов:** НЕ выбирать первого. При >1 кандидата — `match_status='needs_review'` (ручной разбор), не авто-привязка. Поле `match_status` есть (String; значения unmatched/auto_matched/manual_matched).
6. **Идемпотентность:** при привязке обновлять `match_status='auto_matched'` И `matched_act_id`, а выборку фильтровать по `matched_act_id IS NULL AND match_status='unmatched'` (не по matched_invoice_id). Защита от повторной привязки.
7. **Переплата:** `paid_amount = min(total_amount, paid_amount + amount)`; остаток/переплату фиксировать отдельно.

Данные в модели: есть `tx.counterparty_inn/purpose/document_number/amount/direction/match_status/matched_act_id/matched_invoice_id`, `act.counterparty_inn/document_number/total_amount/paid_amount/payment_status/client_id`. **Нет/не заполнено:** `act.counterparty_inn` (0/19), назначение содержит номера счетов а не актов; отдельного поля «назначение разобрано/номер извлечён» нет.

---

## Доказательства (запросы/интроспекция)
- Разбор выражения: exact-код bank.py:113-125 + реальные purpose/document_number (SELECT bank_transactions/acts) + synthetic purpose=None.
- Масштаб: CTE-запрос выше (30 tx, 0 кандидатов); остатки актов и суммы incoming tx — SELECT (приведены).
- Защиты: чтение bank.py:71-79 (выборка без direction, по matched_invoice_id) и :131-143 (привязка без обновления match_status).
- Доступность полей: `acts.counterparty_inn` 0/19; `tx.purpose` 48/48; `tx.direction` incoming 22/outgoing 26; `tx.matched_act_id` 0/48; интроспекция mapper BankTransaction/Act (document_number NOT NULL).

## Итог
- Дефект логики реален: purpose_match мёртв → разноска только по сумме ±1% (произвольный выбор), нет защиты от исходящих и повторной привязки, переплата не ограничена.
- На текущих данных воздействие = 0 (0 кандидатов): риск латентный. Произвол проявится при совпадении сумм (5 актов с остатком 62900 → 5 кандидатов на платёж 62900) и при повторных запусках (двойной учёт).
- Публиковать auto_match_payments в текущем виде нельзя; сначала правило из §4 (ИНН+номер+направление+идемпотентность+ручной разбор при нескольких кандидатах) и заполнение acts.counterparty_inn.

Все находки — отчёт; починку и публикацию выполняет пользователь. Ничего не правилось; БД только читалась.
