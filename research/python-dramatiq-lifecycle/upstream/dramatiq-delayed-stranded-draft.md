# Draft: Dramatiq, new issue on Bogdanp/dramatiq

Prepared 2026-10-28. Not approved to post. Not filed. Tracker item DM2.

The filing package is [`f2-delayed-stranded-filing.md`](f2-delayed-stranded-filing.md). Everything between the two rules below is the proposed issue body. The rest of this file is internal.

**Proposed title:** `Delayed messages already fetched by a live worker never run after Redis restarts`

**Destination:** a new issue at https://github.com/Bogdanp/dramatiq/issues/new?template=bug_report.md. Link #527 in the body. Do not reopen #527. No pull request.

**Re-checked 2026-10-28, before this draft.** PyPI `latest` was still 2.2.1. `master` was still `d3138e2ea824` (2026-10-27, the Dependabot bump). #527 was still closed, with no comment after 2023-02-25. Issues updated since 2026-10-27 were #911 (closed, a different shutdown hang) and #894 (open, `redis.TimeoutError`). Neither is this report. The script below was not re-run.

**Before posting:**

1. Approval of the exact title, body, and destination.
2. Rewrite the AI sentence so you can stand behind it. Dramatiq's contributing guide asks for a human author.
3. Search again for an issue or pull request opened after 2026-10-28 that reports prefetched delayed messages sitting in a live worker's ack set. If one exists, comment there instead.
4. If PyPI is no longer 2.2.1, run the script on that release before describing it.
5. If `master` has a new commit on `dramatiq/worker.py` after `fb252f92bbc1`, re-read lines 325–327 and 486.

---

I used AI tools to help investigate this and to draft this report.

## What OS are you using?

macOS, and the same restart on Linux.

## What version of Python are you using?

CPython 3.13.11 on macOS, and 3.13.17 on Linux.

## What version of Dramatiq are you using?

2.2.1. The same restart also left the messages stranded on `master` at `08d711a`. On current `master` (`d3138e2`, 2026-10-27) the handler described below is still at `dramatiq/worker.py` lines 325–327 and 486. That commit does not change `worker.py`.

## What Broker are you using?

Redis, with redis-py 8.1.0 and Redis 8.6.2. The script starts its own `redis-server` with AOF and `appendfsync always`.

## What did you do?

A worker fetches a delayed message, Redis is stopped and started again, and the worker stays up.

The script sets a 2 second heartbeat timeout and runs maintenance on every broker call. That is stricter than Dramatiq's defaults (60 seconds, and maintenance on about 1 call in 1,000). If the messages came back because the heartbeat timed out, this script would show that within a few seconds.

```python
import argparse
import subprocess
import tempfile
import time

import dramatiq
import redis
from dramatiq import Worker
from dramatiq.brokers.redis import MAINTENANCE_SCALE, RedisBroker

parser = argparse.ArgumentParser()
parser.add_argument("--redis-server", default="redis-server")
parser.add_argument("--port", type=int, default=56391)
args = parser.parse_args()

data_dir = tempfile.mkdtemp()
command = [args.redis_server, "--port", str(args.port), "--bind", "127.0.0.1", "--dir", data_dir,
           "--appendonly", "yes", "--appendfsync", "always", "--save", ""]
client = redis.Redis(port=args.port, decode_responses=True)


def start_redis():
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL)
    for _ in range(200):
        try:
            client.ping()
            return proc
        except redis.ConnectionError:
            time.sleep(0.05)
    raise RuntimeError("redis-server did not start")


def acks():
    return {k: sorted(client.smembers(k)) for k in client.scan_iter("dramatiq:__acks__.*")}


runs = []
broker = RedisBroker(host="127.0.0.1", port=args.port, heartbeat_timeout=2000, maintenance_chance=MAINTENANCE_SCALE)
dramatiq.set_broker(broker)


@dramatiq.actor
def scheduled():
    runs.append(time.time())


server = start_redis()
worker = Worker(broker, worker_threads=1)
worker.start()
message = scheduled.send_with_options(delay=10000)
eta = message.options["eta"] / 1000
while not acks():
    time.sleep(0.1)
print("fetched by the worker: %s" % acks())

server.terminate()
server.wait()
print("Redis stopped for 10 s")
time.sleep(10)
server = start_redis()
print("Redis started again")

time.sleep(max(0, eta + 30 - time.time()))
age = time.time() * 1000 - client.zscore("dramatiq:__heartbeats__", broker.broker_id)
print("30 s after the ETA: runs=%d, DQ list=%s, ack sets=%s, worker heartbeat age=%d ms"
      % (len(runs), client.lrange("dramatiq:default.DQ", 0, -1), acks(), age))
worker.stop()
print("after worker.stop(): runs=%d, ack sets=%s" % (len(runs), acks()))
print("dramatiq %s, redis-py %s, redis-server %s" % (dramatiq.__version__, redis.__version__, client.info()["redis_version"]))
server.terminate()
server.wait()
```

I also restarted Redis while a worker held three messages that had a 25 second delay, with Redis down for 15 seconds. Those runs are the counts below.

## What did you expect would happen?

#527 is the same symptom on Dramatiq 1.14.0: a delayed job did not run after Redis was killed and restarted, and it ran a few hours later. The explanation there was that a Redis crash is like a worker crash, and the heartbeat timeout has to pass before the messages are put back.

With the 2 second timeout in the script, and maintenance on every call, I expected the message to be back on `default.DQ` and to run once Redis was up again.

## What happened?

The worker logs the connection error and reconnects. The actor does not run. Thirty seconds after the ETA the message is still in that worker's delay-queue ack set, the delay queue is empty, and the heartbeat is 597 ms old. `Worker.stop()` leaves it there.

```text
fetched by the worker: {'dramatiq:__acks__.019509e3-8a95-4d50-849f-3017f2a39b16.default.DQ': ['e1d80c0e-0f0a-4d71-be2a-ec49ad0e8500']}
Redis stopped for 10 s
Redis started again
30 s after the ETA: runs=0, DQ list=[], ack sets={'dramatiq:__acks__.019509e3-8a95-4d50-849f-3017f2a39b16.default.DQ': ['e1d80c0e-0f0a-4d71-be2a-ec49ad0e8500']}, worker heartbeat age=597 ms
after worker.stop(): runs=0, ack sets={'dramatiq:__acks__.019509e3-8a95-4d50-849f-3017f2a39b16.default.DQ': ['e1d80c0e-0f0a-4d71-be2a-ec49ad0e8500']}
dramatiq 2.2.1, redis-py 8.1.0, redis-server 8.6.2
```

The three-message restart did the same on 2.2.1 and on `master` `08d711a`, on macOS and on Linux. One run used Dramatiq's default 60 second timeout and default maintenance chance. The messages were still in the owner's ack set 300 seconds after the ETA, and the heartbeat was at most 688 ms old.

A second worker did not pick them up while the owner stayed alive and kept calling Redis. With maintenance on every call and the default 60 second timeout, that was 3 of 3. They did get recovered in two narrower cases: another worker's maintenance ran first, with a 2 second timeout, before the owner's first call after the outage (1 of 3), and the owner was paused with SIGSTOP past the other worker's timeout (2 of 2).

After the owner process exits, a new worker runs the messages. In the three-message runs that new worker ran all three within about a third of a second of starting. A worker that is SIGKILLed, instead of Redis being restarted, also has its delayed messages recovered by the replacement (3 of 3). With no Redis restart, the same three messages run at their ETA (3 of 3).

On a connection error, `ConsumerThread.run` replaces `self.delay_queue` with a new empty queue (`worker.py` 325–327) and then `close()` requeues whatever is in that queue (line 486). The messages that were already fetched stay in `dramatiq:__acks__.<worker>.default.DQ`. The worker keeps refreshing its heartbeat, so maintenance does not treat it as dead. RabbitMQ's `requeue` says unacked messages are re-enqueued on disconnect and that its own requeue is a no-op (`brokers/rabbitmq.py` 575–576). Redis does not do that.

I have not attached a patch. Keeping those messages in memory, while maintenance can also put them back, ran each message twice when the owner's heartbeat expired and the owner still held them.

---
