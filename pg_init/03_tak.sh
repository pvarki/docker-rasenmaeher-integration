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
# Adjust default privileges and make a trigger to reassign table ownerships so the normal tak user can use tables
# We need superuser privileges to run the SchemaManager and without this the tables will be owned by the superuser
# and tak normal user has no access :(
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "tak" <<-EOSQL
    CREATE OR REPLACE FUNCTION rm_func_create_set_owner()
     RETURNS event_trigger
     LANGUAGE plpgsql
    AS \$function\$
    DECLARE
        obj record;
    BEGIN
        FOR obj IN
            SELECT *
            FROM pg_event_trigger_ddl_commands()
            WHERE command_tag='CREATE TABLE'
        LOOP
            if obj.object_identity ~ '.*'
            THEN
                EXECUTE format('ALTER TABLE %s OWNER TO tak', obj.object_identity);
            end if;
        END LOOP;
    END;
    \$function\$;
    CREATE EVENT TRIGGER rm_trg_create_set_owner
        ON ddl_command_end
        WHEN tag IN ('CREATE TABLE')
        EXECUTE PROCEDURE rm_func_create_set_owner();
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO  tak;
EOSQL
# Sadly schemamanager nukes all procedures and triggers as the first thing it does when it sees a db without migration state
