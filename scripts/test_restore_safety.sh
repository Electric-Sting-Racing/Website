#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_PARENT="${TMPDIR:-/tmp}"
if [[ ! -d "$TEMP_PARENT" ]]; then
  TEMP_PARENT="$ROOT"
fi
TEMP_DIR="$(mktemp -d "$TEMP_PARENT/.restore-safety.XXXXXX")"
trap 'rm -rf "$TEMP_DIR"' EXIT

mkdir -p "$TEMP_DIR/bin"
touch "$TEMP_DIR/backup.dump"

cat > "$TEMP_DIR/bin/psql" <<'PSQL'
#!/usr/bin/env bash
set -Eeuo pipefail

dsn=""
command_text=""
for arg in "$@"; do
  case "$arg" in
    --dbname=*) dsn="${arg#--dbname=}" ;;
    --command=*) command_text="${arg#--command=}" ;;
  esac
  if [[ -z "$dsn" && "$arg" != -* ]]; then
    dsn="$arg"
  fi
done

if [[ "$command_text" == "SELECT current_database();" ]]; then
  case "$dsn" in
    */target-dsn) printf '%s\n' "${TARGET_DATABASE:?}" ;;
    */production-dsn*) printf '%s\n' "${PRODUCTION_DATABASE:?}" ;;
    *) printf 'unexpected test database target\n' >&2; exit 2 ;;
  esac
fi
PSQL

cat > "$TEMP_DIR/bin/pg_restore" <<'PG_RESTORE'
#!/usr/bin/env bash
set -Eeuo pipefail
touch "${PG_RESTORE_MARKER:?}"
PG_RESTORE

chmod +x "$TEMP_DIR/bin/psql" "$TEMP_DIR/bin/pg_restore"

expect_refusal() {
  local output_file="$TEMP_DIR/output.txt"
  rm -f "$TEMP_DIR/pg_restore_called"
  if env \
    PATH="$TEMP_DIR/bin:$PATH" \
    BACKUP_FILE="$TEMP_DIR/backup.dump" \
    RESTORE_DATABASE_URL="$1" \
    TARGET_DATABASE="$2" \
    PRODUCTION_DATABASE="$3" \
    PG_RESTORE_MARKER="$TEMP_DIR/pg_restore_called" \
    DATABASE_URL="$4" \
    bash "$ROOT/scripts/restore_test_postgres.sh" >"$output_file" 2>&1; then
    cat "$output_file" >&2
    printf 'expected restore refusal\n' >&2
    exit 1
  fi
  if [[ -e "$TEMP_DIR/pg_restore_called" ]]; then
    printf 'pg_restore ran after a safety check failed\n' >&2
    exit 1
  fi
}

expect_refusal \
  'postgresql://db.example/production-dsn' \
  'fsae' \
  'unused' \
  ''
grep -q 'must end in _restore' "$TEMP_DIR/output.txt"

expect_refusal \
  'postgresql://restore-user@restore.example/target-dsn' \
  'fsae_restore' \
  'fsae_restore' \
  'postgres://different-user@production.example/production-dsn?sslmode=require'
grep -q 'matches DATABASE_URL' "$TEMP_DIR/output.txt"

rm -f "$TEMP_DIR/pg_restore_called"
env \
  PATH="$TEMP_DIR/bin:$PATH" \
  BACKUP_FILE="$TEMP_DIR/backup.dump" \
  RESTORE_DATABASE_URL='postgresql://restore-user@restore.example/target-dsn' \
  TARGET_DATABASE='fsae_restore' \
  PRODUCTION_DATABASE='fsae' \
  DATABASE_URL='postgresql://app@production.example/production-dsn' \
  PG_RESTORE_MARKER="$TEMP_DIR/pg_restore_called" \
  bash "$ROOT/scripts/restore_test_postgres.sh" >"$TEMP_DIR/output.txt" 2>&1

test -e "$TEMP_DIR/pg_restore_called"
grep -q 'restore test passed' "$TEMP_DIR/output.txt"
printf 'PASS: restore refuses non-disposable and production-named targets; disposable target proceeds\n'
