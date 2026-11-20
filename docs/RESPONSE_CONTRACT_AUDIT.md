# RESPONSE_CONTRACT_AUDIT — поля, читаемые фронтендом, но не возвращаемые бэкендом

Дата: 2026-11-19. Режим: только расследование; рабочая БД не изменялась; правки кода/конфигов/тестов запрещены; внешняя отправка не выполнялась. `shifts/templates.py`, `bank_integration_service.py`, `geofence.py` не тронуты. Коммит — только этот отчёт через pathspec с проверкой состава до push.

Метод: для страниц `frontend/src/pages` и api-модулей извлечены вызовы apiClient и поля, читаемые из `res.data` (прямые обращения, map по массиву, ключи колонок/графиков); сопоставлены с фактическим возвратом зарегистрированного обработчика (код return / response_model / ключи словаря, с учётом вложенности и массивов). Приоритет — money-поля и счётчики (undefined → 0/NaN выглядит как факт). Динамические ключи/`any` помечены «требует подтверждения».

**Охват (честно):** сплошная сверка выполнена для dict-returning stats/dashboard/money-эндпоинтов (platform-overview, receivables, fuel-dashboard, fuel analytics/consumption/by-vehicle, driver-kpi, utilization, cost-per-hour/rates/forecast, pnl, gps/points/stats, marketplace/stats, acts/registry, recent-actions). CRUD-страницы на Pydantic response_model (Vehicles/Requests/Invoices/Payouts/Finance/Salaries/Maintenance/Contractors/Drivers) сплошняком НЕ сверялись — см. §5.

---

## 1. ПОДТВЕРЖДЕНО: поле читается, но НЕ возвращается (undefined в интерфейсе)

### Приоритет — money / видимость факта

| Страница:строка | Поле | Путь/метод | Возврат обработчика | Что увидит пользователь | Доказательство |
|---|---|---|---|---|---|
| **PlatformOverviewPage.tsx:117** | `data.revenue_trend` | GET /shifts/stats/platform-overview | `get_platform_overview` возвращает users/vehicles/acts_this_month/overdue_acts/transactions_this_month/unmatched_transactions/documents_in_archive/shifts_today/date — **revenue_trend НЕТ** | `(data.revenue_trend \|\| [65,45,80,55,90,70,85]).map(…)` → **hardcoded фейковый тренд выручки** [65,45,80,55,90,70,85] под видом реальных данных | shift_stats_service.get_platform_overview return (без revenue_trend); PlatformOverviewPage:117 fallback-массив |
| **ActsPage.tsx:163** | `a.signature` | GET /shifts/acts/registry | `get_acts_registry` items: id/act_number/act_date/vehicle_name/driver_name/hours_worked/total_amount/vat_amount/status/edo_message_id — **signature НЕТ** | `a.status==='signed' && a.signature` → signature undefined → **KEP-бейдж ✍️ не показывается** даже у подписанных актов | diadoc.py:309-320 items (без signature); ActsPage:163 |
| **ReceivablesPage.tsx:107** | `a.counterparty` | GET /shifts/stats/receivables | `get_receivables_dashboard` overdue_acts[].counterparty = **захардкожено ""** (bank.py:213) | `a.counterparty \|\| '—'` → **всегда '—'** (поле есть, но никогда не заполняется) | bank.py:213 `"counterparty": ""`; ReceivablesPage:107 |

### Приоритет — счётчики / индикаторы

| Страница:строка | Поле | Путь/метод | Возврат | Что увидит пользователь | Доказательство |
|---|---|---|---|---|---|
| **PlatformOverviewPage.tsx:128-138** | `data.gps_health.{success_rate,avg_ms,errors_24h}` | GET /shifts/stats/platform-overview | gps_health **НЕ возвращается** | `data.gps_health?.success_rate ?? '—'` → **'—' / 0** (блок «Здоровье GPS» пуст) | get_platform_overview return без gps_health; PlatformOverviewPage:128-138 optional chaining |
| **ActsPage.tsx:147** | `a.vehicle_id` | GET /shifts/acts/registry | items без vehicle_id (есть vehicle_name) | `a.vehicle_name \|\| a.vehicle_id` → при пустом vehicle_name fallback undefined → пусто | diadoc.py:309-320 (vehicle_name есть, vehicle_id нет); ActsPage:147 |
| **FuelDashboardPage.tsx:42-66** | `data.summary.{total_liters,avg_daily_liters,total_entries,vehicles_count,anomalies_count}` | GET /shifts/stats/fuel-dashboard | при отсутствии записей `get_fuel_dashboard` возвращает **`summary: {}`** (пустой объект) | `data.summary.total_liters` → **undefined → пустые/NaN карточки** (edge-case нет данных) | shift_stats_service.get_fuel_dashboard early-return `summary: {}`; FuelDashboardPage:42-66 |
| **finance.ts:538** (`verifyUpdSignature`) | тип `{valid, xml_size, sig_size}` | GET /shifts/acts/{id}/verify-signature | handler возвращает `{valid, provider, signed_at}` (или `{valid, message}`) | **xml_size/sig_size undefined**; тип фронтенда не совпадает. **Латентно:** verifyUpdSignature не вызывается ни одной страницей (grep tsx пуст) | diadoc.verify_act_signature return; finance.ts:538 тип; нет UI-потребителя |

### Смежное (путь, не поле — кнопка 404)
| Страница:строка | Вызов | Реальный маршрут | Что увидит пользователь |
|---|---|---|---|
| **UtilizationPage.tsx:42** «Выгрузка 1С» | GET /shifts/export/1c-acts | зарегистрирован **/shifts/acts/export/1c** (export_acts_for_1c) | кнопка → **404** (ничего не выгружает) |

---

## 2. Наблюдения: поле возвращается, но не используется / всегда пусто (возможная недоделка, не дефект)

| Обработчик | Поле | Наблюдение |
|---|---|---|
| get_acts_registry (diadoc.py:314) | `driver_name` | возвращается, но ActsPage не читает; при этом `getattr(a,"driver_name",None)` — у Act нет driver_name → **всегда ""** (phantom). Недоделанная колонка «Водитель» в реестре |
| get_driver_kpi | `active_days`, `total_days` | возвращаются, DriverKPIPage не читает (только shift_count/utilization_pct/total_hours/completion_rate/rating) |
| get_receivables_dashboard | `overdue_acts[].status` | возвращается, ReceivablesPage не читает |
| get_platform_overview | `date` | возвращается, PlatformOverviewPage не читает |
| get_fuel_analytics | `total_drains`, `total_volume_drain`, `net_volume` | возвращаются, FuelAnalyticsPage не читает (только refuel-метрики) |

---

## 3. Приоритет money-полей и счётчиков (пояснение)
- **revenue_trend (PlatformOverview)** — самый опасный: отсутствие поля замаскировано hardcoded-массивом, и пользователь видит **фейковый тренд выручки как факт**. Это не «пусто», а ложные данные.
- **counterparty (Receivables)** — всегда '—': дебиторка без контрагента, поле не заполняется кодом.
- **signature (ActsPage)** — подписанные акты не показывают KEP-индикатор: пользователь не видит, что акт подписан.
- **summary:{} (FuelDashboard)** — при отсутствии данных карточки undefined/NaN вместо явных 0/«нет данных».
- Остальные money-поля (total_amount/revenue/outstanding/total_cost/liters) в проверенных эндпоинтах возвращаются и совпадают с читаемыми (см. §4).

---

## 4. Проверено и СОВПАДАЕТ (охват, дефектов нет)

| Страница | Эндпоинт | Поля ответа ↔ читаемые |
|---|---|---|
| PnLPerVehiclePage | /shifts/stats/pnl | vehicles[].{vehicle_id,vehicle_name,hours,revenue,fuel_cost,wage_cost,amortization_cost,margin,margin_pct} — все есть. (hours=0 — отдельный дефект значения из phantom planned_start, не отсутствие поля; см. MODEL_KWARGS/PHANTOM_READS) |
| CostPerHourPage | /shifts/stats/cost-per-hour, cost-rates, cost-forecast | summary/vehicles/rates/forecast.{total_cost,change_pct,fuel_liters,fuel_cost,wage_cost,amortization_cost}/period.forecast_from — совпадают |
| FinanceDashboardPage | /shifts/stats/finance-dashboard | summary.{total_revenue,total_expenses,total_margin,total_margin_pct}/months[] — совпадают |
| DriverKPIPage | /shifts/stats/driver-kpi | drivers[].{driver_id,driver_name,rating,shift_count,utilization_pct,total_hours,completion_rate} — совпадают |
| UtilizationPage | /shifts/stats/utilization | summary.{total_vehicles,avg_utilization_pct,total_shifts,total_hours}/vehicles[] — совпадают |
| FuelAnalyticsPage | /telematics/fuel/analytics, /consumption, /by-vehicle | analytics.{total_volume_refuel,total_refuels,total_cost,avg_price_per_liter,avg_volume_per_refuel,refuels_by_month,period}; consumption[].{engine_hours,liters_per_hour,liters_per_100km,total_fuel_liters} (engine_hours/liters_per_hour всегда float → .toFixed безопасен); byVehicle[].{refuels_count,drains_count,total_refuel_volume,total_drain_volume,net_volume,total_cost,avg_cost_per_refuel} — совпадают |
| FuelDashboardPage (непустой case) | /shifts/stats/fuel-dashboard | summary/daily_trend/anomalies/top_consumers — совпадают |
| DashboardPage | platform-overview, /gps/points/stats, /public/marketplace/stats | platformOverview.{shifts_today,acts_this_month,overdue_acts,transactions_this_month,unmatched_transactions}; gpsStats.{total_points,vehicles_with_data}; mpStats.{active_requests,assigned_requests,pending_responses,avg_payment_days,client_requests,dispatcher_requests} — совпадают |
| ReceivablesPage | /shifts/stats/receivables | summary.{total_outstanding,overdue_amount,overdue_count,on_time_amount}/ageing_buckets{current,1_30,31_60,61_90,90_plus}/overdue_acts[].{act_number,act_date,vehicle_name,outstanding,days_overdue} — совпадают (кроме counterparty §1) |
| PlatformOverviewPage (recent-actions) | /shifts/stats/recent-actions | [{id,action,details,resource_type,created_at}] — совпадают (resource_type корректен, в отличие от admin.py entity_type) |

---

## 5. Требует подтверждения / не покрыто сплошняком
- **CRUD-страницы на response_model** (VehiclesPage/RequestsPage/InvoicesPage/PayoutsPage/FinancePage/SalariesPage/MaintenancePage/ContractorsPage/DriversPage): используют Pydantic-схемы (VehicleRead/RequestRead/InvoiceRead/PayoutRead/ActRead и др.). Сплошная сверка читаемых полей со схемами в этой задаче НЕ выполнена (приоритет отдан dict-returning stats/money). Возможные расхождения (поле читается, но не в схеме) не исключены — требуется отдельный проход.
- **ActsPage refresh-statuses** (`res.data.updated/total_checked`): возврат refresh_all_diadoc_statuses не сверен в этой задаче — требует подтверждения.
- **Динамические ключи/any**: большинство страниц типизированы `any` (data:any, a:any) — статически гарантировать полноту нельзя; выводы основаны на фактических обращениях в коде + возврате обработчика.
- **PnL hours=0**: значение неверно (phantom planned_start/end), но поле hours присутствует — это дефект значения (PHANTOM_READS/MODEL_KWARGS), не контракта ответа. Пользователь видит 0 часов/зарплаты/амортизации и завышенную маржу как факт.

## 6. Сводка приоритетов
1. **revenue_trend фейк** (PlatformOverview) — ложные money-данные под видом факта.
2. **signature KEP-бейдж** (ActsPage) — не видно, что акт подписан (документы).
3. **counterparty всегда '—'** (Receivables) — дебиторка без контрагента.
4. **gps_health пусто** (PlatformOverview), **summary:{} NaN** (FuelDashboard edge), **vehicle_id fallback** (ActsPage).
5. **verify-signature xml_size/sig_size** (finance.ts, латентно, нет потребителя).
6. **1С-кнопка 404** (UtilizationPage, путь).

Все находки — отчёт; исправление решает пользователь. Ничего не правилось.
