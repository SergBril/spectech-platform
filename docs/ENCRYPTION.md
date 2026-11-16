# Шифрование секретов интеграций (ENCRYPTION_KEY)

Секреты интеграций в БД (`companies.diadoc_api_key`, `companies.sbis_token`)
хранятся зашифрованными (Fernet, префикс `enc::`). Ключ шифрования —
**отдельная** переменная `ENCRYPTION_KEY`, не связанная с `JWT_SECRET_KEY`:
ротация JWT не должна делать секреты нерасшифровываемыми.

## Генерация ключа

Однократно, на защищённой машине (результат — в secret manager / `.env.prod`,
**никогда** в репозиторий):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- `.env.prod`: `ENCRYPTION_KEY=<сгенерированный ключ>`.
- Helm: `--set credentials.encryption.key=<ключ>` (передаётся в backend через
  secret `db-credentials`, см. `helm/spectech/templates/backend-deployment.yaml`).
- В production отсутствие ключа — **ошибка старта**: lifespan вызывает
  `ensure_keys_configured()`, контейнер без ключа не поднимается (crash-loop
  виден сразу). В dev/testing ключ выводится из `JWT_SECRET_KEY` с warning —
  для прода это недопустимо.

## Ротация ключа (с ОБЯЗАТЕЛЬНОЙ перешифровкой)

MultiFernet читает значения и активным, и предыдущим ключом, поэтому ротация
идёт без простоя:

1. Сгенерировать новый ключ (команда выше).
2. Установить `ENCRYPTION_KEY_PREVIOUS=<старый ключ>`,
   `ENCRYPTION_KEY=<новый ключ>`.
3. Пересоздать контейнеры: `docker compose up -d` (именно `up -d`, не
   `restart` — `restart` не перечитывает env_file). Для helm — обновить secret
   и сделать rollout.
4. Перешифровать существующие секреты активным ключом:
   ```bash
   docker compose exec -T backend python scripts/rotate_company_secrets.py          # dry-run
   docker compose exec -T backend python scripts/rotate_company_secrets.py --apply  # запись
   ```
   Скрипт идемпотентен: уже перешифрованные значения не трогает, легаси-открытые
   (без `enc::`) пропускает и выводит в отчёт, нечитаемые значения НЕ перезаписывает.
   В отчёте только `company_id`/поле/статус, без самих секретов.
5. Проверить, что `failed=0` и настройки ЭДО читаются (маски в GET `/edo-settings`,
   флаги `*_decryptable`).
6. **Только после перешифровки** очистить `ENCRYPTION_KEY_PREVIOUS` и снова
   `up -d`. Если очистить previous до перешифровки, значения, зашифрованные
   старым ключом, станут нечитаемыми (decrypt вернёт пустоту, интеграции уйдут
   в stub) — восстановление только повторным вводом ключей.

## Бэкап ключа — ОТДЕЛЬНО от бэкапа БД

- Дамп БД **без ключа бесполезен** для секретов: значения `enc::...` не
  расшифровать. Бэкап БД (ежедневный, `scripts/backup_db.sh`) не содержит ключ.
- Ключ хранить в secret manager / офлайн-копии (например, зашифрованный
  конверт в сейфе), отдельно от дампов БД и отдельно от репозитория.
- Проверять восстановление: дамп БД + копия ключа → тестовый стенд →
  `decrypt_secret` читает значения.
- При ротации предыдущий ключ тоже должен быть в бэкапе, пока не завершена
  перешифровка.

## Потеря ключа

Потеря `ENCRYPTION_KEY` (и `ENCRYPTION_KEY_PREVIOUS`) = **потеря всех
интеграционных секретов**: `decrypt_secret` вернёт пустоту, Diadoc уйдёт в
stub-режим. Восстановление невозможно перебором — только повторный ввод
ключей/токенов через UI настроек ЭДО (PUT `/edo-settings` шифрует новым ключом).
Поэтому бэкап ключа критичнее бэкапа БД.

## Перенос dev-БД в production

В dev без `ENCRYPTION_KEY` ключ выводится из `JWT_SECRET_KEY`
(`base64(sha256(jwt))`). Секреты dev-БД зашифрованы этим производным ключом.
При переносе в прод:

1. Вычислить dev-ключ: `python -c "import base64,hashlib; print(base64.urlsafe_b64encode(hashlib.sha256('<dev JWT_SECRET_KEY>'.encode()).digest()).decode())"`.
2. Установить в проде `ENCRYPTION_KEY=<новый прод-ключ>`,
   `ENCRYPTION_KEY_PREVIOUS=<вычисленный dev-ключ>`.
3. Выполнить перешифровку скриптом (шаги 4–6 ротации выше).
4. Очистить previous.

Без этого прод не расшифрует dev-значения (другой ключ) — компании уйдут в stub.

## Что шифруется

- `companies.diadoc_api_key`, `companies.sbis_token` — единственные поля,
  проходящие через `encrypt_secret` (PUT `/edo-settings`).
- Легаси-значения без префикса `enc::` отдаются как есть (постепенная миграция);
  скрипт ротации их не трогает — они попадают в отчёт как `skipped_plaintext`.
- `Vehicle.gps_provider_config` (api_key/password GPS-провайдеров) — пока
  plaintext, отдельная задача (долг зафиксирован).
