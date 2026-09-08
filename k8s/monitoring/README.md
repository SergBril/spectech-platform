# Мониторинг и алертинг для spectech-platform

## Компоненты

- **Prometheus** - сбор метрик Kubernetes
- **Grafana** - визуализация (dashboards + Explore)
- **Alertmanager** - обработка алертов
- **Loki** - централизованное логирование
- **Promtail** - сбор логов с pod'ов

## Алерты

### cert-manager
- `CertificateExpiringSoon` - сертификат истекает через 14 дней
- `CertificateNotReady` - сертификат не Ready > 10 мин
- `ClusterIssuerNotReady` - ClusterIssuer не Ready > 15 мин

### Loki
- `LokiRequestErrors` - >10% запросов возвращают 5xx
- `LokiRequestPanic` - Loki panic

### Тестовые
- `TestTelegramAlert` - для проверки уведомлений

## Уведомления

### Telegram (нативный receiver)
- **Secret**: `telegram-credentials`  # pragma: allowlist secret
- Receivers: `telegram-warning`, `telegram-critical`
- Parse mode: MarkdownV2

**Важно:** api.telegram.org может быть заблокирован в некоторых регионах (Россия).
Для production используйте сервер за рубежом.

## Доступ к UI

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
