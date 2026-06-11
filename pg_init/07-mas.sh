#!/bin/bash
if [ -z "$MAS_PASSWORD" ]
then
  echo "MAS_PASSWORD not set"
  exit 1
fi
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER mas WITH ENCRYPTED PASSWORD '$MAS_PASSWORD';
    CREATE DATABASE mas TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';
    GRANT ALL PRIVILEGES ON DATABASE mas TO mas;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "mas" <<-EOSQL
    ALTER SCHEMA public OWNER TO mas;
    GRANT ALL ON SCHEMA public TO mas;
EOSQL
