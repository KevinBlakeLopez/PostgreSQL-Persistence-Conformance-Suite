#!/bin/bash
# Inside a disposable python:3.13-slim container with the study at /study.
# Builds source trees for master 08d711a, each candidate fix, PR #895's
# redis.py change alone, and two fix combinations, plus one test venv
# (Dramatiq is imported from each tree, not installed).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1
apt-get update -qq
apt-get install -y -qq redis-server git procps build-essential libmemcached-dev zlib1g-dev >/dev/null
M=08d711a7611077e3d07ce1006349bc9342ada6e8
git clone -q https://github.com/Bogdanp/dramatiq /src/master
git -C /src/master checkout -q $M
git -C /src/master fetch -q origin pull/895/head:pr895
mk() { git -C /src/master worktree add -q --detach /src/$1 $M; }
for fix in fix-d4-a1 fix-d4-a2 fix-redis-reconnect; do mk $fix; git -C /src/$fix apply /study/reproductions/fixes/$fix.diff; done
mk pr895
git -C /src/master diff $(git -C /src/master merge-base $M pr895) pr895 -- dramatiq/brokers/redis.py | git -C /src/pr895 apply
mk combo-a1-reconnect
git -C /src/combo-a1-reconnect apply /study/reproductions/fixes/fix-d4-a1.diff /study/reproductions/fixes/fix-redis-reconnect.diff
mk combo-a2-reconnect
git -C /src/combo-a2-reconnect apply /study/reproductions/fixes/fix-d4-a2.diff /study/reproductions/fixes/fix-redis-reconnect.diff
python -m venv /venv/test && /venv/test/bin/pip install -q 'redis==8.1.0' pika pylibmc pytest pytest-cov
for t in master fix-d4-a1 fix-d4-a2 fix-redis-reconnect pr895 combo-a1-reconnect combo-a2-reconnect; do
  echo "$t: $(git -C /src/$t diff --stat | tail -1)"
done
redis-server --version; python --version; cat /etc/debian_version; uname -srm
