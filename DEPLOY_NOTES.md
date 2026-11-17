global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alert_rules.yml

scrape_configs:
  - job_name: 'spectech-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

## Инвентаризация алертов (17.11.2026)

Проверено исполнением выражений через API Prometheus, а не чтением файлов.

**Что было сломано:** в `prometheus.yml` не было секции `rule_files`. Файл с
правилами был смонтирован и валиден, но не загружался: API отдавал ноль групп.
Десять алертов, написанных ранее, никогда не вычислялись.

**Что работает после починки (12 правил в 3 группах):**

| Правило | Состояние |
|---|---|
| BackendDown | видит данные, up=1 |
| HighLatency | видит данные, p95≈0.10s |
| HighErrorRate | сработает при первом 5xx (серии 5xx пока нет) |
| SchedulerJobFailing / SchedulerJobMissed | сработают при первом провале задачи |
| PostgresDown / ConnectionsNearLimit / Deadlocks | мертвы: нет postgres-exporter |
| RedisDown / RedisMemoryHigh | мертвы: нет redis-exporter |
| DiskSpaceLow | мёртво: нет node-exporter |
| ContainerRestarting | мёртво: нет cadvisor |

**Доставки нет:** секции `alerting` в конфиге нет, Alertmanager не поднят,
`/api/v1/alertmanagers` отдаёт ноль активных. Алерты видны в UI Prometheus и
никуда не отправляются.

**Как проверять, а не угадывать:** пустой результат выражения с сравнением
(`up == 0`) означает «условие ложно», а не «правило сломано». Чтобы отличить
здоровое правило от слепого, надо вычислять основу без сравнения (`up`).
Метка статуса у instrumentator сгруппирована: `status="2xx"`, не `200`.

**Не сделано (требует решения):** Alertmanager с доставкой в MAX через
внутренний webhook backend; экспортёры postgres/redis/cadvisor/node для
семи мёртвых правил.
