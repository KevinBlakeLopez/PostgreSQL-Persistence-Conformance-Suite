#!/bin/sh
# Removes the disposable server and its instance file. The data directory is a tmpfs, so nothing remains.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
PPCS_INSTANCE_TOKEN=unused PPCS_PGPASSWORD=unused docker compose -f "$DIR/compose.yaml" down --volumes --remove-orphans
rm -f "$DIR/.ppcs-instance.json"
