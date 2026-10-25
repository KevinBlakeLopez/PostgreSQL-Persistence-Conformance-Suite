#!/bin/zsh
# Adversarial verification batch, in three lanes with their own ports.
# Lane A needs the fault proxy (third port).
# Usage: run-verify.sh <venvs dir> priority|rest
set -u
here=${0:A:h}
v=$1
logs=$here/../outputs/verify/_batch-logs
mkdir -p $logs
x() { # venv build ports experiment args...
  local venv=$1 build=$2 ports=$3; shift 3
  PPCS_DRAMATIQ_BUILD=$build $v/$venv/bin/python -I $here/verify.py "$@" --ports $ports
}
R="2.2.1 (PyPI)"
F1A="master 08d711a + fix-d4-a1"; F2A="master 08d711a + fix-d4-a2"; FR="master 08d711a + fix-redis-reconnect"
# The experiments most likely to change a conclusion, one repetition each.
priA() {
  local p=56391,56392,56393
  x rel221 $R $p f1 --variant lostreply --form host --reps 1
  x rel221 $R $p f3 --variant blackhole --form url --reps 1
  x fix-d4-a2 $F2A $p f1 --variant a2-lostreply --form url --reps 1 --tag fix-d4-a2
}
priB() {
  local p=56394,56395
  x rel221 $R $p f1 --variant ackfail-recover --reps 1
  x rel221 $R $p f1 --variant ackfail-kill --reps 1
  x rel221 $R $p f4 --variant nobarrier-asyncio --reps 1
  x fix-d4-a1 $F1A $p f1 --variant a1-nackfail-kill --reps 1 --tag fix-d4-a1
  x fix-d4-a2 $F2A $p f1 --variant a2-shutdown --reps 1 --tag fix-d4-a2
}
priC() {
  local p=56396,56397
  x rel221 $R $p f2 --variant secondworker --reps 1
  x rel221 $R $p f2 --variant secondworker-shorthb --reps 1
  x fix-redis-reconnect $FR $p f2 --variant secondworker-shorthb --reps 1 --tag fix-redis-reconnect
}
laneA() {
  local p=56391,56392,56393
  x rel221 $R $p f1 --variant lostreply --form url --reps 2
  x rel221 $R $p f1 --variant lostreply --form host --reps 2
  x fix-d4-a2 "master 08d711a + fix-d4-a2" $p f1 --variant a2-lostreply --form url --reps 2 --tag fix-d4-a2
  x rel221 $R $p f3 --variant blackhole --form url --reps 2
  x pr895 "master 08d711a + PR #895 (redis.py only)" $p f3 --variant blackhole --form url --reps 1 --tag pr895
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f3 --variant blackhole --form url --reps 1 --tag fix-redis-reconnect
  x rel221 $R $p f2 --variant promotion-lostreply --form url --reps 1
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant promotion-lostreply --form url --reps 1 --tag fix-redis-reconnect
}
laneB() {
  local p=56394,56395
  x rel221 $R $p f1 --variant ackfail-recover --reps 2
  x rel221 $R $p f1 --variant ackfail-kill --reps 2
  x fix-d4-a1 "master 08d711a + fix-d4-a1" $p f1 --variant a1-nackfail-kill --reps 2 --tag fix-d4-a1
  x fix-d4-a2 "master 08d711a + fix-d4-a2" $p f1 --variant a2-shutdown --reps 2 --tag fix-d4-a2
  for var in retryexc lastretry exhausted throws; do x rel221 $R $p f1 --variant $var --reps 1; done
  x rel221 $R $p f1send --variant outage
  x fix-d4-a2 "master 08d711a + fix-d4-a2" $p f1send --variant outage --tag fix-d4-a2
  x rel221 $R $p f4 --variant nobarrier --reps 2
  x rel221 $R $p f4 --variant nobarrier-asyncio --reps 2
  x rel221 $R $p f4 --variant pause-boundary --form url --reps 1
  x rel221 $R $p f4 --variant pause-boundary-asyncio --form url --reps 1
  x rel221 $R $p f4 --variant barrier-asyncio-first --reps 1
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f4 --variant nobarrier-asyncio --reps 1 --tag fix-redis-reconnect
}
laneC() {
  local p=56396,56397
  x rel221 $R $p f2 --variant secondworker --reps 2
  x rel221 $R $p f2 --variant secondworker-shorthb --reps 2
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant secondworker-shorthb --reps 2 --tag fix-redis-reconnect
  x rel221 $R $p f2 --variant sigstop --reps 2
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant sigstop --reps 2 --tag fix-redis-reconnect
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant eta-during-outage --reps 1 --tag fix-redis-reconnect
  x rel221 $R $p f2 --variant eta-during-outage --reps 1
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant repeated --reps 1 --tag fix-redis-reconnect
  x fix-redis-reconnect "master 08d711a + fix-redis-reconnect" $p f2 --variant shutdown-during-outage --reps 1 --tag fix-redis-reconnect
  x rel221 $R $p f2 --variant fault --reps 1
  x rel221 $R $p f3 --variant twoworkers-pause --form url --reps 1
  x rel221 $R $p f3 --variant pause --form url --reps 1
}
if [ "$2" = priority ]; then
  priA > $logs/priA.log 2>&1 &
  priB > $logs/priB.log 2>&1 &
  priC > $logs/priC.log 2>&1 &
else
  laneA > $logs/laneA.log 2>&1 &
  laneB > $logs/laneB.log 2>&1 &
  laneC > $logs/laneC.log 2>&1 &
fi
wait
echo "verify batch finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
