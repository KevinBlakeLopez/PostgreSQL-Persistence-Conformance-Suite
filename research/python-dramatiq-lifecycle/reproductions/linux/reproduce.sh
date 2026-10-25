#!/bin/bash
# Runs inside the container after setup-in-container.sh: the main
# reproductions on Linux, with evidence under outputs/linux/.
set -u
export PPCS_REDIS_SERVER=/usr/bin/redis-server PPCS_OUTPUTS_SUBDIR=linux
cd /study/reproductions
p=56391,56392
x() { local venv=$1 build=$2; shift 2; PPCS_DRAMATIQ_BUILD="$build" /venv/$venv/bin/python -I experiments.py "$@" --ports $p; }
x rel221 "2.2.1 (PyPI)" d4 --variant fault --reps 3
x rel221 "2.2.1 (PyPI)" d4 --variant fault-actor-redis --reps 1
x rel221 "2.2.1 (PyPI)" d4 --variant control-ok --reps 1
x rel221 "2.2.1 (PyPI)" n1 --variant fault-aggressive --reps 3
x rel221 "2.2.1 (PyPI)" n2 --variant fault --form url --reps 3
x rel221 "2.2.1 (PyPI)" d7 --variant fault --reps 3
x rel221 "2.2.1 (PyPI)" d7 --variant fault-asyncio --reps 1
x master "master 08d711a" d4 --variant fault --reps 1 --tag master
x fix-d4-a1 "master 08d711a + fix-d4-a1" d4 --variant fault --reps 1 --tag fix-d4-a1
x fix-d4-a2 "master 08d711a + fix-d4-a2" d4 --variant fault --reps 1 --tag fix-d4-a2
x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" n1 --variant fault-aggressive --reps 1 --tag fix-redis-reconnect
x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" n2 --variant fault --form url --reps 1 --tag fix-redis-reconnect
x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" d7 --variant fault-asyncio --reps 1 --tag fix-redis-reconnect
echo "linux reproductions finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
