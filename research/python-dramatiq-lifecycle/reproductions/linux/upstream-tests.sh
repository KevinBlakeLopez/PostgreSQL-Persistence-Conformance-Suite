#!/bin/bash
# Runs inside the container. Dramatiq's own Redis broker, worker and Retries
# tests against master and each candidate fix, with Redis on the container's
# loopback port 6379. RabbitMQ and memcached tests skip (CI is unset).
set -uo pipefail
out=/study/outputs/linux/upstream-tests
mkdir -p $out
redis-server --port 6379 --bind 127.0.0.1 --save '' --appendonly no --daemonize yes --logfile /tmp/redis-tests.log
sleep 0.5
for name in master fix-d4-a1 fix-d4-a2 fix-redis-reconnect; do
  tree=$name; [ "$name" = master ] && tree=dramatiq
  ( cd /src/$tree && /venv/test-$name/bin/python -m pytest -o addopts='' -p no:cacheprovider -q \
      tests/test_redis.py tests/test_worker.py tests/middleware/test_retries.py ) > $out/$name.txt 2>&1
  echo "$name: $(tail -1 $out/$name.txt)"
done
redis-cli -p 6379 shutdown nosave >/dev/null 2>&1 || true
