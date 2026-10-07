#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_FILE:?Set BACKUP_FILE to a custom-format PostgreSQL dump}"
: "${RESTORE_DATABASE_URL:?Set RESTORE_DATABASE_URL to a dedicated restore database}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  printf 'backup not found: %s\n' "$BACKUP_FILE" >&2
  exit 1
fi

target_database="$(
  psql \
    --no-psqlrc \
    --dbname="$RESTORE_DATABASE_URL" \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command='SELECT current_database();'
)"

if [[ "$target_database" != *_restore ]]; then
  printf 'refusing to restore: target database name must end in _restore\n' >&2
  exit 1
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  production_database="$(
    psql \
      --no-psqlrc \
      --dbname="$DATABASE_URL" \
      --set=ON_ERROR_STOP=1 \
      --tuples-only \
      --no-align \
      --command='SELECT current_database();'
  )"

  if [[ "$target_database" == "$production_database" ]]; then
    printf 'refusing to restore: target database name matches DATABASE_URL\n' >&2
    exit 1
  fi
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

psql --no-psqlrc "$RESTORE_DATABASE_URL" --set=ON_ERROR_STOP=1 -c 'SELECT 1;' >/dev/null
printf 'restore test passed for %s\n' "$BACKUP_FILE"
