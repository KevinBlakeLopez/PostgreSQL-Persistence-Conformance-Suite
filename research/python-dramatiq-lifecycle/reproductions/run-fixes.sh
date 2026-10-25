#!/bin/zsh
# Candidate fixes against the reproductions and their controls, plus the
# unpatched D4 fault with the durability check. Two lanes with their own
# ports. Usage: run-fixes.sh <venvs dir>
set -u
here=${0:A:h}
venvs=$1
logs=$here/../outputs/_batch-logs
mkdir -p $logs
x() { # venv build ports experiment args...
  local venv=$1 build=$2 ports=$3; shift 3
  PPCS_DRAMATIQ_BUILD=$build $venvs/$venv/bin/python -I $here/experiments.py "$@" --ports $ports
}
laneF1() {
  local p=56395,56396
  for fix in fix-d4-a1 fix-d4-a2; do
    x $fix "master 08d711a + $fix" $p d4 --variant fault --reps 3 --tag $fix
    x $fix "master 08d711a + $fix" $p d4 --variant fault-actor-redis --reps 3 --tag $fix
    x $fix "master 08d711a + $fix" $p d4 --variant control-ok --reps 3 --tag $fix
  done
  x rel221 "2.2.1 (PyPI)" $p d4 --variant fault --reps 3 --tag durability
}
laneF2() {
  local p=56397,56398 fix=fix-redis-reconnect
  x $fix "master 08d711a + $fix" $p n1 --variant fault-aggressive --reps 3 --tag $fix
  x $fix "master 08d711a + $fix" $p n1 --variant control-norestart --reps 1 --tag $fix
  x $fix "master 08d711a + $fix" $p n2 --variant fault --form url --reps 3 --tag $fix
  x $fix "master 08d711a + $fix" $p n2 --variant control-shortpause --form url --reps 1 --tag $fix
  x $fix "master 08d711a + $fix" $p d7 --variant fault --reps 3 --tag $fix
  x $fix "master 08d711a + $fix" $p d7 --variant fault-asyncio --reps 3 --tag $fix
  x $fix "master 08d711a + $fix" $p d7 --variant control --reps 1 --tag $fix
  x $fix "master 08d711a + $fix" $p d4 --variant control-ok --reps 1 --tag $fix
  x $fix "master 08d711a + $fix" $p d4 --variant fault --reps 1 --tag $fix
}
laneF1 > $logs/laneF1.log 2>&1 &
laneF2 > $logs/laneF2.log 2>&1 &
wait
echo "fixes finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
