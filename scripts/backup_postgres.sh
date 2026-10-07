#!/usr/bin/env bash
set -Eeuo pipefail

backup_dir="${BACKUP_DIR:-backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
umask 077
mkdir -p "$backup_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_dir%/}/fsae-${timestamp}.dump"

pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$backup_file"

find "$backup_dir" -type f -name 'fsae-*.dump' -mtime +"$retention_days" -delete
printf 'created %s\n' "$backup_file"
