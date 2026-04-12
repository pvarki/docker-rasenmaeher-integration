#!/bin/bash
if [ -z "$RMCRYPTPAD_PASSWORD" ]
then
  echo "RMCRYPTPAD_PASSWORD not set"
  exit 1
fi
set -e
# FIXME: Can we use mTLS for auth ??
# FIXME: Get the user and db name from ENV too (or things break when someone changes the defaults)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER rmcryptpad WITH ENCRYPTED PASSWORD '$RMCRYPTPAD_PASSWORD';
    CREATE DATABASE rmcryptpad;
    GRANT ALL PRIVILEGES ON DATABASE rmcryptpad TO rmcryptpad;
EOSQL
