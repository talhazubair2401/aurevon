# Backups and restore

P-17 (frequency, retention, RTO, RPO) is **pending**; until it is decided, use the provisional plan below.

| | Provisional |
|---|---|
| Primary | Managed PostgreSQL daily snapshots + point-in-time recovery (provider feature) |
| Independent copy | `scripts/ops/backup.sh` nightly to storage outside the primary provider, kept 30 days |
| Media | Object-storage versioning on the public and private buckets |
| Restore test | Monthly: restore the newest independent copy into a scratch database with `scripts/ops/restore.sh` |

## Backup

```sh
DATABASE_URL=postgres://… scripts/ops/backup.sh /secure/backups
```

Produces `aurevon-<UTC time>.dump` (pg_dump custom format, compressed) and a `.sha256` checksum. Backups contain
personal data (customers, orders, staff): store them encrypted, with access limited to the Owner and the hosting
administrator.

## Restore (tested 2026-11-10)

```sh
createdb aurevon_restore
TARGET_URL=postgres://…/aurevon_restore scripts/ops/restore.sh /secure/backups/aurevon-….dump
DATABASE_URL=postgres://…/aurevon_restore python manage.py migrate --check
```

The script verifies the checksum, refuses a non-empty target, restores, and prints row counts for the key tables.
Verified on 2026-11-10 with a demo-catalogue database: 45 migrations, 24 products and 209 stock rows restored, and
`migrate --check` clean; a second restore into the same database was refused as intended.

Then point the services at the restored database (or rename databases during a maintenance window), and run the
release smoke test. Staff sessions survive a restore; customer bags newer than the backup are lost.
