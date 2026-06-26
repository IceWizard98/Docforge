# DocForge

AI-first SaaS platform for intelligent enterprise document drafting, review, and collaboration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                       │
│  Tiptap/ProseMirror Editor + Pinia + Vue Router          │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP / WebSocket
┌──────────────▼──────────────────────────────────────────┐
│                  API (FastAPI)                            │
│  Auth ── Routes ── Services ── Core Domain                │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
│  PostgreSQL  │ │    Redis   │ │     MinIO      │
│  + pgvector  │ │   (Queue)  │ │  (File Store)  │
└──────────────┘ └────────────┘ └────────────────┘
       ▲                           ▲
       │      ┌────────────────────┘
       │      │
┌──────┴──────▼──────────────────────────────────────────┐
│                  Workers (Celery)                        │
│  Document Processing ── OCR ── LLM Integration           │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, Vite 6, Tiptap/ProseMirror, Pinia, Vue Router, TailwindCSS 4 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 + pgvector |
| Queue | Redis 7 + Celery |
| Storage | MinIO (S3-compatible) |
| Auth | JWT (python-jose + passlib) |
| LLM | OpenAI / Anthropic (multi-provider) |
| Container | Docker, Docker Compose |
| Orchestration | Kubernetes (optional) |

## Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 20+
- Just (command runner) — `brew install just`

## Quick Start

```bash
# Clone and enter the project
git clone <repo-url> docforge
cd docforge

# Initialize (creates .env, venv, installs deps, starts DB, runs migrations)
just init

# Start development servers (API + Worker + Frontend)
just dev
```

Then open http://localhost:5173 in your browser.

## Development Setup

### 1. Environment

```bash
cp .env.example .env
# Edit .env with your settings (API keys, etc.)
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn api.app:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Infrastructure

```bash
# Start PostgreSQL, Redis, and MinIO
docker compose up -d postgres redis minio
```

### 5. Worker

```bash
cd backend
celery -A workers.celery_app worker --loglevel=info
```

## Available Commands

All commands are available via `just`:

| Command | Description |
|---------|-------------|
| `just dev` | Start all dev services |
| `just dev-api` | Start API server only |
| `just dev-worker` | Start Celery worker only |
| `just dev-frontend` | Start frontend dev server |
| `just dev-db` | Start infrastructure services |
| `just test-all` | Run all tests |
| `just test-backend` | Run backend tests |
| `just test-frontend` | Run frontend tests |
| `just lint` | Lint all code |
| `just db-migrate` | Run database migrations |
| `just db-rollback` | Rollback last migration |
| `just db-new-migration msg="desc"` | Create new migration |
| `just docker-build` | Build Docker images |
| `just docker-up` | Start Docker stack |
| `just docker-down` | Stop Docker stack |
| `just clean` | Clean cache files |
| `just init` | Initialize project |
| `just seed` | Seed demo data |

## Project Structure

```
docforge/
├── backend/
│   ├── api/            # FastAPI routes, middleware, schemas
│   ├── core/           # Domain models (pure Python, zero deps)
│   ├── ports/          # Interface definitions (ABCs)
│   ├── adapters/       # PostgreSQL, MinIO implementations
│   ├── config/         # Settings, logging
│   ├── workers/        # Celery app and tasks
│   └── tests/          # Test suite
├── frontend/
│   ├── src/
│   │   ├── api/        # API client and stores
│   │   ├── components/ # Vue components
│   │   ├── composables/# Vue composables
│   │   ├── extensions/ # Tiptap extensions
│   │   ├── router/     # Vue Router config
│   │   ├── stores/     # Pinia stores
│   │   ├── types/      # TypeScript types
│   │   └── views/      # Page views
│   └── tests/          # Test suite
├── infra/
│   ├── docker/         # Dockerfiles + nginx.conf
│   ├── k8s/            # Kubernetes manifests
│   └── scripts/        # Infrastructure scripts
├── scripts/            # Development scripts
├── .github/workflows/  # CI/CD pipelines
├── docker-compose.yml  # Local stack: infra + api + worker + frontend (hot reload)
├── justfile            # Command runner
└── README.md
```

## Environment Variables

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://docforge:docforge@localhost:5432/docforge` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | MinIO server endpoint | `localhost:9000` |
| `JWT_SECRET` | JWT signing secret | `change-me-in-production` |
| `OPENAI_API_KEY` | OpenAI API key | (required for LLM features) |
| `ANTHROPIC_API_KEY` | Anthropic API key | (alternative LLM provider) |
| `LLM_PROVIDER` | Default LLM provider | `openai` |
| `ENABLE_OTEL` | Enable OpenTelemetry | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Testing

```bash
# Run all tests
just test-all

# Backend only
just test-backend

# Frontend only
just test-frontend

# With coverage
cd backend && pytest tests/ -v --cov=core
```

## Docker

```bash
# Build all images
just docker-build

# Start the full local stack (hot reload)
just docker-up

# Stop it
just docker-down
```

> Production topology (TLS edge, replicas, one-shot migrations) is not committed
> yet — it will be added in a dedicated compose file when we deploy.

## License

Proprietary — All rights reserved.
