#!/bin/bash
if [ -z "$SYNAPSE_PASSWORD" ]
then
  echo "SYNAPSE_PASSWORD not set"
  exit 1
fi
set -e

# 1. Create the User and Database
# We connect to the default DB ($POSTGRES_DB) to do this.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER synapse WITH ENCRYPTED PASSWORD '$SYNAPSE_PASSWORD';
    CREATE DATABASE synapse TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C';
    GRANT ALL PRIVILEGES ON DATABASE synapse TO synapse;
EOSQL

# 2. Grant Schema Permissions
# CRITICAL: We must connect TO the 'synapse' database to alter its public schema.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "synapse" <<-EOSQL
    ALTER SCHEMA public OWNER TO synapse;
    GRANT ALL ON SCHEMA public TO synapse;
EOSQL