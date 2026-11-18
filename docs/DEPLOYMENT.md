# 🚀 Деплой в продакшен

## Требования к серверу

### Минимальные
- **CPU:** 2 cores
- **RAM:** 4 GB
- **Disk:** 40 GB SSD
- **OS:** Ubuntu 22.04 LTS
- **Бюджет:** ~500-1000 ₽/мес

### Рекомендуемые хостинги
- [Timeweb Cloud](https://timeweb.cloud/) — от 499 ₽/мес
- [Selectel](https://selectel.ru/) — от 600 ₽/мес
- [Yandex Cloud](https://cloud.yandex.ru/) — от 800 ₽/мес
- [Aeza](https://aeza.net/) — от 400 ₽/мес

## Шаг 1: Подготовка сервера

```bash
# SSH подключение
ssh root@your-server-ip

# Обновление системы
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
apt install docker-compose-plugin -y

# Создание пользователя
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy

Шаг 2: Настройка firewall

ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable

Шаг 3: Клонирование репозитория

su - deploy
git clone https://github.com/SergBril/spectech-platform.git
cd spectech-platform

Шаг 4: Настройка окружения

cp backend/.env.example backend/.env
nano backend/.env

Критически важные настройки
# JWT (генерируется через: openssl rand -hex 32)
JWT_SECRET_KEY=change-me-in-production

# PostgreSQL (смените пароль!)
DATABASE_URL=postgresql+psycopg://spectech:change-me-in-production@postgres:5432/spectech  # pragma: allowlist secret

# Production SMTP (Yandex/Gmail/Mailgun)
EMAIL_ENABLED=true
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=your-email@yandex.ru
SMTP_PASSWORD=change-me-in-production  # pragma: allowlist secret
SMTP_FROM_EMAIL=your-email@yandex.ru

# Sentry (для отслеживания ошибок)
SENTRY_DSN=https://change-me-in-production@sentry.io/xxx  # pragma: allowlist secret

# Environment
ENVIRONMENT=production
DEBUG=false

# CORS (ваш домен)
CORS_ORIGINS=https://yourdomain.com
FRONTEND_URL=https://yourdomain.com

Шаг 5: Nginx + Let's Encrypt
Установка certbot

apt install nginx certbot python3-certbot-nginx -y
Конфигурация Nginx
Создайте /etc/nginx/sites-available/spectech:

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 100M;

    # Frontend
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

Активация и SSL

ln -s /etc/nginx/sites-available/spectech /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# SSL сертификат (нужен работающий домен!)
certbot --nginx -d yourdomain.com -d www.yourdomain.com

Шаг 6: Запуск приложения

cd ~/spectech-platform
docker-compose up -d --build

# Проверка
docker-compose ps
docker-compose logs -f backend

Шаг 7: Бэкапы PostgreSQL
Автоматический бэкап (cron)

# Создать скрипт
nano /usr/local/bin/backup-spectech.sh

Содержимое:

#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker exec spectech-platform-postgres-1 pg_dump -U spectech spectech | gzip > $BACKUP_DIR/spectech_$DATE.sql.gz

# Удалять бэкапы старше 30 дней
find $BACKUP_DIR -name "spectech_*.sql.gz" -mtime +30 -delete

chmod +x /usr/local/bin/backup-spectech.sh

# Добавить в cron (ежедневно в 3:00)
crontab -e
# 0 3 * * * /usr/local/bin/backup-spectech.sh

Шаг 8: Мониторинг
UptimeRobot
Зарегистрируйтесь на https://uptimerobot.com/
Добавьте монитор: https://yourdomain.com/health
Настройте алерты в Telegram
Sentry

# В backend/.env
SENTRY_DSN=https://xxx@sentry.io/xxx

Логи

# Все сервисы
docker-compose logs -f

# Только backend
docker-compose logs -f backend

# Поиск ошибок
docker-compose logs backend | grep -i error

Шаг 9: CI/CD (GitHub Actions)
Создайте .github/workflows/deploy.yml:

name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd ~/spectech-platform
            git pull origin main
            docker-compose pull
            docker-compose up -d --build
            docker-compose exec -T backend alembic upgrade head

Secrets в GitHub
Настройки → Secrets and variables → Actions:
SERVER_HOST — IP сервера
SERVER_USER — deploy
SERVER_SSH_KEY — приватный SSH ключ
Шаг 10: Чек-лист перед запуском
Домен куплен и настроен DNS A-запись → IP сервера
SSL сертификат получен (Let's Encrypt)
PostgreSQL пароль изменён на сложный
JWT_SECRET_KEY сгенерирован (openssl rand -hex 32)
SMTP настроен (Yandex/Mailgun/SendGrid)
Sentry DSN добавлен
Автоматические бэкапы настроены (cron)
Firewall настроен (ufw)
UptimeRobot мониторит /health
Тестовая покупка/создание счёта прошла успешно
Email приходит на реальный ящик
Откат на предыдущую версию

cd ~/spectech-platform
git log --oneline  # посмотреть историю
git checkout v1.6.1  # или другой тег
docker-compose up -d --build

Полезные команды

# Перезапустить всё
docker-compose restart

# Перезапустить только backend
docker-compose restart backend

# Войти в контейнер backend
docker-compose exec backend bash

# PostgreSQL shell
docker-compose exec postgres psql -U spectech -d spectech

# Посмотреть использование ресурсов
docker stats

## Шифрование секретов интеграций (ENCRYPTION_KEY)

В production обязателен отдельный ключ `ENCRYPTION_KEY` (Fernet) — без него
backend не стартует (fail-fast в lifespan). Генерация ключа, ротация через
`ENCRYPTION_KEY_PREVIOUS` с обязательной перешифровкой
(`scripts/rotate_company_secrets.py`), бэкап ключа ОТДЕЛЬНО от бэкапа БД и
перенос dev-БД в прод — см. **[docs/ENCRYPTION.md](ENCRYPTION.md)**.

## Переполнение системного диска (инцидент 18.11.2026)

Стек чуть не встал: на C: осталось **1.6 ГБ** из 120. Postgres получил бы ошибку
записи, Docker VM остановилась бы, бэкапы перестали бы писаться.

Мониторинг этого не видел. `DiskSpaceLow` проверяет только `mountpoint="/"` —
корень виртуальной машины Docker, который лежит на D:. Системный диск Windows
в проверку не входит вовсе. Метрика для него есть: node-exporter отдаёт
`/mnt/host/c` (fstype 9p) с реальной заполненностью хоста — на момент инцидента
1.4% свободного, после чистки 10.6%.

Что освобождено и куда перенесено:

| Действие | Освобождено на C: |
|---|---|
| Кэш npm, Temp, кэши установщиков | 4.4 ГБ |
| `Downloads` → `D:\Downloads` + junction на прежнем пути | 5.6 ГБ |

Итого 1.6 → 11.5 ГБ. Junction создан только после проверки, что источник пуст:
иначе файлы остались бы в двух местах, что хуже, чем не делать вовсе.

Важно про чистку Docker: `docker builder prune` освобождает место **внутри диска
VM**, а сам диск VM находится на D: (`DockerData`). Для переполнения C: это
бесполезно — 20 ГБ освободятся не там, где нужно. Место на C: возвращают только
операции с файлами самого C:.

Что остаётся невидимым для алертов: заполненность C:. Пока правило не покрывает
`/mnt/host/c`, инцидент может повториться без предупреждения.
