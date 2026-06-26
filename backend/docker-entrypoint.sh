#!/bin/bash
set -e

echo "=== DocForge Entrypoint ==="

echo "Waiting for PostgreSQL..."
until pg_isready -h postgres -U docforge -d docforge -q 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

# Run migrations only when asked. With multiple api replicas (prod) a dedicated
# one-shot `migrate` service owns `alembic upgrade head`; replicas set
# RUN_MIGRATIONS=0 so they don't race the same migration on cold start.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running alembic migrations..."
  alembic upgrade head
  echo "Migrations applied."
else
  echo "Skipping migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS})."
fi

echo "Starting application: $@"
exec "$@"
