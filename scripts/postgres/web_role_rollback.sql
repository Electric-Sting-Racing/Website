-- Removes the web role and puts back the default access it took away.
-- Run as the database owner, connected to the site database, only after the web service
-- no longer connects as this role. Expects :web_user to default to fsae_web.
\set ON_ERROR_STOP on
\if :{?web_user}
\else
  \set web_user fsae_web
\endif
SELECT current_database() AS db \gset

-- DROP OWNED also drops objects the role owns. It should own none; stop if it does.
SELECT count(*) > 0 AS owns_any, count(*) AS owned
FROM pg_shdepend d
JOIN pg_roles r ON r.oid = d.refobjid
WHERE d.deptype = 'o'
  AND d.dbid = (SELECT oid FROM pg_database WHERE datname = :'db')
  AND r.rolname = :'web_user' \gset
\if :owns_any
  \echo Refusing to continue: :web_user owns :owned object(s) in :db, and DROP OWNED would delete them.
  DO $$ BEGIN RAISE EXCEPTION 'web role owns objects'; END $$;
\endif

-- Revokes the role's grants and default privileges.
DROP OWNED BY :"web_user";
DROP ROLE :"web_user";
GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO PUBLIC;
-- Put back the stock access on the other databases (template1 never had TEMPORARY).
SELECT format('GRANT CONNECT%s ON DATABASE %I TO PUBLIC', CASE WHEN datname = 'template1' THEN '' ELSE ', TEMPORARY' END, datname)
FROM pg_database WHERE datallowconn AND datname <> :'db' \gexec
