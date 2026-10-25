#!/bin/zsh
# Repetitions and controls for D4, N1, N2 and D7, in four lanes with their
# own ports. Usage: run-batch.sh <rel221 venv> <master venv>
set -u
here=${0:A:h}
rel=$1/bin/python
mst=$2/bin/python
logs=$here/../outputs/_batch-logs
mkdir -p $logs
x() { # python build ports experiment args...
  local py=$1 build=$2 ports=$3; shift 3
  PPCS_DRAMATIQ_BUILD=$build $py -I $here/experiments.py "$@" --ports $ports
}
laneA() {
  local p=56391,56392
  x $rel "2.2.1 (PyPI)" $p d4 --variant fault --reps 3
  x $rel "2.2.1 (PyPI)" $p d4 --variant control-ok --reps 3
  x $rel "2.2.1 (PyPI)" $p d4 --variant control-kill --reps 3
  x $rel "2.2.1 (PyPI)" $p d4 --variant control-noretries --reps 3
  x $rel "2.2.1 (PyPI)" $p d4 --variant fault --form url --reps 3
  x $rel "2.2.1 (PyPI)" $p d4 --variant fault-actor-redis --reps 3
  x $mst "master 08d711a" $p d4 --variant fault --reps 3 --tag master
}
laneB() {
  local p=56393,56394
  x $rel "2.2.1 (PyPI)" $p n1 --variant fault-aggressive --reps 3
  x $rel "2.2.1 (PyPI)" $p n1 --variant control-norestart --reps 3
  x $rel "2.2.1 (PyPI)" $p n1 --variant control-crash --reps 3
  x $rel "2.2.1 (PyPI)" $p n1 --variant fault-aggressive --form url --reps 3
  x $mst "master 08d711a" $p n1 --variant fault-aggressive --reps 3 --tag master
}
laneC() {
  local p=56395,56396
  x $rel "2.2.1 (PyPI)" $p n2 --variant fault --form url --reps 3
  x $rel "2.2.1 (PyPI)" $p n2 --variant control-shortpause --form url --reps 3
  x $mst "master 08d711a" $p n2 --variant fault --form url --reps 3 --tag master
  x $rel "2.2.1 (PyPI)" $p d7 --variant fault --reps 3
  x $rel "2.2.1 (PyPI)" $p d7 --variant control --reps 3
  x $rel "2.2.1 (PyPI)" $p d7 --variant fault-asyncio --reps 3
  x $rel "2.2.1 (PyPI)" $p d7 --variant control-asyncio --reps 3
  x $mst "master 08d711a" $p d7 --variant fault --reps 3 --tag master
}
laneD() {
  local p=56397,56398
  x $rel "2.2.1 (PyPI)" $p n1 --variant fault-default --reps 1 --observe 300
  x $rel "2.2.1 (PyPI)" $p d7 --variant fault-defaultrecovery --reps 1
}
laneA > $logs/laneA.log 2>&1 &
laneB > $logs/laneB.log 2>&1 &
laneC > $logs/laneC.log 2>&1 &
laneD > $logs/laneD.log 2>&1 &
wait
echo "batch finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
