# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/).

## [1.7.0] - 2026-09-17

### Added
- Полная документация проекта
- `docs/ARCHITECTURE.md` — архитектура системы
- `docs/MULTI_COMPANY.md` — multi-tenant документация
- `docs/EMAIL_SETUP.md` — настройка SMTP
- `docs/DEPLOYMENT.md` — инструкция по деплою
- Обновлён README.md с полной информацией о проекте

## [1.6.1] - 2026-09-17

### Fixed
- PDF теперь прикрепляется и к email-уведомлениям об актах
- MIME-тип PDF корректно указан как `application/pdf`
- Удалён временный диагностический файл из репозитория

## [1.6.0] - 2026-09-17

### Added
- **Email-уведомления с PDF-вложениями** для счетов и актов
- Кнопка 📧 "Отправить повторно" в UI для счетов и актов
- Endpoint `POST /invoices/{id}/resend-email`
- Endpoint `POST /acts/{id}/resend-email`
- Интеграция с MailHog для локальной разработки

## [1.5.1] - 2026-09-17

### Fixed
- Удалён дубликат `translate_unit` из `finance_service.py`
- Очищены мусорные описания в `invoice_items`
- Перегенерированы все 38 PDF-документов
- Удалён BOM-символ в начале `finance_service.py`

## [1.5.0] - 2026-09-17

### Added
- **Полная изоляция мульти-компании** для аналитики и finance dashboard
- `analytics.py`: все endpoints используют `get_current_company_id`
- `payments.py`: убрана специальная логика для superuser

## [1.4.0] - 2026-09-17

### Added
- **Multi-company frontend**: CompanySwitcher в Navbar
- `CompanyContext` с хранением выбора в localStorage
- `Navbar.tsx` — переиспользуемый компонент навигации
- Header `X-Company-Id` во все API-запросы

## [1.3.0] - 2026-09-16

### Added
- **Multi-company backend**: изоляция данных по company_id
- Фильтрация по company_id во всех основных роутах
- Dependency `get_current_company_id` в `deps.py`
- Вторая тестовая компания "ИП Иванов А.С." (УСН 6%)

## [1.2.0] - 2026-09-16

### Added
- **Справочник контрагентов** (Backend + Frontend)
- Автоподстановка системы налогообложения клиента
- Корректный расчёт НДС (ОСНО/УСН/Патент/НПД)
- Полные реквизиты контрагентов в PDF-документах
- Русификация единиц измерения (час, смена, км)

## [1.0.0] - 2026-09-11

### Initial Release
- Первый рабочий прототип платформы
- Базовая аутентификация
- CRUD для техники и заявок

[1.7.0]: https://github.com/SergBril/spectech-platform/compare/v1.6.1...v1.7.0
[1.6.1]: https://github.com/SergBril/spectech-platform/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/SergBril/spectech-platform/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/SergBril/spectech-platform/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/SergBril/spectech-platform/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/SergBril/spectech-platform/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/SergBril/spectech-platform/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/SergBril/spectech-platform/compare/v1.0.0...v1.2.0
[1.0.0]: https://github.com/SergBril/spectech-platform/releases/tag/v1.0.0
