#!/bin/sh
# Starts the disposable PostgreSQL server (compose.yaml) and writes .ppcs-instance.json, which the runner reads.
#
# - A random cluster_name token identifies this server. The runner checks it before sending any other statement.
# - The password is random per start. .ppcs-instance.json is gitignored and readable only by the current user.
# - The host port forward (for example colima's) can lag behind the container, so this waits until the port accepts
#   connections from the host, not just until the container reports healthy.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
INSTANCE="$DIR/.ppcs-instance.json"
PORT="${PPCS_PGPORT:-55435}"
TOKEN="ppcs-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
export PPCS_INSTANCE_TOKEN="$TOKEN" PPCS_PGPASSWORD="$PASSWORD" PPCS_PGPORT="$PORT"

rm -f "$INSTANCE"
docker compose -f "$DIR/compose.yaml" down --volumes --remove-orphans >/dev/null 2>&1 || true
docker compose -f "$DIR/compose.yaml" up --detach --wait --wait-timeout 120

i=0
until node -e "require('net').connect(${PORT}, '127.0.0.1').on('connect', () => process.exit(0)).on('error', () => process.exit(1))" 2>/dev/null; do
  i=$((i+1)); [ "$i" -gt 30 ] && { echo "Port ${PORT} is not reachable from the host" >&2; exit 1; }
  sleep 1
done

IMAGE=$(docker compose -f "$DIR/compose.yaml" config --images | head -n 1)
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
umask 077
printf '{"token":"%s","host":"127.0.0.1","port":%s,"user":"postgres","password":"%s","image":"%s","container":"ppcs-postgres","started_at":"%s"}\n' \
  "$TOKEN" "$PORT" "$PASSWORD" "$IMAGE" "$STARTED" > "$INSTANCE"
docker exec ppcs-postgres psql -U postgres -tAc "select version(), current_setting('cluster_name')"
