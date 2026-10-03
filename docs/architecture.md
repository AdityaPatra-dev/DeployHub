# DeployHub Architecture

This document explains how DeployHub is structured, how a deployment flows through the system, and why key design decisions were made.

**Contents**
1. [Purpose](#1-purpose)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Components](#3-components)
4. [Data Model](#4-data-model)
5. [Deployment Flow](#5-deployment-flow)
6. [Deployment State Machine](#6-deployment-state-machine)
7. [Kubernetes Layout](#7-kubernetes-layout)
8. [CI/CD and Rollback](#8-cicd-and-rollback)
9. [Security Considerations](#9-security-considerations)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Development Environments](#11-development-environments)
12. [Evolution by Phase](#12-evolution-by-phase)

---

## 1. Purpose

DeployHub lets a developer connect a GitHub repository and receive a live public URL without managing infrastructure. DeployHub is the **control layer** that connects existing tools into one workflow:

```mermaid
flowchart LR
    A[GitHub] --> B[Docker]
    B --> C[Registry]
    C --> D[Kubernetes]
    D --> E[Monitoring]
    D --> F[Public URL]
```

It does not build its own container runtime, scheduler, Git implementation, or monitoring system. Its value is the orchestration between them.

---

## 2. High-Level Architecture

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

There are two halves:
- **Control plane:** DeployHub itself (UI, API, database, queue, workers).
- **Data plane:** the Kubernetes cluster where users' applications actually run.

---

## 3. Components

### 3.1 Frontend (React + TypeScript + Vite + Tailwind)
The web dashboard.
- GitHub login
- Repository selection
- Deployment configuration (branch, port, build method)
- Deployment status and live logs
- Application list and details

### 3.2 Backend API (Python + FastAPI)
The control plane.
- Authentication and authorization
- Project and deployment management
- GitHub integration (OAuth, repository listing, webhooks)
- Creating deployment jobs and exposing status and logs
- Communicating with Kubernetes

| Module | Responsibility |
| :--- | :--- |
| `api/` | HTTP endpoints (auth, projects, deployments, logs) |
| `models/` | SQLAlchemy database models |
| `schemas/` | Request and response validation |
| `services/github.py` | GitHub OAuth, repository access, webhooks |
| `services/docker.py` | Image builds and registry pushes |
| `services/kubernetes.py` | Creating and updating cluster resources |
| `services/deployment.py` | Orchestrates the full deployment flow |
| `workers/` | Background job execution |

### 3.3 Database (PostgreSQL)
Stores users, projects, and deployments. See [Data Model](#4-data-model).

### 3.4 Queue and Workers (Redis + Celery)
Builds and deployments take minutes, so they must not block API requests. The API creates a deployment record, places a job on the queue, and immediately returns a deployment ID. Workers run the build and deploy steps in the background.

### 3.5 Build System (Docker)
Clones the repository, detects the project type, builds a Docker image, and tags it with the Git commit SHA.

```mermaid
flowchart TD
    R[Cloned Repository] --> D{Dockerfile exists?}
    D -- Yes --> U[Use the user's Dockerfile]
    D -- No --> P{Project type?}
    P -- "requirements.txt / pyproject.toml" --> PY[Generate Python Dockerfile]
    P -- "package.json" --> NO[Generate Node.js Dockerfile]
    P -- Unknown --> ERR[Fail: unsupported project]
    U --> B[docker build]
    PY --> B
    NO --> B
    B --> T["Tag image with commit SHA"]
```

Initial supported types: Python, Node.js, and user-provided Dockerfiles.

### 3.6 Container Registry (GHCR)
Stores built images. Images are tagged with the commit SHA (for example `my-app:a81f92d`), never relying only on `latest`.

### 3.7 Kubernetes
Runs user applications. For each deployment DeployHub generates a **Deployment** (pods, limits, probes), a **Service** (stable networking), and an **Ingress** (public routing). See [Kubernetes Layout](#7-kubernetes-layout).

### 3.8 Monitoring (Prometheus + Grafana)
Prometheus collects CPU, memory, request, latency, error, and restart metrics. Grafana provides dashboards. Loki can be added later for centralized logs.

---

## 4. Data Model

```mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    PROJECT ||--o{ DEPLOYMENT : has

    USER {
        int id PK
        int github_id
        string username
        string email
        datetime created_at
    }
    PROJECT {
        int id PK
        int user_id FK
        string name
        string repository_url
        string branch
        datetime created_at
    }
    DEPLOYMENT {
        int id PK
        int project_id FK
        string commit_sha
        string image
        string status
        string url
        datetime created_at
        datetime finished_at
    }
```

`status` is one of: `QUEUED`, `CLONING`, `BUILDING`, `PUSHING`, `DEPLOYING`, `HEALTH_CHECK`, `RUNNING`, `FAILED`, `STOPPED`.

---

## 5. Deployment Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant Q as Redis Queue
    participant W as Worker
    participant R as Registry
    participant K as Kubernetes

    U->>API: POST /api/projects/{id}/deploy
    API->>API: Create Deployment record (QUEUED)
    API-->>U: deployment_id, status QUEUED
    API->>Q: Enqueue job
    Q->>W: Worker picks up job
    W->>W: Clone repository, detect project type
    W->>W: Build Docker image (tag = commit SHA)
    W->>R: Push image
    W->>K: Apply Deployment, Service, Ingress
    K->>K: Run liveness and readiness probes
    W->>API: Update status to RUNNING or FAILED
    U->>API: GET /api/deployments/{id}
    API-->>U: status, url, commit_sha
```

Because the API returns immediately, the frontend can poll the status endpoint or receive live updates over SSE/WebSockets.

---

## 6. Deployment State Machine

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

A multi-state lifecycle, instead of a plain "deploy → running", shows exactly where a failure happened and what the user should see.

---

## 7. Kubernetes Layout

### 7.1 Request path to a running app

```mermaid
flowchart LR
    Net([Internet]) --> ING["Ingress<br/>abc123.deployhub.example"]
    ING --> SVC["Service<br/>port 80"]
    SVC --> P1["Pod 1<br/>container port 8000"]
    SVC --> P2["Pod 2<br/>container port 8000"]
    DEP[Deployment] -. manages .-> P1
    DEP -. manages .-> P2
```

- **Deployment:** keeps the desired number of pods running and defines the image, resource limits, and health probes.
- **Service:** gives pods a stable address even when individual pods are replaced.
- **Ingress:** routes `<random-id>.deployhub.example` to the right Service.

Manifests are generated dynamically (or from Helm templates), never hard-coded per project.

### 7.2 Multi-tenant isolation

Each user gets a dedicated namespace.

```mermaid
flowchart TD
    subgraph CLUSTER["Kubernetes Cluster"]
        subgraph N1["Namespace user-101"]
            A1[app-1]
            A2[app-2]
        end
        subgraph N2["Namespace user-102"]
            B1[app-1]
        end
        subgraph N3["Namespace user-103"]
            C1[app-1]
        end
    end
```

Later additions: NetworkPolicies, ResourceQuotas, LimitRanges, Pod Security Admission, and dedicated node pools.

### 7.3 Health checks and resource limits

| Setting | Purpose |
| :--- | :--- |
| Liveness probe (`/health`) | Is the app alive? Restart it if not. |
| Readiness probe (`/health`) | Can the app receive traffic? Hold traffic until it can. |
| CPU request / limit | `100m` / `500m` |
| Memory request / limit | `128Mi` / `512Mi` |

### 7.4 Autoscaling (later phase)

Horizontal Pod Autoscaler policy: minimum 1 replica, maximum 5, target CPU 70%.

```mermaid
flowchart LR
    L["Low traffic<br/>2 pods"] --> H["High load<br/>CPU above 70%"] --> S["HPA scales up<br/>4 pods"]
```

---

## 8. CI/CD and Rollback

### 8.1 Pipeline for DeployHub itself

```mermaid
flowchart LR
    Push[git push] --> Test[Lint and Tests]
    Test --> Build[Docker Build]
    Build --> Scan[Trivy Scan]
    Scan --> Img[Push Image]
    Img --> Dep[Deploy]
    Scan -- CRITICAL found --> Block[Block deployment]
```

### 8.2 Rollback

Because every image is tagged with an immutable commit SHA, rolling back means redeploying a previous image.

```mermaid
flowchart LR
    V1["v1<br/>sha 3f9a1c2<br/>working"] --> V2["v2<br/>sha 7b2d4e8<br/>working"]
    V2 --> V3["v3<br/>sha a81f92d<br/>broken"]
    V3 -. rollback .-> V2R["Redeploy v2<br/>RUNNING"]
```

### 8.3 GitHub webhook auto-deploy

```mermaid
flowchart LR
    Dev([Developer]) -- git push --> GH[GitHub]
    GH -- webhook --> API[DeployHub API]
    API --> V{Signature valid?}
    V -- No --> X[Reject request]
    V -- Yes --> D[Create deployment]
    D --> B[Build and deploy]
```

---

## 9. Security Considerations

DeployHub executes user-supplied code, so isolation is essential.

- No privileged containers.
- Never mount `/var/run/docker.sock` into user containers.
- CPU, memory, and process limits on every application.
- Non-root containers where possible.
- Per-user Kubernetes namespaces (later: NetworkPolicies and ResourceQuotas).
- Image scanning with Trivy: block CRITICAL, warn on HIGH.
- Verify GitHub webhook signatures using the webhook secret.
- Never expose host credentials to user containers.
- Never store secrets in Git, Docker images, logs, or normal API responses; use Kubernetes Secrets.
- Rate limit public endpoints (for example login 10/min, deploy 5/min, logs 60/min).
- Enforce authorization: users can only access their own projects, deployments, logs, and variables.

---

## 10. Key Design Decisions

| Decision | Reasoning |
| :--- | :--- |
| **Use Kubernetes instead of a custom scheduler** | Scheduling, restarts, scaling, and networking are solved problems. DeployHub's value is the orchestration layer. |
| **Use Docker/containerd instead of a custom runtime** | Standard, secure, and widely supported. |
| **Use a job queue for builds** | Builds take minutes; the API must respond immediately. |
| **Tag images with the Git commit SHA** | Immutable tags make deployments reproducible and rollbacks reliable. |
| **Generate manifests dynamically (or via Helm)** | Hard-coding YAML per project does not scale. |
| **One namespace per user** | Simple tenant isolation to start; NetworkPolicies and quotas can be layered on later. |
| **Build the core engine before the frontend** | Proves the Repository → Build → Container → URL concept first. |
| **Start with Docker, then move to Kubernetes** | Every phase produces a working system and keeps scope manageable. |

---

## 11. Development Environments

| Environment | Setup |
| :--- | :--- |
| **Local control plane** | Docker Compose: frontend, backend, PostgreSQL, Redis, Prometheus, Grafana |
| **Local Kubernetes** | Kind (lightweight), Minikube, or Docker Desktop Kubernetes |
| **Cloud** | AWS (EC2-based cluster first, EKS later), provisioned with Terraform |

---

## 12. Evolution by Phase

```mermaid
flowchart LR
    MVP["MVP<br/>Repo, Docker build,<br/>Docker run, URL"] --> V2["Version 2<br/>GitHub OAuth + webhooks,<br/>Registry, Kubernetes,<br/>Ingress, rollback"]
    V2 --> V3["Version 3<br/>CI/CD, Trivy, HPA,<br/>Prometheus + Grafana,<br/>multi-user isolation"]
```

See the [README roadmap](../README.md#-implementation-roadmap) for the phase-by-phase plan.
