#!/bin/sh
# Passes only if the connecting role (PGUSER etc.) can read and write every site table but cannot
# change the schema or reach other databases.
set -eu
q() { psql -X -v ON_ERROR_STOP=1 -At -c "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
[ "$(q "select rolsuper or rolcreatedb or rolcreaterole or rolreplication or rolbypassrls from pg_roles where rolname = current_user")" = f ] || fail "role has elevated attributes"
[ "$(q "select has_database_privilege(current_database(), 'CREATE') or has_database_privilege(current_database(), 'TEMP') or has_schema_privilege('public', 'CREATE')")" = f ] || fail "role can create objects"
[ "$(q "select count(*) from pg_tables where schemaname = 'public' and tableowner = current_user")" = 0 ] || fail "role owns tables"
# has_table_privilege(t, 'A, B') is true if ANY is held, so check each privilege separately.
[ "$(q "select count(*) from pg_tables t, lateral (select format('%I.%I', t.schemaname, t.tablename) n) x where t.schemaname = 'public' and not (has_table_privilege(x.n, 'SELECT') and has_table_privilege(x.n, 'INSERT') and has_table_privilege(x.n, 'UPDATE') and has_table_privilege(x.n, 'DELETE'))")" = 0 ] || fail "some tables are not readable and writable"
if psql -X -c "create table role_check_should_fail (id int)" >/dev/null 2>&1; then fail "CREATE TABLE succeeded"; fi
if psql -X -d postgres -c "select 1" >/dev/null 2>&1; then fail "can connect to the postgres database"; fi
others="$(q "select string_agg(datname, ', ' order by datname) from pg_database where datallowconn and datname <> current_database() and has_database_privilege(datname, 'CONNECT')")"
[ -z "$others" ] || fail "can connect to other databases: $others"
printf 'PASS: %s can read and write rows but cannot change the schema\n' "$(q 'select current_user')"
