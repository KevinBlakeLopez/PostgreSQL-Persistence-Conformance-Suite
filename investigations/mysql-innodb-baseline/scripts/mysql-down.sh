#!/bin/sh
# Removes the disposable MySQL baseline containers. Does not select the PPCS compose project.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
# compose.yaml interpolates these even for `down`. The real passwords are not required to remove the containers.
export MPCS_ROOT_PASSWORD="${MPCS_ROOT_PASSWORD:-unused}"
export MPCS_PASSWORD="${MPCS_PASSWORD:-unused}"
docker compose -p mpcs-baseline -f "$DIR/compose.yaml" down --volumes --remove-orphans
rm -f "$DIR/.mpcs-instance.json"
echo "MySQL baseline servers are down."
