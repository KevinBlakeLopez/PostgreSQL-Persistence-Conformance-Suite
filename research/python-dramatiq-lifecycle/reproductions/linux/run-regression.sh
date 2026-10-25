#!/bin/bash
# Inside the container: the study's regression tests on every tree, then
# Dramatiq's suite (minus benchmarks; RabbitMQ and memcached tests skip
# without servers) on master and the fixes. Redis is the container's own.
set -uo pipefail
out=/study/outputs/verify/linux-regression
mkdir -p $out
redis-server --port 6379 --bind 127.0.0.1 --save '' --appendonly no --daemonize yes --logfile /tmp/redis-tests.log
sleep 0.5
for t in master fix-d4-a1 fix-d4-a2 fix-redis-reconnect pr895 combo-a1-reconnect combo-a2-reconnect; do
  cp /study/reproductions/regression-tests/test_ppcs_lifecycle.py /src/$t/tests/
  ( cd /src/$t && /venv/test/bin/python -m pytest -o addopts='' -p no:cacheprovider -q -rA tests/test_ppcs_lifecycle.py ) > $out/regression-$t.txt 2>&1
  echo "regression $t: $(grep -E '^(PASSED|FAILED|ERROR) ' $out/regression-$t.txt | awk '{print $1, $2}' | sed 's#tests/test_ppcs_lifecycle.py::##' | tr '\n' ' ')"
done
if [ "${1:-}" = full ]; then
  for t in master fix-d4-a1 fix-d4-a2 fix-redis-reconnect combo-a1-reconnect combo-a2-reconnect; do
    ( cd /src/$t && /venv/test/bin/python -m pytest -o addopts='' -p no:cacheprovider -q tests --ignore=tests/benchmarks --ignore=tests/test_ppcs_lifecycle.py ) > $out/suite-$t.txt 2>&1
    echo "suite $t: $(tail -1 $out/suite-$t.txt)"
  done
fi
redis-cli -p 6379 shutdown nosave >/dev/null 2>&1 || true
