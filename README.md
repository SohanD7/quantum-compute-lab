# ⚛️ Quantum Compute Labs — CSS 436

![AWS](https://img.shields.io/badge/AWS-EKS%20%7C%20EC2%20%7C%20ECR-orange?logo=amazon-aws)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Indexed%20Jobs-blue?logo=kubernetes)
![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED?logo=docker)
![Redis](https://img.shields.io/badge/Redis-Pub%2FSub-DC382D?logo=redis)
![Prometheus](https://img.shields.io/badge/Prometheus-Scraping-E6522C?logo=prometheus)
![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?logo=grafana)

Modernizing a legacy Fortran physics engine computing a 2D locus of the **Schrödinger Wave Equation** — containerized, parallelized on Amazon EKS, brokered via EC2 Redis, observed with Prometheus & Grafana, and visualized in real-time with Python Matplotlib.

---

## 🏗️ Architecture
```
Local Laptop (Matplotlib 3D Visualizer)
        ↕  Subscribes to wave_channel
Amazon EC2 — Redis Pub/Sub Broker (Port 6379)
        ↑  Publishes JSON matrix payloads
Amazon EKS Cluster (us-west-2)
  └── Kubernetes Indexed Job (10 completions, parallelism 5)
        ├── Worker Pod 0-9  [ Fortran/Python worker | node-exporter sidecar :9100 ]
        ↓  Prometheus scrapes :9100 via Kubernetes Service Discovery
        ↓  Grafana visualizes via PromQL (NodePort 30007)
        ↓  Results written to hostPath Persistent Volume
```

---

## 📁 Structure
```
quantum-compute-lab/
├── worker/
│   ├── schrodinger.f90          # Fortran source (Schrödinger wave equation)
│   ├── parallel_worker.py       # f2py wrapper + Redis publisher
│   └── Dockerfile               # Multi-stage: gfortran builder + slim runtime
├── k8s/
│   ├── configmap.yaml
│   ├── storage.yaml             # Static hostPath PV + PVC
│   ├── pvc-aggregator.yaml
│   ├── indexed-job.yaml         # 10 completions, parallelism 5, native sidecar
│   ├── worker-demo-deployment.yaml
│   └── monitoring/
│       ├── prometheus-rbac.yaml
│       ├── prometheus-config.yaml
│       ├── prometheus-deployment.yaml
│       ├── grafana-datasource.yaml
│       └── grafana-deployment.yaml
└── visualizer.py                # Matplotlib 3D surface animation client
```

---

## 🚀 Phases

| Phase | Component | Highlights |
|---|---|---|
| **D1** | Dockerized Fortran Worker | Fixed 3 Fortran bugs, f2py compilation, multi-stage Dockerfile, pushed to ECR as `linux/amd64` |
| **D2** | EKS Indexed Job | 3-node `t3.medium` cluster, 10 completions / parallelism 5, hostPath PV+PVC, native K8s 1.29 sidecar pattern |
| **D3** | EC2 Redis Broker | Ubuntu 22.04, Redis bound to `0.0.0.0`, 10 workers published ~234KB JSON payloads, job completed in **16 seconds** |
| **D4** | Prometheus + Grafana | Kubernetes SD ConfigMap, node-exporter sidecars on :9100, Grafana NodePort 30007, CPU/memory dashboard |
| **D5** | Matplotlib Visualizer | Threaded Redis subscriber, live rotating 3D surface plot, tiled screen recording with Grafana |

---

## 🔑 Key Engineering Decisions

| Problem | Solution |
|---|---|
| Mac ARM → EKS x86 mismatch | `docker build --platform=linux/amd64` |
| f2py crashes on special characters | Added `locales` + `LANG=en_US.UTF-8` to builder stage |
| EKS Auto Mode CSI topology key error | Static `hostPath` PV — no cloud provisioner needed |
| EBS `WaitForFirstConsumer` deadlock | Static PV bypasses StorageClass entirely |
| Sidecar blocking job completions | K8s 1.29 native sidecar: `restartPolicy: Always` in initContainers |
| Prometheus `no route to host` :9100 | Added VPC CIDR `172.31.0.0/16` inbound rule to EKS node security group |

---

## 📊 Performance

| Metric | Value |
|---|---|
| Grid size | 100 × 100 |
| Fortran compute time per worker | ~0.1ms |
| JSON payload per worker | ~234 KB |
| Total job completion (10 workers) | **16 seconds** |
| Redis channel | `wave_channel` |

## 🎥 D5 Demo Video
[▶️ Watch Tiled Demo — Matplotlib + Grafana (Google Drive)] https://drive.google.com/file/d/1TvF71ZqMr1odVhZMJ4-nAYu8R_MFTyMm/view?usp=drive_link

> ⚠️ AWS infrastructure has been spun down to avoid costs. All source code, manifests, and the D5 demo video are preserved in this repository.
