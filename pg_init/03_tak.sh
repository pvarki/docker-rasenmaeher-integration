#!/bin/bash
if [ -z "TAK_PASSWORD" ]
then
  echo "TAK_PASSWORD not set, not creating the DB"
  exit 0
fi
set -e
# FIXME: Can we use mTLS for auth ??
# FIXME: Get the user and db name from ENV too (or things break when someone changes the defaults)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER tak WITH ENCRYPTED PASSWORD '$TAK_PASSWORD';
    CREATE DATABASE tak;
    GRANT ALL PRIVILEGES ON DATABASE tak TO tak;
EOSQL
# Make sure the gis etc extensions are actually present and usable
# And allow normal user to mess around in public schema, see https://www.cybertec-postgresql.com/en/error-permission-denied-schema-public/
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "tak" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';
    CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;
    COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';
    GRANT ALL PRIVILEGES ON TABLE public.spatial_ref_sys TO tak;
    GRANT ALL ON SCHEMA public TO tak;
EOSQL
