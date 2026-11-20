# FRONTEND_RENAME_PLAN — точный план переименований с проверкой формы запроса/ответа

Дата: 2026-11-19. Режим: только расследование; правки кода/конфигов/тестов запрещены; рабочая БД не изменялась; внешняя отправка не выполнялась. `shifts/admin.py`, `notification_template_service.py` не тронуты. Коммит — только этот отчёт через pathspec с проверкой состава до push.

Метод: канонические маршруты из `app.routes` в процессе + `inspect.signature`/`inspect.getsource` обработчиков и сервисов (форма возврата); строки фронтенда — grep + чтение компонентов (поля `res.data`). Для каждого пункта сверены путь, метод, имена query/Body-полей, обязательность, скаляр/объект, и поля ответа против читаемых UI.

## Сводная таблица

| # | Фронтенд (file:line) | Было | Стало (канон) | Запрос | Ответ | Вердикт |
|---|---|---|---|---|---|---|
| 1 | PnLPerVehiclePage.tsx:13,27 | GET /shifts/stats/pnl-per-vehicle (+/export) | GET /shifts/stats/pnl (+/pnl/export) | ✓ date_from/date_to | поля ✓, но hours=0 (phantom) | **переименовать + правка бэкенда** |
| 2 | CostPerHourPage.tsx:25 | GET /shifts/cost-rates | GET /shifts/stats/cost-rates | ✓ | ✓ | **достаточно переименовать** |
| 2 | CostPerHourPage.tsx:31 | PUT /shifts/cost-rates | PATCH /shifts/stats/cost-rates | ✓ Body-объект | не читается | **переименовать путь+метод** |
| 2 | OnboardingWizardPage.tsx:20 | PUT /shifts/cost-rates | PATCH /shifts/stats/cost-rates | ✓ Body-объект | не читается | **переименовать путь+метод** |
| 3 | DispatcherDashboard.tsx:19 | POST /shifts/alerts/check-idle | GET /shifts/alerts/idle-vehicles | ✓ (без тела) | ✓ notified/message | **переименовать путь+метод** |
| 3 | DispatcherDashboard.tsx:26 | POST /shifts/alerts/check-conflicts | GET /shifts/alerts/conflicts | ✓ (без тела) | ✓ notified/message | **переименовать путь+метод** |
| 4 | RequestDetailPage.tsx:273 | POST /requests/bulk-responses | POST /requests/responses/bulk-action | ✓ Body embed | ✓ processed | **переименовать** (бэкенд-дефекты side-effect) |
| 5 | UserRolesPage.tsx:31 | PUT /shifts/users/bulk-role | POST /shifts/users/bulk-role | ✓ Body {user_ids,role} | ✓ updated | **переименовать метод** |
| 6 | DriverAppPage.tsx:46 | POST /drivers/shifts/{id}/start | POST /driver/shifts/{id}/start | ✓ (Form optional) | не читается | **переименовать путь** (показания не шлются) |
| 7 | finance.ts:540 | POST /acts/{id}/verify-signature | GET /shifts/acts/{id}/verify-signature | ✓ | ✗ xml_size/sig_size vs provider/signed_at | **переименовать + правка формы ответа** |

---

## 1. PnLPerVehiclePage — переименовать + правка бэкенда (hours всегда 0)

**Фронтенд:**
- `PnLPerVehiclePage.tsx:13`: `apiClient.get('/shifts/stats/pnl-per-vehicle', { params: { date_from: dateFrom, date_to: dateTo } })`
- `PnLPerVehiclePage.tsx:27`: `window.open('/api/v1/shifts/stats/pnl-per-vehicle/export?date_from=…&date_to=…')`
- Читает: `data.vehicles[].{vehicle_id, vehicle_name, hours, revenue, fuel_cost, wage_cost, amortization_cost, margin, margin_pct}`.

**Канон:** `GET /api/v1/shifts/stats/pnl` → `app.api.routes.shifts.stats.get_pnl_per_vehicle(date_from: str = Query(...), date_to: str = Query(...), db, current_user, company_id)`. Export: `GET /api/v1/shifts/stats/pnl/export` → `export_pnl_excel(date_from: str = Query(...), date_to: str = Query(...))` (stats.py:216-230).

**Запрос:** date_from/date_to ОБЯЗАТЕЛЬНЫЕ Query; фронтенд шлёт оба ✓. Сервис `shift_stats_service.get_pnl_per_vehicle` ФИЛЬТРУЕТ по дате: `ShiftTask.shift_date >= d_from <= d_to`, `Act.act_date >= d_from <= d_to`, fuel через task.shift_date. → date-фильтр применяется (в отличие от бага календаря). ✓

**Ответ:** сервис возвращает `{period:{from,to}, vehicles:[{vehicle_id, vehicle_name, hours, fuel_liters, revenue, fuel_cost, wage_cost, amortization_cost, total_expenses, margin, margin_pct}]}`. Все поля, читаемые UI, присутствуют ✓.
**НО дефект бэкенда:** `hours` вычисляется как `(getattr(t,"planned_end",None) - getattr(t,"planned_start",None)).total_seconds()/3600` с фильтром `if getattr(t,"planned_start") and getattr(t,"planned_end")`. У `ShiftTask` НЕТ planned_start/planned_end (mapper; есть на RequestAssignment) → getattr всегда None → фильтр отсекает ВСЕ смены → **hours=0 у всех машин** → wage_cost=0, amortization_cost=0, margin завышена. Тот же phantom-класс, что PHANTOM_READS P5.

**Вердикт:** переименовать `/shifts/stats/pnl-per-vehicle`→`/shifts/stats/pnl` и `/pnl-per-vehicle/export`→`/pnl/export` (запрос/поля ответа совпадают). **Нужна правка бэкенда:** источник hours — не phantom planned_start/end (например, фактическая длительность смены / moto_hours), иначе страница покажет нулевые часы/зарплату/амортизацию и завышенную маржу.

## 2. CostPerHourPage + OnboardingWizardPage — достаточно переименовать

**Фронтенд:**
- `CostPerHourPage.tsx:25`: `apiClient.get('/shifts/cost-rates').then(res => setRatesForm(res.data))`. ratesForm = `{fuel_price_per_liter, hourly_wage, amortization_per_hour}`.
- `CostPerHourPage.tsx:31`: `apiClient.put('/shifts/cost-rates', ratesForm)`.
- `OnboardingWizardPage.tsx:20`: `apiClient.put('/shifts/cost-rates', { fuel_price_per_liter: form.fuel_price, hourly_wage: form.hourly_wage, amortization_per_hour: form.amortization })`.

**Канон:**
- `GET /api/v1/shifts/stats/cost-rates` → `stats.get_cost_rates(db, current_user, company_id)` → `shift_stats_service.get_cost_rates` возвращает `{fuel_price_per_liter, hourly_wage, amortization_per_hour, updated_at?}` (или дефолты 65/500/300).
- `PATCH /api/v1/shifts/stats/cost-rates` → `stats.update_cost_rates(fuel_price_per_liter: float = Body(...), hourly_wage: float = Body(...), amortization_per_hour: float = Body(...), …)`.

**Запрос:** GET без параметров ✓. PATCH — несколько Body → объект `{fuel_price_per_liter, hourly_wage, amortization_per_hour}`; фронтенд шлёт ровно этот объект ✓ (имена совпадают). Метод PUT→PATCH.
**Ответ:** GET возвращает fuel_price_per_liter/hourly_wage/amortization_per_hour ↔ ratesForm ✓ (updated_at лишний, игнорируется). PATCH ответ не читается UI (alert). ✓

**Вердикт:** GET `/shifts/cost-rates`→`/shifts/stats/cost-rates`; PUT→PATCH `/shifts/cost-rates`→`/shifts/stats/cost-rates` (обе страницы). Запрос/ответ совпадают — **достаточно переименовать** (путь + метод). Основная страница CostPerHour грузится через `/shifts/stats/cost-per-hour` (уже зарегистрирован, не меняется).

## 3. DispatcherDashboard — переименовать путь+метод (GET)

**Фронтенд:**
- `DispatcherDashboard.tsx:19`: `apiClient.post('/shifts/alerts/check-idle')` → читает `res.data.notified`, `res.data.message`.
- `DispatcherDashboard.tsx:26`: `apiClient.post('/shifts/alerts/check-conflicts')` → `res.data.notified`, `res.data.message`.

**Канон:**
- `GET /api/v1/shifts/alerts/idle-vehicles` → `alerts.check_idle_vehicles(target_date: str | None = Body(default=None), …)` → `alert_service.check_and_notify_idle_vehicles` возвращает `{idle_count, notified, message?}` (message только при notified=True; при idle_count=0 → `{idle_count:0, notified:False}` без message).
- `GET /api/v1/shifts/alerts/conflicts` → `alerts.check_schedule_conflicts(target_date: str | None = Body(default=None), …)` → `{conflict_count, notified, message?}`.

**Запрос:** фронтенд шлёт POST без тела; канон GET с `target_date` Body optional → при отсутствии тела target_date=None → today ✓. Метод POST→GET. (GET с Body-параметром допустим, тело не обязательно.)
**Ответ:** UI `res.data.notified ? res.data.message : 'Нет…✅'` — при notified=True message есть ✓; при False читается fallback-строка, message не требуется ✓. Совпадает.

**Вердикт:** `POST /shifts/alerts/check-idle`→`GET /shifts/alerts/idle-vehicles`; `POST /shifts/alerts/check-conflicts`→`GET /shifts/alerts/conflicts`. **Достаточно переименовать** (путь+метод).
**Побочный эффект (не блокер переименования):** обработчики вызывают `send_alert_email`/`send_telegram_alert` → при клике уходят уведомления (email/telegram). Учитывать при тестировании.

## 4. RequestDetailPage — переименовать путь (бэкенд-дефекты side-effect)

**Фронтенд:** `RequestDetailPage.tsx:273`: `apiClient.post('/requests/bulk-responses', { assignment_ids: Array.from(selectedResponses), action, reason: action==='reject' ? 'Массовое отклонение' : '' })` → читает `res.data.processed`.

**Канон:** `POST /api/v1/requests/responses/bulk-action` → `requests.bulk_response_action(assignment_ids: list[int] = Body(..., embed=True), action: str = Body(..., embed=True), reason: str = Body(default="", embed=True), …)` → `RequestService.bulk_response_action` возвращает `{processed, errors, action}`.

**Запрос:** embed=True → объект `{assignment_ids, action, reason}`; фронтенд шлёт ровно его ✓. action approve/reject ✓ (сервис валидирует).
**Ответ:** `{processed, errors, action}` ↔ UI `res.data.processed` ✓.

**Вердикт:** `/requests/bulk-responses`→`/requests/responses/bulk-action`. Запрос/ответ совпадают — **достаточно переименовать** для самого вызова.
**Бэкенд-дефекты side-effect (уже PHANTOM_READS P4/P10, не блокер вызова):** при approve создаётся `ShiftTask(operator_id=getattr(vehicle,"current_driver_id",None))` → current_driver_id phantom (есть assigned_driver_id) → operator_id=None; уведомления используют `assignment.assigned_by` (phantom) → молча падают (try/except). Вызов вернёт processed, но смена без оператора и уведомления не уйдут. Нужна правка бэкенда отдельно.

## 5. UserRolesPage — переименовать метод PUT→POST

**Фронтенд:** `UserRolesPage.tsx:31`: `apiClient.put('/shifts/users/bulk-role', { user_ids: Array.from(selectedUsers), role: bulkRole })` → читает `res.data.updated`.

**Канон:** `POST /api/v1/shifts/users/bulk-role` → `admin.bulk_change_roles(user_ids: list[int] = Body(...), role: str = Body(...), db, current_user)` → возвращает `{updated, role}`. Валидирует `role` против `[r.value for r in Role]` (иначе 400).

**Запрос:** несколько Body → объект `{user_ids, role}`; фронтенд шлёт его ✓. Метод PUT→POST (путь тот же).
**Ответ:** `{updated, role}` ↔ UI `res.data.updated` ✓.

**Вердикт:** `PUT /shifts/users/bulk-role`→`POST /shifts/users/bulk-role`. **Достаточно переименовать метод.**
**Требует подтверждения:** значения `Role` enum должны совпадать со списком UI (admin/dispatcher/driver/accountant/viewer), иначе 400 «Invalid role». Проверить `Role` перед применением.

## 6. DriverAppPage — переименовать путь /drivers→/driver

**Фронтенд:** `DriverAppPage.tsx:46`: `apiClient.post('/drivers/shifts/${taskId}/start')` (без тела); ответ не читается (loadShifts()).

**Канон:** `POST /api/v1/driver/shifts/{task_id}/start` → `driver.start_shift(task_id: int, odometer_start: int | None = Form(default=None), moto_hours_start: float | None = Form(default=None), …)` → возвращает `{message, task_id}`. Роутер смонтирован на `/api/v1/driver` (main.py:319, ед.ч.).

**Запрос:** Form-поля optional; фронтенд шлёт без тела → odometer_start/moto_hours_start=None ✓ (старт без показаний допустим). Путь `/drivers/`→`/driver/`.
**Ответ:** `{message, task_id}` — UI не читает ✓.

**Вердикт:** `/drivers/shifts/{id}/start`→`/driver/shifts/{id}/start`. **Достаточно переименовать путь.**
**Функциональный пробел (не блокер переименования):** фронтенд НЕ передаёт odometer_start/moto_hours_start → показания счётчиков не собираются (остаются NULL), хотя обработчик для этого предназначен. Если нужны показания — добавить Form-поля в UI отдельно.

## 7. finance.ts verifyUpdSignature — переименовать + правка формы ответа

**Фронтенд:** `finance.ts:540`: `apiClient.post('/acts/${actId}/verify-signature')`; сигнатура функции `verifyUpdSignature(actId): Promise<{ valid: boolean; xml_size: number; sig_size: number }>`.

**Канон:** `GET /api/v1/shifts/acts/{act_id}/verify-signature` → `diadoc.verify_act_signature(act_id: int, db, current_user, company_id)` → возвращает `{valid, provider, signed_at}` (если подписан) или `{valid: False, message}` (если не подписан).

**Запрос:** path act_id, без тела; метод POST→GET, путь `/acts/{id}/verify-signature`→`/shifts/acts/{id}/verify-signature`. ✓
**Ответ: НЕСОВПАДЕНИЕ.** Фронтенд-тип ожидает `{valid, xml_size, sig_size}`; обработчик возвращает `{valid, provider, signed_at}` (или `{valid, message}`). `xml_size`/`sig_size` ОТСУТСТВУЮТ → undefined; `provider`/`signed_at` фронтенд-тип не ожидает. `valid` совпадает.

**Вердикт:** переименовать путь+метод. **Нужна правка формы ответа:** либо бэкенд возвращает xml_size/sig_size (как ожидает тип), либо фронтенд-тип/потребитель читает provider/signed_at/message.
**Требует подтверждения / латентно:** `verifyUpdSignature` сейчас НЕ вызывается ни одним .tsx-компонентом (grep по frontend/src пуст) → несовпадение не проявляется в UI, пока функцию не начнут использовать. При использовании — поправить форму ответа.

---

## Что проверено и совпадает (охват)
- Запрос совпадает у всех 8 вызовов после переименования (имена query/Body-полей, обязательность, объект vs скаляр): date_from/date_to (pnl), Body-объекты cost-rates/bulk-role/bulk-responses, Form optional start, GET без тела alerts.
- Ответ совпадает: cost-rates (fuel_price_per_liter/hourly_wage/amortization_per_hour), alerts (notified/message), bulk-responses (processed), bulk-role (updated), start (не читается).
- date-фильтр pnl реально применяется (сервис фильтрует shift_date/act_date) — бага «чужая неделя» как в календаре НЕТ.

## Требуют правки бэкенда (не переименованием)
1. **pnl hours=0** — phantom ShiftTask.planned_start/planned_end (источник часов неверен) → нулевые часы/зарплата/амортизация, завышенная маржа.
2. **verify-signature форма ответа** — xml_size/sig_size vs provider/signed_at (латентно, нет потребителя).
3. **bulk-responses side-effect** — operator_id из phantom current_driver_id→None; assigned_by phantom→уведомления молча падают (PHANTOM_READS P4/P10).
4. **Role enum** (bulk-role) — подтвердить совпадение значений со списком UI.

## Пробелы фронтенда (не блокер переименования)
- DriverAppPage start не передаёт показания счётчиков (odometer_start/moto_hours_start).
- verifyUpdSignature не имеет UI-потребителя.

Все находки — отчёт; переименования и правки выполняет пользователь. Ничего не правилось.
