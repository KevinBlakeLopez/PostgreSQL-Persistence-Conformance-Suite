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
  # --ignore-workspace keeps an adapter out of a parent workspace. pnpm 12 reads allowBuilds only from
  # pnpm-workspace.yaml, and that flag drops the file, so an adapter that denies dependency builds
  # installs without it.
  if [ -f "$project/pnpm-workspace.yaml" ]; then
    (cd "$project" && pnpm install --frozen-lockfile)
  else
    (cd "$project" && pnpm install --frozen-lockfile --ignore-workspace)
  fi
  if [ -f "$project/schema.prisma" ]; then
    echo "== ${project#"$DIR"}/ prisma generate"
    (cd "$project" && pnpm exec prisma generate)
  fi
done
# The Go adapters are not part of the Node install. When Go is on PATH, download the
# pinned module so later `go run -mod=readonly` does not touch go.sum. A machine
# without Go still installs the JavaScript adapters.
if command -v go >/dev/null 2>&1 && [ -f "$DIR/adapters/go/go.mod" ]; then
  echo "== /adapters/go/"
  (cd "$DIR/adapters/go" && go mod download)
fi
