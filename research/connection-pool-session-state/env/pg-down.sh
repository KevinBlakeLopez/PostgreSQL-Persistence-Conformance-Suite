#!/bin/sh
# Removes this investigation's container, and nothing else. Optionally saves its server log first.
#
# Usage: env/pg-down.sh [log-file]
set -eu
NAME=ppcs-ssc-pg
export DOCKER_CONTEXT="${DOCKER_CONTEXT:-colima}"
if [ "${1:-}" != "" ]; then
  docker logs "$NAME" > "$1" 2>&1
fi
docker rm -f -v "$NAME" >/dev/null
