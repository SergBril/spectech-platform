# 🏢 Multi-Company (Multi-Tenant) архитектура

## Обзор

Система поддерживает работу нескольких независимых компаний в одной инсталляции (multi-tenant SaaS). Каждая компания видит только свои данные.

## Схема данных

companies
├── id (PK)
├── name
├── legal_name
├── inn
├── default_tax_system
└── is_active
users
├── id (PK)
├── email
├── company_id (FK → companies)
└── is_superuser
contractors, vehicles, requests, invoices, acts, payouts, shifts, ...
└── company_id (FK → companies) ← все бизнес-сущности


## Переключение между компаниями

### Для обычных пользователей
- Видят только свою компанию
- Не могут переключаться

### Для superuser
- Может переключаться между всеми компаниями
- Использует HTTP header `X-Company-Id`

### UI-компонент: CompanySwitcher

Расположен в `Navbar`, справа от логотипа. Показывает:
- Текущую компанию (с иконкой 🏢)
- Dropdown со всеми доступными компаниями (для superuser)
- ИНН и систему налогообложения каждой компании

## Backend: как это работает

### 1. Endpoint `/api/v1/me/companies`

Возвращает список компаний:
- Superuser: все активные
- Обычный пользователь: только своя

### 2. Header `X-Company-Id`

Добавляется автоматически axios interceptor'ом:

```typescript
// frontend/src/api/client.ts
apiClient.interceptors.request.use((config) => {
  const companyId = localStorage.getItem('spectech_current_company_id');
  if (companyId) {
    config.headers['X-Company-Id'] = companyId;
  }
  return config;
});

3. Dependency get_current_company_id

# backend/app/api/deps.py
def get_current_company_id(
    user: User = Depends(get_current_user),
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    db: Session = Depends(get_db),
) -> int:
    if x_company_id and user.is_superuser:
        requested_id = int(x_company_id)
        company = db.get(Company, requested_id)
        if not company or not company.is_active:
            raise HTTPException(404, "Company not found")
        return requested_id
    return user.company_id

4. Использование в роутах

@router.get("/invoices")
def list_invoices(
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Invoice).where(Invoice.company_id == company_id)
    ).all()

Изолированные сущности

Сущность
Endpoint
Статус
Contractors
/contractors
✅
Vehicles
/vehicles
✅
Requests
/requests
✅
Invoices
/invoices
✅
Acts
/acts
✅
Payouts
/payouts
✅
Shifts
/shifts/*
✅
Geofences
/telematics/geofences
✅
Fuel
/telematics/fuel
✅
Alerts
/telematics/alerts
✅
GPS Points
/telematics/gps/*
✅
Analytics
/analytics/*
✅
Finance Dashboard
/payments/dashboard
✅


Тестирование
Тест-кейс: изоляция данных
Зайти как admin@spectech.dev (superuser, компания 1)
Открыть "Счета" → увидеть 20 счетов
Переключиться через CompanySwitcher на "ИП Иванов А.С." (компания 2)
Открыть "Счета" → увидеть 0 счетов
Вернуться на компанию 1 → снова 20 счетов
curl тесты

# Компания 1 (через user.company_id)
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/contractors
# → 2 контрагента

# Компания 2 (через X-Company-Id)
curl -H "Authorization: Bearer $TOKEN" \
     -H "X-Company-Id: 2" \
     http://localhost:8000/api/v1/contractors
# → 1 контрагент (ИП Петров)

Безопасность
Защита от IDOR
Все запросы фильтруются по company_id на уровне БД
Нельзя получить чужие данные, подставив ID в URL
Superuser проходит валидацию: компания должна быть активной
Защита от эскалации привилегий
Header X-Company-Id работает только для is_superuser=true
Обычный пользователь с поддельным header получит свои данные
Миграция существующих данных

-- Привязать все существующие данные к компании 1
UPDATE contractors SET company_id = 1 WHERE company_id IS NULL;
UPDATE vehicles SET company_id = 1 WHERE company_id IS NULL;
UPDATE requests SET company_id = 1 WHERE company_id IS NULL;
UPDATE invoices SET company_id = 1 WHERE company_id IS NULL;
UPDATE acts SET company_id = 1 WHERE company_id IS NULL;
UPDATE payouts SET company_id = 1 WHERE company_id IS NULL;
UPDATE shift_tasks SET company_id = 1 WHERE company_id IS NULL;
UPDATE shift_reports SET company_id = 1 WHERE company_id IS NULL;
UPDATE geofences SET company_id = 1 WHERE company_id IS NULL;
UPDATE fuel_transactions SET company_id = 1 WHERE company_id IS NULL;
UPDATE alerts SET company_id = 1 WHERE company_id IS NULL;

Roadmap
Роли в компаниях (admin, manager, viewer)
Приглашения пользователей в компанию по email
Логирование действий по компаниям (audit log)
Лимиты по компаниям (техника, пользователи)
Billing / подписки
