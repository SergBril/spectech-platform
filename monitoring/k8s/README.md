# Артефакты для Kubernetes, не для Docker Compose

Эти файлы относятся к развёртыванию в Kubernetes и в текущем стеке
(Docker Compose) не применяются.

- `grafana-dashboard-crd.json` — экспорт дашборда из Grafana v13 в формате
  `dashboard.grafana.app/v2` (kind: Dashboard). File provisioning Grafana
  ожидает классический JSON дашборда, поэтому такой файл не загружается:
  в логе было "Dashboard title cannot be empty" каждые 10 секунд.
- `../servicemonitors/backend-servicemonitor.yaml` — ServiceMonitor для
  kube-prometheus-stack.

Запросы в них используют метки `namespace="spectech", app="backend"`.
В Compose метки другие: `job="spectech-backend"`, `instance="backend:8000"`.
Рабочий дашборд лежит в `../grafana/dashboards/backend-dashboard.json`.
