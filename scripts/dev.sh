#!/bin/bash
set -euo pipefail

echo "Starting DocForge dev environment..."

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

echo "Starting infrastructure services..."
docker compose up -d postgres redis minio

echo "Waiting for postgres..."
until docker compose exec postgres pg_isready -U docforge > /dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

echo "Waiting for redis..."
until docker compose exec redis redis-cli ping > /dev/null 2>&1; do
  sleep 1
done
echo "Redis is ready."

echo "Waiting for minio..."
until curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1; do
  sleep 1
done
echo "MinIO is ready."

echo "Running database migrations..."
cd backend && alembic upgrade head
cd ..

echo ""
echo "============================================"
echo "  DocForge Dev Environment"
echo "============================================"
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  MinIO:    http://localhost:9001"
echo "============================================"
echo ""

echo "Starting API server..."
cd backend && uvicorn api.app:app --reload --port 8000 &
API_PID=$!

cd frontend && npm run dev &
FRONTEND_PID=$!

echo "API PID: $API_PID"
echo "Frontend PID: $FRONTEND_PID"

trap "kill $API_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
