# 🏛️ Архитектура системы

## Общая схема
┌──────────────────────────────────────────────────────────────┐
│ Client │
│ (Browser / Mobile) │
└───────────────────────────┬──────────────────────────────────┘
│ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│ Nginx (prod) │
│ Reverse Proxy + SSL/TLS │
└───────────┬──────────────────────────────────────┬───────────┘
│ │
┌───────▼────────┐ ┌────────▼────────┐
│ Frontend │ │ Backend │
│ (React + Vite)│ │ (FastAPI) │
│ :3000 / :8080 │ │ :8000 │
└────────────────┘ └───┬─────┬───┬───┘
│ │ │
┌──────────────────────────┘ │ └────────────┐
│ │ │
┌────────▼────────┐ ┌────────▼──────┐ ┌──────▼──────┐
│ PostgreSQL │ │ Redis │ │ MinIO │
│ (port 5432) │ │ (port 6379) │ │ (port 9000)│
└─────────────────┘ └───────────────┘ └─────────────┘


## Backend: Слои приложения


backend/app/
├── api/
│ ├── deps.py # Dependencies (get_current_user, get_current_company_id)
│ └── routes/ # HTTP endpoints (FastAPI routers)
│ ├── auth.py # Регистрация, логин, refresh
│ ├── contractors.py
│ ├── requests.py
│ ├── vehicles.py
│ ├── invoices.py
│ ├── acts.py
│ ├── payouts.py
│ ├── shifts.py
│ ├── telematics.py
│ ├── analytics.py
│ ├── payments.py
│ └── me.py # Текущий пользователь + список компаний
├── core/
│ ├── config.py # Pydantic Settings (.env)
│ ├── db.py # SQLAlchemy async engine
│ └── constants.py # Enum'ы (TaxSystem, DocumentStatus)
├── models/ # SQLAlchemy ORM модели
├── schemas/ # Pydantic схемы (request/response)
├── services/ # Бизнес-логика
│ ├── finance_service.py # Создание документов
│ ├── email_service.py # SMTP
│ ├── pdf_generator.py # WeasyPrint
│ ├── storage_service.py # MinIO/S3
│ └── translations.py # Перевод единиц измерения
└── templates/ # Jinja2 шаблоны (email, PDF)

## Ключевые паттерны

### 1. Multi-Tenant Isolation

Каждый endpoint использует dependency `get_current_company_id`:

```python
@router.get("/contractors")
def list_contractors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    stmt = select(Contractor).where(Contractor.company_id == company_id)
    return db.scalars(stmt).all()

2. PDF Generation Pipeline

DB Data → Jinja2 Template (HTML+CSS) → WeasyPrint → PDF Bytes → MinIO → URL

3. Email with Attachments

Invoice/Act → generate_pdf() → storage_service.upload_bytes()
         ↓
email_service.send_email() → smtplib.SMTP → MailHog/SMTP
         ↑
storage_service.get_file() → временный файл → MIME attachment

Frontend: Структура

frontend/src/
├── api/
│   ├── client.ts         # Axios instance + interceptors
│   ├── finance.ts        # financeApi
│   ├── contractors.ts
│   ├── vehicles.ts
│   └── requests.ts
├── components/
│   ├── Navbar.tsx        # Общий навбар + CompanySwitcher
│   ├── CompanySwitcher.tsx
│   ├── InvoiceFormModal.tsx
│   └── ...
├── contexts/
│   ├── AuthContext.tsx   # JWT, user, login/logout
│   ├── CompanyContext.tsx # Текущая компания
│   └── WebSocketContext.tsx
└── pages/
    ├── DashboardPage.tsx
    ├── FinancePage.tsx   # Счета + Акты + Выплаты
    ├── InvoicesPage.tsx
    └── ...

Поток данных при переключении компании

1. User кликает "ИП Иванов" в CompanySwitcher
2. setCurrentCompanyId(2) → localStorage.setItem('spectech_current_company_id', '2')
3. window.location.reload()
4. CompanyProvider загружает /api/v1/me/companies
5. Axios interceptor добавляет X-Company-Id: 2 во все запросы
6. Backend get_current_company_id читает header → возвращает 2
7. Все SELECT'ы фильтруются по company_id = 2
8. Frontend получает пустые списки (у компании 2 нет данных)

Масштабирование
Текущий setup (single-server)
Все сервисы на одном VPS
Подходит до ~100 одновременных пользователей
Production ready (horizontal scaling)
Отдельный PostgreSQL (managed: AWS RDS / Yandex Managed PostgreSQL)
Отдельный Redis (managed)
Отдельный S3 (Yandex Object Storage / AWS S3)
Несколько backend-инстансов за load balancer
Frontend на CDN (CloudFlare / Yandex CDN)
