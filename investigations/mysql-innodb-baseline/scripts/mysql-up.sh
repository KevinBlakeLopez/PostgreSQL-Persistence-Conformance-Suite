#!/bin/sh
# Starts the disposable MySQL 8.4 servers (compose.yaml in this directory) and writes .mpcs-instance.json.
#
# Does not call the repository's scripts/pg-up.sh and does not select the PPCS compose project.
# A random token is stored in each server. src/run-all.mjs refuses a server that does not have that token.
# Passwords are random per start. .mpcs-instance.json is gitignored.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
INSTANCE="$DIR/.mpcs-instance.json"
TOKEN="mpcs-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
ROOT_PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
export MPCS_ROOT_PASSWORD="$ROOT_PASSWORD" MPCS_PASSWORD="$PASSWORD"

rm -f "$INSTANCE"
docker compose -p mpcs-baseline -f "$DIR/compose.yaml" down --volumes --remove-orphans >/dev/null 2>&1 || true
docker compose -p mpcs-baseline -f "$DIR/compose.yaml" up --detach --wait --wait-timeout 180

wait_port() {
  port="$1"
  i=0
  until node -e "require('net').connect(${port}, '127.0.0.1').on('connect', () => process.exit(0)).on('error', () => process.exit(1))" 2>/dev/null; do
    i=$((i + 1))
    [ "$i" -gt 60 ] && { echo "Port ${port} is not reachable from the host" >&2; exit 1; }
    sleep 1
  done
}
wait_port 13306
wait_port 13307

stamp() {
  container="$1"
  docker exec -e MYSQL_PWD="$ROOT_PASSWORD" "$container" \
    mysql -uroot -e "CREATE DATABASE IF NOT EXISTS mpcs_meta; CREATE TABLE IF NOT EXISTS mpcs_meta.instance (id TINYINT PRIMARY KEY, token VARCHAR(64) NOT NULL); INSERT INTO mpcs_meta.instance (id, token) VALUES (1, '${TOKEN}') ON DUPLICATE KEY UPDATE token = VALUES(token);"
}

stamp mpcs-baseline-mysql
stamp mpcs-baseline-mysql-rb-timeout

IMAGE=$(docker inspect mpcs-baseline-mysql --format '{{.Config.Image}}')
IMAGE_ID=$(docker inspect mpcs-baseline-mysql --format '{{.Image}}')
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
umask 077
cat > "$INSTANCE" <<EOF
{
  "token": "${TOKEN}",
  "image": "${IMAGE}",
  "image_id": "${IMAGE_ID}",
  "started_at": "${STARTED}",
  "user": "mpcs",
  "password": "${PASSWORD}",
  "root_user": "root",
  "root_password": "${ROOT_PASSWORD}",
  "database": "mpcs",
  "default": {
    "host": "127.0.0.1",
    "port": 13306,
    "container": "mpcs-baseline-mysql",
    "innodb_rollback_on_timeout": "server default"
  },
  "rollback_on_timeout": {
    "host": "127.0.0.1",
    "port": 13307,
    "container": "mpcs-baseline-mysql-rb-timeout",
    "innodb_rollback_on_timeout": "ON"
  }
}
EOF

echo "MySQL baseline servers are up."
docker exec -e MYSQL_PWD="$ROOT_PASSWORD" mpcs-baseline-mysql mysql -uroot -N -e "SELECT VERSION()"
docker exec -e MYSQL_PWD="$ROOT_PASSWORD" mpcs-baseline-mysql mysql -uroot -N -e "SELECT @@global.innodb_rollback_on_timeout, @@global.transaction_isolation, @@global.autocommit, @@global.innodb_lock_wait_timeout"
docker exec -e MYSQL_PWD="$ROOT_PASSWORD" mpcs-baseline-mysql-rb-timeout mysql -uroot -N -e "SELECT @@global.innodb_rollback_on_timeout"
