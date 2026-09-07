# 🏆 Week 10 Summary: Kubernetes Production Deployment

## Overview

Week 10 was dedicated to transforming SpectechPlatform from a Docker Compose application into a **production-grade Kubernetes deployment** with enterprise-level features:

- ✅ Full Kubernetes cluster setup
- ✅ Stateful services with persistent storage
- ✅ Ingress Controller with TLS termination
- ✅ Helm chart packaging
- ✅ Observability stack (Prometheus + Grafana)
- ✅ Auto-scaling with HPA

---

## Day-by-Day Achievements

### Day 1: Kubernetes Setup & Basics
- ✅ Enabled Kubernetes in Docker Desktop (v1.36.1)
- ✅ Created `spectech` namespace
- ✅ Created first Pod (test Nginx)
- ✅ Created backend Deployment (2 replicas)
- ✅ Created backend Service (ClusterIP)
- ✅ Verified self-healing (deleted pods → auto-recreated)
- ✅ Configured port-forwarding for local access
- **Key concept:** Pods, Deployments, Services, Namespaces

### Day 2: Stateful Services
- ✅ Created K8s Secret for credentials (`db-credentials`)
- ✅ Created ConfigMap for backend configuration
- ✅ PostgreSQL StatefulSet with 5Gi PVC
- ✅ Redis Deployment with health probes
- ✅ MinIO StatefulSet with 10Gi PVC
- ✅ Added `enableServiceLinks: false` to fix env conflicts
- ✅ Increased backend memory to 2Gi (fixed OOM Kill)
- ✅ Added `startupProbe` (5-minute startup timeout)
- **Key concept:** StatefulSets, PVCs, Secrets, ConfigMaps

### Day 3: Ingress Controller + TLS
- ✅ Installed NGINX Ingress Controller v1.11.2
- ✅ Created K8s TLS Secret from self-signed certificate
- ✅ Configured Ingress routing:
  - `/api/*` → backend:8000
  - `/ws/*` → backend:8000 (WebSocket)
  - `/` → frontend:80 (Next.js)
- ✅ HTTP → HTTPS redirect (308 Permanent)
- ✅ TLS termination at Ingress level
- **Key concept:** Ingress, TLS termination, LoadBalancer

### Day 4: Frontend Deployment
- ✅ Created Frontend Deployment (Next.js, 2 replicas)
- ✅ Created Frontend Service (ClusterIP)
- ✅ Updated Ingress for frontend routing
- ✅ Verified full stack: Frontend → Backend → DB
- ✅ Tagged Docker image correctly (`spectech-frontend:latest`)
- **Key concept:** Complete production stack in K8s

### Day 5: Helm Charts
- ✅ Installed Helm v3.16.1
- ✅ Created `spectech` Helm chart with:
  - Chart.yaml (metadata, version 0.1.0)
  - values.yaml (all configuration parameters)
  - 13 templates (Deployments, Services, PVCs, Ingress, Secret)
  - `_helpers.tpl` (reusable labels)
- ✅ Configured pre-commit to exclude Helm templates from YAML checks
- ✅ Tested `helm install`, `upgrade`, `rollback`, `uninstall`
- ✅ Parametrized deployment: `--set backend.replicaCount=3`
- **Key concept:** Helm packaging, templating, releases

### Day 6: Observability Stack
- ✅ Installed `kube-prometheus-stack` via Helm
- ✅ Prometheus with 5Gi persistent storage (2-day retention)
- ✅ Grafana with 2Gi storage (admin/spectech2026)
- ✅ Alertmanager with 1Gi storage
- ✅ Kube State Metrics + Node Exporter
- ✅ Created ServiceMonitor for backend metrics
- ✅ Created PrometheusRule with 5 alerts:
  - BackendHighErrorRate (>5% 5xx errors)
  - BackendPodRestarting (>3 restarts/hour)
  - BackendHighLatency (P95 > 1s)
  - PostgresDown
  - RedisDown
- ✅ Imported Grafana dashboards:
  - Kubernetes Cluster (ID: 15661)
  - Kubernetes Pods (ID: 6417)
  - Node Exporter (ID: 1860)
- **Key concept:** Prometheus, Grafana, Alertmanager, CRDs

### Day 7: Horizontal Pod Autoscaler
- ✅ Installed Metrics Server (with `--kubelet-insecure-tls`)
- ✅ Created backend HPA:
  - Min 2, Max 10 replicas
  - CPU target: 50%
  - Memory target: 70%
  - Smart scale-down (5-minute stabilization)
  - Fast scale-up (immediate)
- ✅ Installed Prometheus Adapter for custom metrics
- ✅ Verified CPU-based auto-scaling:
  - 2 pods → 4 pods at 79% CPU under load
  - Auto scale-down after load completes
- ✅ Prometheus collects metrics from backend (verified in UI)
- **Key concept:** HPA, Metrics Server, auto-scaling

---

## Final Architecture

                ┌──────────────────────┐
                │  Internet (HTTPS)    │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │  Ingress Controller  │
                │   (TLS termination)  │
                │   HTTP→HTTPS (308)   │
                └──────────┬───────────┘
                           ↓
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
     ┌────────┐      ┌────────┐        ┌────────┐
     │Frontend│      │Backend │   ...  │Backend │
     │(2 pods)│      │(2-10)  │        │(pod N) │
     │Next.js │      │FastAPI │        │        │
     └────┬───┘      └────┬───┘        └────┬───┘
          │               │                 │
          │               └────────┬────────┘
          │                        ↓
          │         ┌──────────────┼──────────────┐
          │         ↓              ↓              ↓
          │    ┌────────┐     ┌────────┐     ┌────────┐
          │    │Postgres│     │ Redis  │     │ MinIO  │
          │    │ (1 pod)│     │ (1 pod)│     │ (1 pod)│
          │    │ 5Gi PVC│     │        │     │10Gi PVC│
          │    └────────┘     └────────┘     └────────┘
          │
          └──→ Monitored by:
               ┌────────────────────┐
               │ Prometheus Stack   │
               │ (monitoring ns)    │
               │ • Server + Grafana │
               │ • Alertmanager     │
               │ • ServiceMonitors  │
               │ • PrometheusRules  │
               └────────────────────┘


---

## Resource Summary

### Kubernetes Resources
| Resource | Count | Namespace |
|----------|-------|-----------|
| Pods | 7-11 (with HPA) | spectech |
| Deployments | 3 (backend, frontend, redis) | spectech |
| StatefulSets | 2 (postgres, minio) | spectech |
| Services | 5 (ClusterIP) | spectech |
| PVCs | 2 (15Gi total) | spectech |
| Secrets | 2 (db-credentials, spectech-tls) | spectech |
| ConfigMaps | 1 (backend-config) | spectech |
| Ingress | 1 (with TLS) | spectech |
| ServiceMonitors | 1 | spectech |
| PrometheusRules | 1 (5 alerts) | spectech |
| HPA | 1 | spectech |

### Monitoring Stack (monitoring namespace)
| Component | Replicas | Storage |
|-----------|----------|---------|
| Prometheus | 1 | 5Gi |
| Grafana | 1 | 2Gi |
| Alertmanager | 1 | 1Gi |
| Kube State Metrics | 1 | - |
| Node Exporter | 1 (DaemonSet) | - |
| Prometheus Operator | 1 | - |
| Prometheus Adapter | 1 | - |

---

## Helm Chart Structure


helm/spectech/
├── Chart.yaml # Chart metadata
├── values.yaml # Default configuration
├── values-prod.yaml.example # Production template
└── templates/
├── _helpers.tpl # Reusable labels
├── backend-deployment.yaml
├── backend-service.yaml
├── frontend-deployment.yaml
├── frontend-service.yaml
├── postgres-statefulset.yaml
├── postgres-service.yaml
├── postgres-pvc.yaml
├── redis-deployment.yaml
├── redis-service.yaml
├── minio-statefulset.yaml
├── minio-service.yaml
├── minio-pvc.yaml
├── ingress.yaml
└── secret.yaml


---

## Key Commands

### Helm Operations
```bash
# Install full stack
helm install spectech ./helm/spectech -n spectech

# Upgrade with custom values
helm upgrade spectech ./helm/spectech -n spectech --set backend.replicaCount=5

# Rollback to previous version
helm rollback spectech 1 -n spectech

# View release history
helm history spectech -n spectech

# Uninstall
helm uninstall spectech -n spectech

# Prometheus UI
kubectl port-forward -n monitoring svc/kube-prometheus-kube-prome-prometheus 9090:9090

# Grafana UI
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3001:80

# Alertmanager UI
kubectl port-forward -n monitoring svc/kube-prometheus-kube-prome-alertmanager 9093:9093

# Backend API
kubectl port-forward -n spectech svc/backend 8000:8000

# Frontend
kubectl port-forward -n spectech svc/frontend 3000:3000

# View HPA status
kubectl get hpa -n spectech -w

# View pod resource usage
kubectl top pods -n spectech

# View Prometheus targets
kubectl port-forward -n monitoring svc/kube-prometheus-kube-prome-prometheus 9090:9090
# http://localhost:9090/targets

# Check custom metrics API
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1"
