#!/bin/sh
# Removes this study's two MySQL containers and ../.mysd-instance.json. Touches no other compose project.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
# compose.yaml interpolates these even for `down`. The real passwords are not needed to remove the containers.
export MYSD_ROOT_PASSWORD="${MYSD_ROOT_PASSWORD:-unused}"
export MYSD_PASSWORD="${MYSD_PASSWORD:-unused}"
docker compose -p mysd -f "$DIR/compose.yaml" down --volumes --remove-orphans
rm -f "$DIR/.mysd-instance.json"
echo "Servers are down."
