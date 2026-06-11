#!/bin/bash
set -euo pipefail

echo "Seeding DocForge with demo data..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR/backend"

if [ -f "scripts/seed-data.py" ]; then
  echo "Running seed-data.py..."
  python scripts/seed-data.py
else
  echo "scripts/seed-data.py not found. Creating demo data via inline script..."
  python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config.settings import get_settings

async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        from sqlalchemy import text
        result = await session.execute(text(\"SELECT id FROM tenants LIMIT 1\"))
        tenant_row = result.fetchone()
        if not tenant_row:
            print('No tenant found. Run init-db.sh first.')
            return
        tenant_id = tenant_row[0]

        from sqlalchemy import text
        result = await session.execute(
            text(\"SELECT id FROM users WHERE tenant_id = :tid LIMIT 1\"),
            {\"tid\": tenant_id}
        )
        user_row = result.fetchone()
        if not user_row:
            print('No user found. Run init-db.sh first.')
            return
        user_id = user_row[0]

        result = await session.execute(
            text(\"SELECT id FROM documents WHERE tenant_id = :tid LIMIT 1\"),
            {\"tid\": tenant_id}
        )
        if result.fetchone():
            print('Demo documents already exist. Skipping.')
            return

        from sqlalchemy import text
        sample_content = {
            'type': 'doc',
            'content': [
                {'type': 'section', 'attrs': {'id': 'sec-1'}, 'content': [
                    {'type': 'clause', 'attrs': {'id': 'cl-1'}, 'content': [
                        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'This is a sample document for DocForge.'}]}
                    ]}
                ]}
            ]
        }
        import json
        await session.execute(
            text(\"\"\"
                INSERT INTO documents (id, tenant_id, title, content, outline, version, status, language, created_at, updated_at)
                VALUES (gen_random_uuid(), :tid, :title, :content::jsonb, :outline::jsonb, 1, 'draft', 'en', NOW(), NOW())
            \"\"\"),
            {
                'tid': tenant_id,
                'title': 'Welcome to DocForge',
                'content': json.dumps(sample_content),
                'outline': json.dumps([{'id': 'sec-1', 'title': 'Introduction'}]),
            }
        )
        await session.commit()
        print('Demo document created successfully.')

asyncio.run(seed())
"
fi

echo "Seed complete."
