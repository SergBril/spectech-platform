# Collation mismatch: расследование и вердикт

## Среда

- Образ `timescale/timescaledb:2.30.1-pg16`, Alpine 3.23 (musl). Запинен по digest в `docker-compose.yml`.
- `pg_database.datcollversion = '2.41'` (glibc), `datcollate = en_US.utf8`.
- musl не сообщает версию коллации, поэтому `ALTER DATABASE ... REFRESH COLLATION VERSION`
  падает с `invalid collation version change`, а предупреждение печатается на каждом подключении:
  `database "spectech" has no actual collation version, but a version was recorded`.
- TimescaleDB 2.30.1, гипертаблица `gps_points`.

Причина расхождения: плавающий тег `latest-pg16` сменил базовый образ с glibc на Alpine
под уже существующим кластером.

## Вердикт

**На текущих данных порядок под индексами совпадает с порядком под текущим libc.
Ни один index-backed запрос не возвращает иных результатов. Аварийный `REINDEX` не требуется —
live-базу рекомендуется оставить в покое.**

Вердикт основан на наблюдаемом выводе запросов, а не на рассуждениях о musl vs glibc.

## Что измерялось

Два независимых прогона:

1. **Scratch** `collation_check` (из `template0`, восстановление байт-в-байт дампа) —
   до и после `REINDEX DATABASE collation_check`.
2. **Live `spectech`, только на чтение** (SELECT/EXPLAIN/SET LOCAL, транзакция READ ONLY) —
   решающее измерение: индексы live те самые, что могли быть построены под glibc.

Для каждой индексированной text/varchar/name-колонки public-схемы сравнивался порядок
строк, отдаваемый индексом (`enable_seqscan=off`), с порядком seqscan + явная сортировка
под текущим libc (`enable_indexscan=off`, `enable_bitmapscan=off`). Индексный путь
подтверждался через `EXPLAIN (FORMAT JSON)` (top node `Index Only Scan`); колонки без
индексного плана помечались NOT MEASURED. Дополнительно — range-пробы
`col >= 'О' AND col < 'П'` (фиксированная) и `col >= min(col) AND col < max(col)`
(data-derived, неvacuous): index vs seqscan, сравнение множеств ctid по хэшам.
В вывод только счётчики/хэши/позиции/узлы планов — без значений данных.

Чувствительность детектора проверена самотестом: `ORDER BY name` против
`ORDER BY name DESC` → `asc_vs_desc_differs=true` (механизм ловит различия, не слепой).

## Гейты верности scratch-копии

Дамп `backup-clean.sql` (128 712 621 байт, байт-в-байт, создан в контейнере + `docker cp`).

- Restore: `CREATE EXTENSION timescaledb` + `timescaledb_pre_restore()`; конфликт
  `metadata_pkey` устранён очисткой `_timescaledb_catalog.metadata` в scratch;
  циклические FK — загрузка с `session_replication_role=replica` (plain SQL →
  `pg_restore --disable-triggers` неприменим; роль отключает FK-триггеры на сессию,
  superuser). После — `post_restore()`, роль `origin`, невалидированных FK = 0.
- **Ноль ошибок** в логе восстановления (grep ERROR|FATAL = 0).
- Anti-join всех FK public-схемы: **TOTAL_ORPHAN_ROWS=0**.
- Счётчики строк **всех 79 public-таблиц** live vs scratch (отсортировано, `fc`):
  **no differences encountered**. (gps_points/audit_logs/user_sessions/salary_records
  дрейфовали относительно дампа от 16.11 из-за записи в live — обновлены в scratch
  read-only COPY из live; все 4 вне скоупа сравнения: индексированных text-колонок нет.)
- `gps_points`: **6708 = 6708**. Чанки: scratch 12, live 14; диапазоны 12 data-чанков
  совпадают; 2 «лишних» live-чанка — диапазоны **2030/2031** (выбросы часов устройств),
  точные счётчики `chunk2030_rows=0`, `chunk2031_rows=0`. Все 12 непустых чанков на месте.

## Результат

| Метрика | Scratch before | Scratch after REINDEX | Live (read-only) |
|---|---|---|---|
| Пар колонка/индекс | 26 | 26 | 26 |
| Измерено через индекс (Index Only Scan) | 24 | 24 | 24 |
| Расхождений порядка | **0** | **0** | **0** |
| Range `О..П` расхождений | 0 (vacuous, 0 строк) | 0 | 0 |
| Range min..max расхождений | 0 (12 неvacuous) | 0 | 0 (12 неvacuous) |
| NOT MEASURED (план Sort) | 2 | 2 | 2 |

NOT MEASURED: `notification_templates.channel` (пустая таблица) и `permissions.action` —
неleading колонки композитных индексов, порядок даёт Sort на обоих путях; их range-пробы
index-backed и совпали.

Live-сводка (наблюдаемый вывод): `SUMMARY checked=26 index_backed=24 order_mismatches=0 idx_vs_c_diff=0`.
По всем 24 index-backed колонкам live: `order_match=t`, `idx_vs_c_match=t`, `seq_vs_c_match=t`.
Полная по-колонная таблица — в `live_results.txt` (артефакты ниже); ключевые строки:

| Колонка | Строк | План | order_match | idx_vs_c | r2 строк | r2_match |
|---|---|---|---|---|---|---|
| uploaded_files.storage_path | 468 | Index Only Scan | t | t | 467 | t |
| bank_transactions.bank_transaction_id | 48 | Index Only Scan | t | t | 47 | t |
| invoices.document_number | 45 | Index Only Scan | t | t | 44 | t |
| categories.code | 36 | Index Only Scan | t | t | 35 | t |
| requests.region | 29 | Index Only Scan | t | t | 0 | t |
| acts.document_number | 19 | Index Only Scan | t | t | 18 | t |
| vehicles.id_value | 16 | Index Only Scan | t | t | 15 | t |
| users.email | 12 | Index Only Scan | t | t | 11 | t |
| permissions.entity | 12 | Index Only Scan | t | t | 8 | t |
| payouts.document_number | 7 | Index Only Scan | t | t | 6 | t |

(остальные 16 колонок — аналогично, все `t`; полные выводы в артефактах)

## Отрицательный результат, который нельзя считать доказательством

Пробник на scratch показал те же нули — но он **невалиден как доказательство glibc→musl
staleness**: plain-SQL дамп содержит `CREATE INDEX`, поэтому индексы в scratch строятся
заново под musl и не воспроизводят состояние «индекс построен под glibc». Нулевое
расхождение там предопределено конструкцией (musl-vs-musl); REINDEX ничего не меняет.
Измерять нужно живые индексы — что и сделано в live-прогоне.

Положительный контроль `COLLATE "C"` против дефолта дал `differs=f` на всех пяти пробах
(companies.name, contractors.name, vehicles.name, users.full_name, users.email).
Это не поломка методики, а факт о среде, доказанный литеральным探针ом:

```
VALUES ('a'),('B'),('b'),('A'),('ё'),('е'),('Ё'),('Е')
default = {A,B,a,b,Ё,Е,е,ё}
C       = {A,B,a,b,Ё,Е,е,ё}   -- идентично
```

Под musl `en_US.utf8` ведёт себя как `C` (побайтовый порядок); glibc дал бы
регистронезависимый primary-порядок. Контроль, сравнивающий тождественные вещи,
чувствительность не доказывает — поэтому и был добавлен самотест детектора (ASC/DESC).
По заданному гейту «control shows divergence» **scratch-скоуп = NOT MEASURED**;
решающий вердикт вынесен по live-измерению.

## Границы применимости

Данных мало: 4 компании, 11 контрагентов, 16 машин, 8 сотрудников. Расхождения
glibc/musl проявляются на смешанном регистре, пунктуации, `ё`/`й`, латинице с диакритикой.
Индексированные колонки — преимущественно коды/идентификаторы/нижний регистр; русские
`name`-колонки **не индексированы** (для них нет индекса, который мог бы конфликтовать
с текущим libc). На таком объёме расхождений может не быть просто статистически.
«Сейчас не врёт» не равно «никогда не соврёт».

## Рекомендации

1. Образ запинен — сделано. Предотвращает повторную смену libc при пересборке.
2. `REINDEX` не делать аварийно — доказательств расхождений нет. Внести в плановое
   обслуживание при росте объёма текстовых данных или жалобах на поиск по названиям.
   Стоимость низкая (крупнейшие таблицы: gps_points 6708, uploaded_files 468,
   user_sessions 671), но выигрыша по текущим данным нет.
3. Предупреждение о коллации считать косметическим **до** появления наблюдаемых расхождений;
   `REFRESH COLLATION VERSION` на musl недоступен. Повторять пробник после роста данных.
4. Обновление образа TimescaleDB делать осознанно: при смене libc — `REINDEX` в окно
   обслуживания (при возврате на glibc уже musl-построенные индексы станут устаревшими).

## Побочный урок: как снимать дамп

`pg_dump ... | Out-File -Encoding utf8` в PowerShell **портит данные**: конвейер
декодирует поток консольной codepage и перекодирует обратно, русские строки становятся
mojibake, длины в символах растут, `varchar(20)` переполняется на строке, которая в живой
базе помещается. Один такой дамп дал 1 отбракованную строку и каскад из 8 FK-ошибок.

Правильно — писать внутри контейнера и копировать байт-в-байт:

```
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/dump.sql'
docker cp spectech-postgres:/tmp/dump.sql C:\Users\osavi\backups\backup-clean.sql
docker compose exec -T postgres rm /tmp/dump.sql
```

Проверка дампа: отсутствие BOM, строгая UTF-8 декодируемость, отсутствие mojibake-маркеров,
совпадение числа строк в ключевых таблицах.

## Соблюдение ограничений и артефакты

- Live `spectech`: только read-only; REINDEX/ALTER/DROP по spectech не выполнялись;
  docker-compose.yml не менялся; контейнеры не пересоздавались.
- Секреты не печатались: только счётчики/хэши/позиции/узлы планов.
- Scratch `collation_check` удалён (`DROP DATABASE ... WITH (FORCE)`); промежуточные
  TSV с данными удалены.
- Артефакты вне репозитория (`C:\Users\osavi\backups\`): `restore_clean.log`,
  `harness_setup.log`, `results_before.txt`, `results_after.txt`, `live_results.txt`,
  `counts_live_sorted.txt` / `counts_scratch_sorted.txt`, `collation_harness.sql` (v3),
  `collation_runner.sql`, `live_readonly_checks.sql`, `fk_orphan_check.sql`.
