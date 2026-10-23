-- Creates or updates the least-privilege role the web service connects as.
-- Run as the database owner (POSTGRES_USER), connected to the site database.
-- Safe to run repeatedly. Expects :web_password; :web_user defaults to fsae_web.
\set ON_ERROR_STOP on
\if :{?web_user}
\else
  \set web_user fsae_web
\endif
\if :{?web_password}
\else
  DO $$ BEGIN RAISE EXCEPTION 'set web_password first'; END $$;
\endif
SELECT current_database() AS db, current_user AS owner, (:'web_user' = current_user) AS same_role \gset

-- Altering the owner into the web role would strip its privileges and let the site own the tables.
\if :same_role
  \echo Refusing to continue: the web user and the owner are both :owner. Set DB_WEB_USER to a different name.
  DO $$ BEGIN RAISE EXCEPTION 'web user must differ from the owner'; END $$;
\endif

SELECT format('CREATE ROLE %I LOGIN', :'web_user')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'web_user') \gexec
ALTER ROLE :"web_user" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'web_password';

-- Only the owner and the web role may connect to the site database, and nobody else may use any
-- other database (maintenance, restore, or otherwise). Superusers are unaffected.
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"web_user";
SELECT format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', datname)
FROM pg_database WHERE datallowconn AND datname <> :'db' \gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"web_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"web_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"web_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"web_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"web_user";
