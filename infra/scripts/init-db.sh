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

ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
if [ -z "$ADMIN_PASSWORD" ]; then
  echo "ERROR: ADMIN_PASSWORD env var must be set"
  exit 1
fi

echo "Creating or updating admin user..."
python -c "
import asyncio, sys, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from config.settings import get_settings
from adapters.postgresql.models import TenantModel, UserModel
from passlib.hash import bcrypt

async def init():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        result = await session.execute(select(TenantModel).where(TenantModel.slug == 'default'))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = TenantModel(name='Default', slug='default')
            session.add(tenant)
            await session.flush()

        result = await session.execute(
            select(UserModel).where(UserModel.email == 'admin@docforge.app')
        )
        user = result.scalar_one_or_none()
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        if user:
            user.hashed_password = bcrypt.hash(admin_password)
            print('Updated admin user password')
        else:
            user = UserModel(
                email='admin@docforge.app',
                hashed_password=bcrypt.hash(admin_password),
                display_name='Admin',
                tenant_id=tenant.id,
                role='admin'
            )
            session.add(user)
            print('Created admin user: admin@docforge.app')
        await session.commit()

asyncio.run(init())
" || echo "ERROR: Failed to create admin user" >&2

echo "Database initialization complete."
