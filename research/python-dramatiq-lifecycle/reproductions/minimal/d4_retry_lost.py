"""Minimal reproduction of F1: a failed message whose retry can't be enqueued
is acknowledged and deleted.

  python d4_retry_lost.py [--redis-server PATH] [--port PORT]

It starts its own redis-server (append-only, appendfsync always) in a
temporary directory. The actor stops that server and then raises, standing in
for an actor that fails during a broker outage. A middleware installed ahead
of the defaults (so its after_process_message runs after Retries') starts the
server again, as if the outage had just ended. Then it reports what Redis holds.
"""

import argparse
import subprocess
import tempfile
import time

import dramatiq
import redis
from dramatiq import Worker
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Middleware

parser = argparse.ArgumentParser()
parser.add_argument("--redis-server", default="redis-server")
parser.add_argument("--port", type=int, default=56391)
args = parser.parse_args()

data_dir = tempfile.mkdtemp()
server = None


def start_redis():
    global server
    server = subprocess.Popen(
        [args.redis_server, "--port", str(args.port), "--bind", "127.0.0.1", "--dir", data_dir,
         "--appendonly", "yes", "--appendfsync", "always", "--save", ""],
        stdout=subprocess.DEVNULL,
    )
    client = redis.Redis(port=args.port)
    for _ in range(200):
        try:
            client.ping()
            return
        except redis.ConnectionError:
            time.sleep(0.05)
    raise RuntimeError("redis-server did not start")


def stop_redis():
    server.terminate()
    server.wait()


class OutageEnds(Middleware):
    def after_process_message(self, broker, message, *, result=None, exception=None):
        print("after_process_message: Retries has run; starting Redis again")
        start_redis()


attempts = []
broker = RedisBroker(host="127.0.0.1", port=args.port)
broker.add_middleware(OutageEnds(), before=AgeLimit)
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=2000)
def flaky():
    attempts.append(time.time())
    print("attempt %d: stopping Redis, then raising" % len(attempts))
    stop_redis()
    raise RuntimeError("downstream failure")


start_redis()
message = flaky.send()
worker = Worker(broker, worker_threads=1)
worker.start()
time.sleep(15)  # the ack is retried every 5 s; the retry's backoff is 1-2 s
worker.stop()

client = redis.Redis(port=args.port, decode_responses=True)
keys = sorted(k for k in client.scan_iter("dramatiq:*") if k != "dramatiq:__heartbeats__")
print("dramatiq %s, redis-py %s, redis-server %s" % (dramatiq.__version__, redis.__version__, client.info()["redis_version"]))
print("attempts run: %d" % len(attempts))
print("Redis keys holding messages: %s" % (keys or "none"))
print("message %s is %s" % (message.message_id, "LOST" if not keys and len(attempts) == 1 else "still present"))
stop_redis()
