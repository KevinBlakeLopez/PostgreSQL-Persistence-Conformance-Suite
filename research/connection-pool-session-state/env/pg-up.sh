#!/bin/sh
# Starts this investigation's own disposable PostgreSQL server and writes an instance file (mode 0600) for the
# experiments. It never touches PPCS's shared `ppcs-postgres` container.
#
# Usage: env/pg-up.sh <instance-file>
#
# - Image: PPCS's pinned postgres:18.6 digest (compose.yaml).
# - Container `ppcs-ssc-pg`, host port 55473, bound to 127.0.0.1 only, data directory on tmpfs.
# - A random cluster_name token identifies the server. Every experiment checks it before doing anything else.
# - Random passwords for `postgres` and for the non-superuser login `ssc_app`. They go only into the instance file.
#   `log_statement` is switched off in the session that sets the `ssc_app` password, so it never reaches the log.
# - Statement logging is on, with the virtual transaction ID (%v), the transaction ID (%x) and the SQLSTATE (%e)
#   in every line: `docker logs ppcs-ssc-pg` is the independent server-side record.
set -eu
INSTANCE="${1:?usage: pg-up.sh <instance-file>}"
NAME=ppcs-ssc-pg
PORT=55473
IMAGE='postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336'
export DOCKER_CONTEXT="${DOCKER_CONTEXT:-colima}"

TOKEN="ppcs-ssc-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
PGPW="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
APPPW="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "container $NAME already exists; remove it first with env/pg-down.sh" >&2
  exit 1
fi
if nc -z 127.0.0.1 "$PORT" 2>/dev/null; then
  echo "port $PORT is already in use" >&2
  exit 1
fi

docker run -d --name "$NAME" --label purpose=ppcs-ssc-disposable \
  -e POSTGRES_PASSWORD="$PGPW" \
  -p "127.0.0.1:${PORT}:5432" \
  --tmpfs /var/lib/postgresql:size=512m \
  "$IMAGE" postgres \
  -c cluster_name="$TOKEN" \
  -c max_connections=100 \
  -c log_statement=all \
  -c log_connections=on \
  -c log_disconnections=on \
  -c "log_line_prefix=%m [%p] app=%a vxid=%v xid=%x sqlstate=%e " \
  -c log_lock_waits=on \
  -c deadlock_timeout=1s >/dev/null

i=0
until docker exec "$NAME" psql -h 127.0.0.1 -U postgres -tAc 'select 1' >/dev/null 2>&1; do
  i=$((i+1)); [ "$i" -gt 90 ] && { echo "server did not start" >&2; exit 1; }
  sleep 1
done
i=0
until nc -z 127.0.0.1 "$PORT" 2>/dev/null; do
  i=$((i+1)); [ "$i" -gt 30 ] && { echo "port $PORT is not reachable from the host" >&2; exit 1; }
  sleep 1
done

# Fixture. tenant_a and tenant_b each have their own `item`, as does public, so the schema a row lands in shows
# which search_path the session used. `inserted_by` records current_user, so a row shows the role it ran as.
docker exec -i "$NAME" psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres -q <<SQL
SET log_statement = 'none';
CREATE ROLE ssc_app LOGIN PASSWORD '${APPPW}';
SET log_statement = 'all';
CREATE ROLE ssc_tenant_a NOLOGIN;
CREATE ROLE ssc_tenant_b NOLOGIN;
GRANT ssc_tenant_a, ssc_tenant_b TO ssc_app;
CREATE DATABASE ssc OWNER ssc_app;
\c ssc
CREATE SCHEMA tenant_a AUTHORIZATION ssc_app;
CREATE SCHEMA tenant_b AUTHORIZATION ssc_app;
GRANT CREATE ON SCHEMA public TO ssc_app;
SET ROLE ssc_app;
CREATE TABLE public.item   (id bigserial PRIMARY KEY, label text NOT NULL, inserted_by name NOT NULL DEFAULT current_user);
CREATE TABLE tenant_a.item (id bigserial PRIMARY KEY, label text NOT NULL, inserted_by name NOT NULL DEFAULT current_user);
CREATE TABLE tenant_b.item (id bigserial PRIMARY KEY, label text NOT NULL, inserted_by name NOT NULL DEFAULT current_user);
GRANT USAGE ON SCHEMA tenant_a, tenant_b TO ssc_tenant_a, ssc_tenant_b;
GRANT ALL ON ALL TABLES IN SCHEMA public, tenant_a, tenant_b TO ssc_tenant_a, ssc_tenant_b;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public, tenant_a, tenant_b TO ssc_tenant_a, ssc_tenant_b;
CREATE TABLE public.probe_row (id int PRIMARY KEY, v int NOT NULL);
INSERT INTO public.probe_row VALUES (1, 0);
RESET ROLE;
SQL

umask 077
printf '{"token":"%s","host":"127.0.0.1","port":%s,"database":"ssc","superuser":"postgres","superuser_password":"%s","user":"ssc_app","password":"%s","image":"%s","container":"%s","started_at":"%s"}\n' \
  "$TOKEN" "$PORT" "$PGPW" "$APPPW" "$IMAGE" "$NAME" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$INSTANCE"
docker exec "$NAME" psql -h 127.0.0.1 -U postgres -tAc "select version(), current_setting('cluster_name')"
