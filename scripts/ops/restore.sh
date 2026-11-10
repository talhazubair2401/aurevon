#!/usr/bin/env bash
# Restores a backup made by backup.sh into an EMPTY database and checks it (M14).
#
#   TARGET_URL=postgres://user:pass@host:5432/aurevon_restore scripts/ops/restore.sh backups/aurevon-....dump
#
# Never point TARGET_URL at the live database: restore next to it, verify, then switch the app over.
set -euo pipefail
: "${TARGET_URL:?set TARGET_URL (an empty database)}"
file="${1:?path to a .dump file}"
sha256sum --check "$file.sha256"
tables=$(psql "$TARGET_URL" -Atc "select count(*) from information_schema.tables where table_schema='public'")
if [ "$tables" != "0" ]; then
  echo "refusing: the target database is not empty ($tables tables)" >&2
  exit 1
fi
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$TARGET_URL" "$file"
psql "$TARGET_URL" -Atc "select 'migrations applied: ' || count(*) from django_migrations"
for t in accounts_account orders_order catalog_product inventory_inventoryitem audit_auditlog; do
  psql "$TARGET_URL" -Atc "select '$t: ' || count(*) from $t"
done
echo "restore complete; now run: python manage.py migrate --check (with DATABASE_URL=\$TARGET_URL)"
