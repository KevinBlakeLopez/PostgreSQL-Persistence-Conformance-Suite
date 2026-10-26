#!/bin/sh
# Starts the two disposable MySQL 8.4 servers in ../compose.yaml and writes ../.mysd-instance.json.
#
# Adapted from investigations/mysql-innodb-baseline/scripts/mysql-up.sh. A random token is stored in each
# server, and run.mjs refuses a server that does not have it. Passwords are random per start.
# .mysd-instance.json is gitignored and mode 0600.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
INSTANCE="$DIR/.mysd-instance.json"
TOKEN="mysd-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
ROOT_PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
export MYSD_ROOT_PASSWORD="$ROOT_PASSWORD" MYSD_PASSWORD="$PASSWORD"

rm -f "$INSTANCE"
docker compose -p mysd -f "$DIR/compose.yaml" down --volumes --remove-orphans >/dev/null 2>&1 || true
docker compose -p mysd -f "$DIR/compose.yaml" up --detach --wait --wait-timeout 180

wait_port() {
  port="$1"
  i=0
  until node -e "require('net').connect(${port}, '127.0.0.1').on('connect', () => process.exit(0)).on('error', () => process.exit(1))" 2>/dev/null; do
    i=$((i + 1))
    [ "$i" -gt 60 ] && { echo "Port ${port} is not reachable from the host" >&2; exit 1; }
    sleep 1
  done
}
wait_port 13316
wait_port 13317

stamp() {
  container="$1"
  docker exec -e MYSQL_PWD="$ROOT_PASSWORD" "$container" \
    mysql -uroot -e "CREATE DATABASE IF NOT EXISTS mysd_meta; CREATE TABLE IF NOT EXISTS mysd_meta.instance (id TINYINT PRIMARY KEY, token VARCHAR(64) NOT NULL); INSERT INTO mysd_meta.instance (id, token) VALUES (1, '${TOKEN}') ON DUPLICATE KEY UPDATE token = VALUES(token);"
}

stamp mysd-mysql
stamp mysd-mysql-rb-timeout

IMAGE=$(docker inspect mysd-mysql --format '{{.Config.Image}}')
IMAGE_ID=$(docker inspect mysd-mysql --format '{{.Image}}')
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
umask 077
cat > "$INSTANCE" <<EOF
{
  "token": "${TOKEN}",
  "image": "${IMAGE}",
  "image_id": "${IMAGE_ID}",
  "started_at": "${STARTED}",
  "user": "mysd",
  "password": "${PASSWORD}",
  "root_user": "root",
  "root_password": "${ROOT_PASSWORD}",
  "database": "mysd",
  "off": {
    "host": "127.0.0.1",
    "port": 13316,
    "container": "mysd-mysql",
    "innodb_rollback_on_timeout": "server default"
  },
  "on": {
    "host": "127.0.0.1",
    "port": 13317,
    "container": "mysd-mysql-rb-timeout",
    "innodb_rollback_on_timeout": "ON"
  }
}
EOF

echo "Servers are up."
docker exec -e MYSQL_PWD="$ROOT_PASSWORD" mysd-mysql mysql -uroot -N -e "SELECT VERSION(), @@global.innodb_rollback_on_timeout, @@global.transaction_isolation, @@global.autocommit, @@global.innodb_lock_wait_timeout"
docker exec -e MYSQL_PWD="$ROOT_PASSWORD" mysd-mysql-rb-timeout mysql -uroot -N -e "SELECT VERSION(), @@global.innodb_rollback_on_timeout"
