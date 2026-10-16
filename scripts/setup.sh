#!/bin/sh
# Installs the harness and every JavaScript adapter from its committed lockfile.
#
# - --frozen-lockfile refuses to change a lockfile, so what is installed is exactly what was recorded.
# - Each adapter is its own project with its own lockfile, so adapters cannot change one another's dependency graphs.
# - pnpm does not run dependencies' install scripts unless they are allow-listed, and no project here allow-lists any.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
for project in "$DIR" "$DIR"/adapters/*; do
  [ -f "$project/package.json" ] || continue
  echo "== ${project#"$DIR"}/"
  (cd "$project" && pnpm install --frozen-lockfile --ignore-workspace)
done
