#!/bin/bash
set -e

echo "=== DocForge Entrypoint ==="

echo "Waiting for PostgreSQL..."
until pg_isready -h postgres -U docforge -d docforge -q 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running alembic migrations..."
alembic upgrade head
echo "Migrations applied."

echo "Starting application: $@"
exec "$@"
