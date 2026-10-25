#!/bin/bash
# Inside the container: the study's regression tests on one extra tree,
# built from master 08d711a plus one diff. Usage: run-regression-one.sh <tree> <diff>
set -uo pipefail
t=$1; diff=$2
M=08d711a7611077e3d07ce1006349bc9342ada6e8
out=/study/outputs/verify/linux-regression
if [ ! -d /src/$t ]; then
  git -C /src/master worktree add -q --detach /src/$t $M
  git -C /src/$t apply /study/reproductions/fixes/$diff
fi
redis-cli -p 6379 ping >/dev/null 2>&1 || redis-server --port 6379 --bind 127.0.0.1 --save '' --appendonly no --daemonize yes --logfile /tmp/redis-tests.log
cp /study/reproductions/regression-tests/test_ppcs_lifecycle.py /src/$t/tests/
( cd /src/$t && /venv/test/bin/python -m pytest -o addopts='' -p no:cacheprovider -q -rA tests/test_ppcs_lifecycle.py ) > $out/regression-$t.txt 2>&1
grep -E '^(PASSED|FAILED|ERROR) ' $out/regression-$t.txt
