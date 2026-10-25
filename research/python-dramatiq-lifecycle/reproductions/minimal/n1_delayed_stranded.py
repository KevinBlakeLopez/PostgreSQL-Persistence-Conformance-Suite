"""Minimal reproduction of F2: after a Redis restart, a delayed message that a
running worker had already fetched never runs while that worker lives.

  python n1_delayed_stranded.py [--redis-server PATH] [--port PORT]

It starts its own redis-server (append-only, appendfsync always). The broker
runs maintenance on every call with a 2 s heartbeat timeout, so if recovery
depended on the heartbeat timeout the message would be back within seconds.
"""

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
