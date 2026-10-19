# Docker Graceful Shutdown

## Overview

All services configured с правильным graceful shutdown для предотвращения потери данных и обеспечения корректной остановки.

## Параметры остановки

### Backend (FastAPI + Uvicorn)
- `init: true` - zombie process reaping
- `stop_grace_period: 45s` - время на завершение запросов
- `stop_signal: SIGINT` - корректный сигнал для Uvicorn
- `--timeout-graceful-shutdown 30` в entrypoint.sh
- Lifespan handler закрывает: scheduler, DB connections, Redis

### PostgreSQL
- `stop_grace_period: 60s` - максимальное время для flush данных
- Стандартный SIGTERM от Docker корректно обрабатывается PostgreSQL
- WAL логи гарантируют целостность данных при остановке

### Redis
- `stop_grace_period: 30s` - время для сохранения RDB/AOF
- `appendonly yes` - AOF persistence включен
- Данные сохраняются на диск перед остановкой

### MinIO
- `stop_grace_period: 30s` - завершение активных upload/download
- Объекты в процессе загрузки сохраняются или отменяются корректно

## Проверка graceful shutdown

```bash
# Запустить сервисы
docker-compose up -d

# Посмотреть логи shutdown
docker-compose stop backend
docker logs spectech-backend | grep -i shutdown

# Ожидаемый вывод:
# 🔄 Shutting down scheduler...
# ✅ Database connections closed
# ✅ Redis connection closed
# 👋 SpectechPlatform shut down gracefully
```

## Таймауты

| Сервис | Grace Period | Причина |
|--------|--------------|----------|
| Backend | 45s | Завершение HTTP запросов, cleanup ресурсов |
| PostgreSQL | 60s | Flush WAL, checkpoint, закрытие соединений |
| Redis | 30s | Сохранение AOF/RDB snapshot |
| MinIO | 30s | Завершение multipart uploads |
| Nginx | 10s (default) | Закрытие keep-alive соединений |

## Troubleshooting

### Сервис не останавливается за grace period
- Проверить зависшие запросы: `docker exec spectech-backend ps aux`
- Увеличить `stop_grace_period` в docker-compose.yml
- Проверить логи: `docker logs --tail 100 spectech-backend`

### PostgreSQL теряет данные при остановке
- Убедиться что `stop_grace_period: 60s` установлен
- Проверить `postgresql.conf`: `synchronous_commit = on`
- Мониторить WAL размер: `docker exec spectech-postgres pg_controldata /var/lib/postgresql/data`

### Redis не сохраняет данные
- Проверить AOF persistence: `docker exec spectech-redis redis-cli INFO persistence`
- Убедиться что volume примонтирован: `docker volume ls | grep redis`
