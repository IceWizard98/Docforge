# DocForge - Justfile

dev-api:
    cd backend && uvicorn api.app:app --reload --port 8000

dev-worker:
    cd backend && celery -A workers.celery_app worker --loglevel=info

dev-frontend:
    cd frontend && npm run dev

dev-db:
    docker compose up -d postgres redis minio

dev: dev-db dev-api dev-worker dev-frontend

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
    cd backend && pytest tests/ -v --cov=core

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

# Docker
docker-build:
    docker compose -f infra/docker/docker-compose.yml build

docker-up:
    docker compose -f infra/docker/docker-compose.yml up -d

docker-down:
    docker compose -f infra/docker/docker-compose.yml down

docker-prod-up:
    docker compose -f infra/docker/docker-compose.prod.yml up -d

docker-prod-down:
    docker compose -f infra/docker/docker-compose.prod.yml down

# Clean
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Initialize
init:
    cp .env.example .env
    cd backend && python -m venv venv
    cd backend && . venv/bin/activate && pip install -r requirements.txt
    cd frontend && npm install
    docker compose up -d postgres redis minio
    sleep 3
    cd backend && alembic upgrade head

# Seed
seed:
    cd backend && python scripts/seed-data.py || ./infra/scripts/seed-data.sh
