# ☁️ DeployHub

<div align="center">

### Automated Self-Service Application Deployment Platform
*Inspired by Render and Railway — From Source Code to Production URL on Kubernetes*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Architecture: Kubernetes](https://img.shields.io/badge/Orchestration-Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![Runtime: Docker](https://img.shields.io/badge/Containers-Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Status: In Development](https://img.shields.io/badge/Status-Active%20Development-success?style=flat-square)]()

</div>

---

## 📌 Overview

**DeployHub** is a self-service PaaS-style deployment platform designed to remove cloud infrastructure friction for developers.

The core philosophy is simple:
> **Developers should care about their application, not the infrastructure required to run it.**

A developer connects a GitHub repository, configures a few settings, clicks **Deploy**, and receives a live public URL. DeployHub handles everything in between: detecting the runtime, building a Docker image, pushing it to a registry, creating Kubernetes resources, running health checks, and streaming logs.

```mermaid
flowchart LR
    A[GitHub Repository] --> B[Detect Project Type]
    B --> C[Build Docker Image]
    C --> D[Push to Registry]
    D --> E[Deploy to Kubernetes]
    E --> F[Health Check]
    F --> G[Public URL]
```

DeployHub is built as a Cloud/DevOps engineering portfolio project, but is designed to be usable by other developers.

> **What DeployHub builds vs. reuses:** DeployHub does **not** implement its own container runtime, scheduler, Git, or monitoring system. It uses Docker, Kubernetes, GitHub, and Prometheus/Grafana. The project is the **orchestration and control layer** that connects them into one developer experience.

---

## 🚀 Features

- **GitHub Integration:** Deploy from a repository and branch; auto-deploy on `git push` via webhooks.
- **Automated Containerization:** Detects Python, Node.js, or an existing Dockerfile and builds an image.
- **Kubernetes Orchestration:** Generates Deployments, Services, and Ingress for each application.
- **Deployment Lifecycle Tracking:** Every deployment moves through a clear state machine.
- **Live Logs & Health Checks:** Streamed build/deploy logs and liveness/readiness probes.
- **Rollbacks & Environment Variables:** Redeploy a previous image; manage secrets securely.
- **Monitoring & Autoscaling:** Prometheus/Grafana metrics and Horizontal Pod Autoscaling.

> Features marked 📅 in the [Project Status](#-project-status) table are planned, not yet implemented.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    Dev([Developer]) --> UI[React Dashboard]
    UI --> API[FastAPI Control API]

    subgraph CP["Control Plane"]
        API --> DB[(PostgreSQL)]
        API --> Q[(Redis Queue)]
        Q --> W[Celery Workers]
    end

    API <--> GH[GitHub API and Webhooks]
    W --> BUILD[Docker Build]
    BUILD --> REG[Container Registry - GHCR]
    W --> K8S[Kubernetes API]
    REG --> K8S

    subgraph CL["Kubernetes Cluster"]
        K8S --> PODS[Application Pods]
        ING[Ingress] --> SVC[Service] --> PODS
        PODS -. metrics .-> PROM[Prometheus]
        PROM --> GRAF[Grafana]
    end

    Visitor([End User]) --> ING
```

For a component-by-component explanation, see [docs/architecture.md](docs/architecture.md).

---

## ⚙️ Deployment Lifecycle

Every deployment moves through explicit states, which makes failures easy to locate and debug.

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> CLONING
    CLONING --> BUILDING
    BUILDING --> PUSHING
    PUSHING --> DEPLOYING
    DEPLOYING --> HEALTH_CHECK
    HEALTH_CHECK --> RUNNING
    CLONING --> FAILED
    BUILDING --> FAILED
    PUSHING --> FAILED
    DEPLOYING --> FAILED
    HEALTH_CHECK --> FAILED
    RUNNING --> STOPPED
```

---

## 🧰 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS |
| **Backend** | Python, FastAPI, SQLAlchemy |
| **Database** | PostgreSQL |
| **Queue / Workers** | Redis + Celery |
| **Authentication** | GitHub OAuth |
| **Containers** | Docker, Docker Compose |
| **Registry** | GitHub Container Registry (GHCR) |
| **Orchestration** | Kubernetes (Kind for local development), Helm |
| **Routing** | Kubernetes Ingress with wildcard subdomains |
| **CI/CD** | GitHub Actions |
| **Monitoring** | Prometheus, Grafana, Loki |
| **Security** | Trivy, NetworkPolicies, ResourceQuotas |
| **Infrastructure as Code** | Terraform |
| **Cloud** | AWS (EC2 / EKS, VPC, IAM) |

---

## 📋 Implementation Roadmap

Each phase produces a working system. The platform is built in stages, smallest working version first.

| Phase | Milestone | Focus Areas |
| :---: | :--- | :--- |
| **01** | **Local Deployment Engine** | Git clone, project detection, `docker build` and `docker run` |
| **02** | **Docker Pipeline** | Dockerfile generation, health checks, deployment state machine |
| **03** | **Kubernetes Integration** | Deployment, Service, Ingress, per-user namespaces |
| **04** | **API & Web Dashboard** | FastAPI, PostgreSQL, React UI, live log streaming (SSE/WebSockets) |
| **05** | **GitHub Integration** | OAuth login, repository selection, webhooks, auto-deploy |
| **06** | **CI/CD** | GitHub Actions, registry pushes, commit-SHA image tags, Trivy scans |
| **07** | **Observability** | Prometheus, Grafana, health alerts, platform metrics |
| **08** | **Autoscaling & Hardening** | HPA, rollback, secrets, resource limits, rate limiting |
| **09** | **Cloud Infrastructure** | Terraform, AWS (EC2/EKS), production deployment |

---

## 📊 Project Status

| Feature | Status |
| :--- | :---: |
| Clone repo + Docker build + run container | 🚧 In progress |
| Deployment state machine | 📅 Planned |
| FastAPI backend + PostgreSQL | 📅 Planned |
| Web dashboard | 📅 Planned |
| Kubernetes deployment | 📅 Planned |
| GitHub OAuth + webhooks | 📅 Planned |
| CI/CD pipeline | 📅 Planned |
| Prometheus / Grafana monitoring | 📅 Planned |
| Autoscaling (HPA) | 📅 Planned |
| Terraform + AWS | 📅 Planned |

✅ Done  ·  🚧 In progress  ·  📅 Planned

---

## 🗂️ Repository Structure

```text
deployhub/
├── frontend/          # React + TypeScript dashboard
├── backend/           # FastAPI control API, services, workers
│   └── app/
│       ├── api/       # auth, projects, deployments, logs
│       ├── models/
│       ├── schemas/
│       ├── services/  # github, docker, kubernetes, deployment
│       └── workers/   # background build/deploy jobs
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   └── terraform/
├── helm/              # Helm chart for DeployHub
├── docs/              # Architecture, API, security, and more
├── .github/workflows/ # CI/CD pipelines
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

## 🚀 Getting Started

> Setup instructions will be added as Phase 01 is completed.

Planned local workflow:

```bash
git clone https://github.com/AdityaPatra-dev>/deployhub.git
cd deployhub
docker compose up
```

| Service | URL |
| :--- | :--- |
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Grafana | http://localhost:3001 |

---

## 🔒 Security

DeployHub runs code supplied by users, so security is a core design concern: non-root containers, no privileged mode, no Docker socket exposure, CPU/memory limits, per-user namespaces, image scanning with Trivy, signed webhook verification, and rate limiting. See the security section of [docs/architecture.md](docs/architecture.md#9-security-considerations).

---

## 📚 Documentation

- [Architecture](docs/architecture.md)
- [DeployHub Development Specification](./DeployHub_Development_Specification.md)

More documents (API reference, database, deployment lifecycle) will be added as each phase is built.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
