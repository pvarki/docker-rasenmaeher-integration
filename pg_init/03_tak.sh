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
