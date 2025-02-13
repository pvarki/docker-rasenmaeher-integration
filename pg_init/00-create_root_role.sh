#!/bin/bash
set -e
# To avoid pg_isready causing weird errors in logs
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER root;
    CREATE DATABASE root;
EOSQL
