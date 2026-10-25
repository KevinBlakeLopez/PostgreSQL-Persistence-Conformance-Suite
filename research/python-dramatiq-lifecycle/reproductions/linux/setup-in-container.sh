#!/bin/bash
# Runs inside a disposable python:3.13-slim container with the study mounted
# at /study. Builds the same environments as on macOS: Dramatiq 2.2.1 from
# PyPI, master at 08d711a, and master plus each candidate fix, all with
# redis-py 8.1.0 and the network guard. Test environments for Dramatiq's own
# test suite are separate and have no guard: the suite uses Redis on the
# container's own loopback port 6379.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1
apt-get update -qq
apt-get install -y -qq redis-server git procps build-essential libmemcached-dev zlib1g-dev >/dev/null
git clone -q https://github.com/Bogdanp/dramatiq /src/dramatiq
git -C /src/dramatiq checkout -q 08d711a7611077e3d07ce1006349bc9342ada6e8
for fix in fix-d4-a1 fix-d4-a2 fix-redis-reconnect; do
  git -C /src/dramatiq worktree add -q --detach /src/$fix 08d711a7611077e3d07ce1006349bc9342ada6e8
  git -C /src/$fix apply /study/reproductions/fixes/$fix.diff
done
python -m venv /venv/rel221 && /venv/rel221/bin/pip install -q 'dramatiq[redis]==2.2.1' 'redis==8.1.0'
for tree in dramatiq fix-d4-a1 fix-d4-a2 fix-redis-reconnect; do
  name=$tree; [ "$tree" = dramatiq ] && name=master
  python -m venv /venv/$name && /venv/$name/bin/pip install -q "/src/${tree}[redis]" 'redis==8.1.0'
  python -m venv /venv/test-$name && /venv/test-$name/bin/pip install -q 'redis==8.1.0' pika pylibmc pytest pytest-cov
done
for venv in rel221 master fix-d4-a1 fix-d4-a2 fix-redis-reconnect; do
  /study/reproductions/netguard/install.sh /venv/$venv
done
redis-server --version
python --version
cat /etc/debian_version
uname -srm
