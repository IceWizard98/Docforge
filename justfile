# DocForge - Justfile

dev-api:
    cd backend && uvicorn api.app:app --reload --port 8000

dev-worker:
    cd backend && celery -A workers.celery_app worker --loglevel=info

dev-frontend:
    cd frontend && npm run dev

dev-db:
    docker compose up -d postgres redis minio

dev:
    @echo "Starting all dev services..."
    just dev-db &
    just dev-api &
    just dev-worker &
    just dev-frontend
    trap 'kill 0' SIGINT SIGTERM

# Scripts
scripts-dev:
    ./scripts/dev.sh

scripts-test:
    ./scripts/test.sh

scripts-lint:
    ./scripts/lint.sh

# Testing
test-all: test-backend test-frontend

test-backend:
    cd backend && source .venv/bin/activate && python -m pytest tests/ -v --cov

test-frontend:
    cd frontend && npm run test

test-e2e:
    cd frontend && npm run test:e2e

# Linting
lint:
    cd backend && ruff check .
    cd backend && mypy core/
    cd frontend && npm run lint

typecheck:
    cd frontend && npm run typecheck

# Database
db-migrate:
    cd backend && alembic upgrade head

db-rollback:
    cd backend && alembic downgrade -1

db-new-migration msg:
    cd backend && alembic revision --autogenerate -m "{{msg}}"

db-init:
    ./infra/scripts/init-db.sh

# Docker — single local stack (infra + api + worker + frontend, hot reload).
docker-build:
    docker compose build

docker-up:
    docker compose up -d

docker-down:
    docker compose down

# Clean
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Initialize
init:
    cp -n .env.example .env 2>/dev/null || echo '.env exists, skipping'
    cd backend && python -m venv venv
    cd backend && . venv/bin/activate && pip install -r requirements.txt
    cd frontend && npm install
    docker compose up -d postgres redis minio
    sleep 3
    cd backend && alembic upgrade head

# Seed
seed:
    cd backend && python scripts/seed-data.py
