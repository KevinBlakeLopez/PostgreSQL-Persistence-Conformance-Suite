#!/bin/sh
# Starts or removes this study's own PostgreSQL container. It touches no other container.
#
#   sh research/transaction-callbacks/tools/container.sh up
#   sh research/transaction-callbacks/tools/container.sh down
#
# `up` writes ../.instance.json (gitignored): host, port, user, a random password, and a random
# cluster_name token that run.mjs checks before it sends anything. The image is the digest PPCS's
# compose.yaml pins. The data directory is a 512 MB tmpfs. Every statement is logged, with the
# database, application name, virtual transaction ID and transaction ID in each line's prefix.
set -eu

NAME=ppcs-callbacks-pg
PORT=55491
IMAGE=postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336
INSTANCE="$(cd "$(dirname "$0")/.." && pwd)/.instance.json"
export DOCKER_CONTEXT=colima

case "${1:-}" in
  up)
    if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
      echo "$NAME already exists; run '$0 down' first" >&2
      exit 1
    fi
    if nc -z 127.0.0.1 "$PORT" 2>/dev/null; then
      echo "port $PORT is already in use" >&2
      exit 1
    fi
    token="cb-$(openssl rand -hex 6)"
    password="$(openssl rand -hex 16)"
    docker run -d --name "$NAME" -p "127.0.0.1:$PORT:5432" \
      --tmpfs /var/lib/postgresql:rw,size=512m \
      -e POSTGRES_PASSWORD="$password" \
      "$IMAGE" \
      -c cluster_name="$token" \
      -c log_statement=all \
      -c "log_line_prefix=%m [%p] db=%d app=%a vxid=%v xid=%x " >/dev/null
    umask 077
    printf '{"host":"127.0.0.1","port":%s,"user":"postgres","password":"%s","token":"%s","container":"%s","image":"%s"}\n' \
      "$PORT" "$password" "$token" "$NAME" "$IMAGE" >"$INSTANCE"
    # The image's entrypoint runs a temporary server without TCP during initdb, so wait for TCP inside the
    # container, then for colima's host port forward, which can lag behind it.
    i=0
    until docker exec "$NAME" pg_isready -q -h 127.0.0.1 -U postgres; do
      i=$((i + 1)); [ "$i" -lt 120 ] || { echo "server did not start" >&2; exit 1; }
      sleep 0.5
    done
    until nc -z 127.0.0.1 "$PORT" 2>/dev/null; do
      i=$((i + 1)); [ "$i" -lt 240 ] || { echo "host port $PORT did not open" >&2; exit 1; }
      sleep 0.5
    done
    echo "$NAME is up on 127.0.0.1:$PORT"
    ;;
  down)
    docker rm -f -v "$NAME" >/dev/null 2>&1 || true
    rm -f "$INSTANCE"
    echo "$NAME removed"
    ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac
