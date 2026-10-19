# Platform Owner Access Control

## Overview

Админ-панель платформы доступна только владельцу (разработчику).

## Настройка

1. Добавьте в `.env`:
   ```
   PLATFORM_OWNER_EMAIL=your-email@example.com
   ```

2. Убедитесь что пользователь с этим email имеет `is_superuser=True`

## Механизм работы

- **Backend**: `_check_platform_owner()` проверяет email перед доступом к admin endpoints
- **Frontend**: Sidebar фильтрует пункт "Админ-панель" по email владельца
- Только `admin@spectech.dev` (или указанный email) видит и имеет доступ

## Тестирование

```bash
# Войти как владелец
# Sidebar показывает "Админ-панель"
# Перейти на /admin/dashboard - работает

# Войти как обычный superuser (другой email)
# Sidebar НЕ показывает "Админ-панель"
# /admin/stats возвращает 403
```

## Безопасность

- Проверка на двух уровнях: UI (скрытие меню) + API (403 Forbidden)
- Даже если обойти UI, API вернет ошибку доступа
- Email владельца хранится в `.env` (не в коде)
