#!/bin/bash
if [ -z "$KEYCLOAK_PASSWORD" ]
then
  echo "KEYCLOAK_PASSWORD not set"
  exit 1
fi
set -e
# FIXME: Can we use mTLS for auth ??
# FIXME: Get the user and db name from ENV too (or things break when someone changes the defaults)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER keycloak WITH ENCRYPTED PASSWORD '$KEYCLOAK_PASSWORD';
    CREATE DATABASE keycloak;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
EOSQL
# Allow normal user to mess around in public schema, see https://www.cybertec-postgresql.com/en/error-permission-denied-schema-public/
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname keycloak <<-EOSQL
    GRANT ALL ON SCHEMA public TO keycloak;
EOSQL
