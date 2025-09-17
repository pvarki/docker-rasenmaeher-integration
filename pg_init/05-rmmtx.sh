#!/bin/bash
if [ -z "$RMMTX_PASSWORD" ]
then
  echo "RMMTX_PASSWORD not set"
  exit 1
fi
set -e
# FIXME: Can we use mTLS for auth ??
# FIXME: Get the user and db name from ENV too (or things break when someone changes the defaults)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER rmmtx WITH ENCRYPTED PASSWORD '$RMMTX_PASSWORD';
    CREATE DATABASE rmmtx;
    GRANT ALL PRIVILEGES ON DATABASE rmmtx TO rmmtx;
EOSQL
