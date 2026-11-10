#!/usr/bin/env bash
# AureVon database backup (M14). Writes a compressed, custom-format pg_dump plus a SHA-256 checksum.
#
#   DATABASE_URL=postgres://user:pass@host:5432/aurevon scripts/ops/backup.sh /path/to/backups
#
# Production keeps managed daily backups and point-in-time recovery at the database provider (MTS §12); this
# script is the separate, provider-independent copy. Frequency, retention, RTO and RPO are P-17 (pending).
# Uploaded media (product images, 3D models) live in object storage and are backed up there, not here.
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
dest="${1:-./backups}"
mkdir -p "$dest"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
file="$dest/aurevon-$stamp.dump"
pg_dump --format=custom --compress=9 --no-owner --no-privileges --file="$file" "$DATABASE_URL"
sha256sum "$file" > "$file.sha256"
echo "backup written: $file ($(du -h "$file" | cut -f1))"
