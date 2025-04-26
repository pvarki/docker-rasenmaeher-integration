#!/bin/bash
if [ -z "$BATTLELOG_PASSWORD" ]
then
  echo "BATTLELOG_PASSWORD not set"
  exit 1
fi
set -e
# FIXME: Can we use mTLS for auth ??
# FIXME: Get the user and db name from ENV too (or things break when someone changes the defaults)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER battlelog WITH ENCRYPTED PASSWORD '$BATTLELOG_PASSWORD';
    CREATE DATABASE battlelog;
    GRANT ALL PRIVILEGES ON DATABASE battlelog TO battlelog;
EOSQL
# Allow normal user to mess around in public schema, see https://www.cybertec-postgresql.com/en/error-permission-denied-schema-public/
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname battlelog <<-EOSQL
    GRANT ALL ON SCHEMA public TO battlelog;
EOSQL
# Make sure the gis etc extensions are actually present and usable
# And allow normal user to mess around in public schema, see https://www.cybertec-postgresql.com/en/error-permission-denied-schema-public/
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "battlelog" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';
    CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;
    COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';
    GRANT ALL PRIVILEGES ON TABLE public.spatial_ref_sys TO battlelog;
    GRANT ALL ON SCHEMA public TO battlelog;
EOSQL
