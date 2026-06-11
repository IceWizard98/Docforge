#!/bin/bash
set -euo pipefail

echo "Initializing DocForge database..."

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-docforge}"
export PGPASSWORD="${PGPASSWORD:-docforge}"
export PGDATABASE="${PGDATABASE:-docforge}"

echo "Waiting for postgres..."
until pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" > /dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

echo "Enabling pgvector extension..."
psql -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR/backend"

if [ -d "alembic" ]; then
  echo "Running database migrations..."
  alembic upgrade head
  echo "Migrations complete."
else
  echo "No alembic directory found. Skipping migrations."
fi

echo "Creating initial admin user..."
python -c "
import asyncio
from api.middleware.auth import create_access_token
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config.settings import get_settings
from adapters.postgresql.models import Base, TenantModel, UserModel

async def init():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        tenant = TenantModel(name='Default', slug='default')
        session.add(tenant)
        await session.flush()
        from passlib.hash import bcrypt
        user = UserModel(
            email='admin@docforge.app',
            hashed_password=bcrypt.hash('admin123'),
            display_name='Admin',
            tenant_id=tenant.id,
            role='admin'
        )
        session.add(user)
        await session.commit()
        print(f'Created admin user: admin@docforge.app / admin123')

asyncio.run(init())
" 2>/dev/null || echo "Admin user may already exist."

echo "Database initialization complete."
