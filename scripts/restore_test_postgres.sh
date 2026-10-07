#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_FILE:?Set BACKUP_FILE to a custom-format PostgreSQL dump}"
: "${RESTORE_DATABASE_URL:?Set RESTORE_DATABASE_URL to a dedicated restore database}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  printf 'backup not found: %s\n' "$BACKUP_FILE" >&2
  exit 1
fi

if [[ -n "${DATABASE_URL:-}" && "$RESTORE_DATABASE_URL" == "$DATABASE_URL" ]]; then
  printf 'refusing to restore into DATABASE_URL; use a dedicated restore database\n' >&2
  exit 1
fi

pg_restore \
  --dbname="$RESTORE_DATABASE_URL" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  --single-transaction \
  "$BACKUP_FILE"

psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1;' >/dev/null
printf 'restore test passed for %s\n' "$BACKUP_FILE"
