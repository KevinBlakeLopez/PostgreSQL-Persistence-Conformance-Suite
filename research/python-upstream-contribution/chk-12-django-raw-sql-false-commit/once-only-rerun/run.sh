#!/bin/bash
# Runs django_once_only.py three times with ATOMIC_REQUESTS off and three with it on, against
# a throwaway PostgreSQL container, then records the psql fates, the server log and the
# cross-check.
# Usage: bash run.sh <virtualenv python>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$1"
OUT="$HERE/output"
NAME=ppcs-django-once-only-pg
PORT=55499
IMAGE='postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336'
FILES="django_once_only.py run.sh wait_for_server.py log_check.py"
export DOCKER_CONTEXT=colima
mkdir -p "$OUT"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then echo "container $NAME exists; refusing" >&2; exit 1; fi
if nc -z 127.0.0.1 "$PORT" 2>/dev/null; then echo "port $PORT is in use; refusing" >&2; exit 1; fi

(cd "$HERE" && shasum -a 256 $FILES) > "$OUT/hashes-before.txt"
"$PY" -m pip freeze > "$HERE/versions-pip.txt"

PASSWORD="$(openssl rand -hex 16)"
TOKEN="t$(openssl rand -hex 8)"
cleanup() { docker rm -f -v "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$NAME" -e POSTGRES_PASSWORD="$PASSWORD" \
  -p "127.0.0.1:$PORT:5432" --tmpfs /var/lib/postgresql \
  "$IMAGE" postgres -c cluster_name="$TOKEN" -c max_connections=100 -c log_lock_waits=on \
  -c deadlock_timeout=1s -c log_statement=all \
  -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x sqlstate=%e ' >/dev/null

DATABASE_URL="postgresql://postgres:${PASSWORD}@127.0.0.1:${PORT}/postgres"
TOKEN="$TOKEN" DATABASE_URL="$DATABASE_URL" "$PY" -I "$HERE/wait_for_server.py"

docker exec "$NAME" psql -U postgres -d postgres -AtX -c "select name || ' = ' || setting from pg_settings
  where name in ('server_version', 'synchronous_commit', 'default_transaction_isolation', 'statement_timeout',
                 'idle_in_transaction_session_timeout', 'log_statement', 'log_line_prefix', 'max_connections')
  order by name" > "$OUT/server-settings.txt"

: > "$OUT/exit-codes.txt"
for mode in off on; do for rep in 1 2 3; do
  set +e
  (cd "$HERE" && DATABASE_URL="$DATABASE_URL" "$PY" -I django_once_only.py "$mode" > "$OUT/$mode.rep$rep.out" 2>&1)
  echo "$mode.rep$rep $?" >> "$OUT/exit-codes.txt"
  set -e
done; done

XIDS="$(grep -ho 'pg_xact_status([0-9]*)' "$OUT"/*.rep*.out | tr -dc '0-9\n' | sort -n | paste -sd, -)"
QUERY="select x::text as xid, pg_xact_status(x::text::xid8) as status from unnest(array[$XIDS]::bigint[]) as x order by x"
{ echo "-- $QUERY"; docker exec "$NAME" psql -U postgres -d postgres -X -c "$QUERY"; } > "$OUT/psql-xact-status.txt"

docker logs "$NAME" > "$OUT/server.log" 2>&1
{
  echo "image: $IMAGE"
  echo "image id: $(docker inspect --format '{{.Image}}' "$NAME")"
  echo "docker server: $(docker version --format '{{.Server.Version}}')"
  echo "colima: $(colima version 2>/dev/null | head -1)"
  echo "host: $(sw_vers -productName) $(sw_vers -productVersion) $(uname -m)"
  echo "python: $("$PY" -V)"
} > "$OUT/env.txt"
(cd "$HERE" && shasum -a 256 $FILES) > "$OUT/hashes-after.txt"

set +e
(cd "$HERE" && "$PY" -I log_check.py output > "$OUT/log-check.txt")
echo "log_check exit $?"
set -e
cmp -s "$OUT/hashes-before.txt" "$OUT/hashes-after.txt" && echo "files unchanged during the runs" || echo "FILES CHANGED DURING THE RUNS"
