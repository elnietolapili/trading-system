#!/bin/bash
# Run new migrations (006-011) on existing database.
# Usage: docker compose exec db bash /docker-entrypoint-initdb.d/../run_new_migrations.sh
# Or: ./scripts/run_migrations.sh

echo "Running migrations 006-011..."

for f in 006 007 008 009 010 011; do
    FILE="/docker-entrypoint-initdb.d/${f}_*.sql"
    for sql in $FILE; do
        if [ -f "$sql" ]; then
            echo "  → $sql"
            psql -U trading -d trading -f "$sql" 2>&1
        fi
    done
done

echo "Done."
