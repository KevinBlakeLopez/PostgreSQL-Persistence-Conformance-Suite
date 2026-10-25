#!/bin/bash
# Inside the container: Dramatiq's suite (minus benchmarks and the study's
# own regression module) on master and the fixes, with a 60 s per-test
# timeout so a hanging test is recorded as a failure instead of stalling
# the run. RabbitMQ and memcached tests skip without servers.
set -uo pipefail
out=/study/outputs/verify/linux-regression
redis-cli -p 6379 ping >/dev/null 2>&1 || redis-server --port 6379 --bind 127.0.0.1 --save '' --appendonly no --daemonize yes --logfile /tmp/redis-tests.log
sleep 0.5
for t in "$@"; do
  ( cd /src/$t && /venv/test/bin/python -m pytest -o addopts='' -p no:cacheprovider -v -rfE --timeout=60 \
      tests --ignore=tests/benchmarks --ignore=tests/test_ppcs_lifecycle.py ) > $out/suite-$t.txt 2>&1
  echo "suite $t: $(tail -1 $out/suite-$t.txt)"
done
