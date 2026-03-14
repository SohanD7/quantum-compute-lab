# Quantum Compute Labs — CSS 436

Modernizing a legacy Fortran physics engine using Docker, Amazon EKS, EC2 Redis, Prometheus, Grafana, and Python Matplotlib.

## Architecture
Local Matplotlib Visualizer ↔ EC2 Redis Broker ← Amazon EKS Compute Cluster

## Phases
| Phase | Description |
|---|---|
| D1 | Multi-stage Docker image, f2py Fortran compilation, Amazon ECR |
| D2 | EKS Indexed Job (10 completions, parallelism 5), PV/PVC |
| D3 | EC2 Redis Pub/Sub broker, JSON matrix payloads |
| D4 | Prometheus service discovery, node-exporter sidecars, Grafana dashboard |
| D5 | Matplotlib 3D surface animation, tiled screen recording |

## Structure
\`\`\`
quantum-compute-lab/
├── worker/
│   ├── schrodinger.f90        # Corrected Fortran source
│   ├── parallel_worker.py     # Kubernetes job worker
│   └── Dockerfile             # Multi-stage build
├── k8s/
│   ├── configmap.yaml
│   ├── storage.yaml
│   ├── pvc-aggregator.yaml
│   ├── indexed-job.yaml
│   ├── worker-demo-deployment.yaml
│   └── monitoring/
│       ├── prometheus-rbac.yaml
│       ├── prometheus-config.yaml
│       ├── prometheus-deployment.yaml
│       ├── grafana-datasource.yaml
│       └── grafana-deployment.yaml
└── visualizer.py              # Matplotlib Redis subscriber
\`\`\`

## Running the Visualizer
\`\`\`bash
pip install redis numpy matplotlib
python visualizer.py --host <EC2_PUBLIC_IP>
\`\`\`
