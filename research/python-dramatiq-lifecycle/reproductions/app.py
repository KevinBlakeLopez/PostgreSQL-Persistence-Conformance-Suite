"""Dramatiq application used by every experiment in this study.

Run by the stock CLI:  python -I -m dramatiq app --path <this dir> ...
It is configured only through PPCS_* environment variables, so the worker
command line is the same in every experiment.

The actor reports to the external witness (a TCP service in the harness
process) and can wait there at a barrier, so the harness can inject a fault
at a known point. WitnessHooks is test instrumentation: it only reports to the
witness. Its single exception is the opt-in consumer-shutdown barrier used by
D7, which pauses a consumer thread at a public middleware hook and changes
nothing else.
"""

import json
import os
import socket
import threading
import time

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, CurrentMessage, Middleware

ALLOWED_PORTS = range(56391, 56399)

REDIS_PORT = int(os.environ["PPCS_REDIS_PORT"])
WITNESS_PORT = int(os.environ["PPCS_WITNESS_PORT"])
if REDIS_PORT not in ALLOWED_PORTS or WITNESS_PORT not in ALLOWED_PORTS:
    raise SystemExit("refusing ports outside the study's range: %d, %d" % (REDIS_PORT, WITNESS_PORT))

BROKER_FORM = os.environ.get("PPCS_BROKER_FORM", "host")
BARRIER_CONSUMER_SHUTDOWN = os.environ.get("PPCS_BARRIER_CONSUMER_SHUTDOWN") == "1"
# Adversarial verification only: pause right after a retry has been enqueued
# successfully, before the original is acked.
BARRIER_AFTER_RETRY_ENQUEUE = os.environ.get("PPCS_BARRIER_AFTER_RETRY_ENQUEUE") == "1"
# Adversarial verification only: report the worker's in-memory state.
REPORT_STATE = os.environ.get("PPCS_REPORT_STATE") == "1"
BARRIER_TIMEOUT = 600


def witness(ev, *, wait=False, **fields):
    """Send one event to the witness. With wait=True, block until the harness
    releases this barrier, and return the action it chose."""
    payload = {"ev": ev, "pid": os.getpid(), "t_client": time.time(), "barrier": wait, **fields}
    try:
        with socket.create_connection(("127.0.0.1", WITNESS_PORT), timeout=BARRIER_TIMEOUT if wait else 5) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode())
            line = sock.makefile("r").readline()
    except OSError:
        if wait:
            raise
        return {}
    return json.loads(line) if line else {}


def ids(message):
    # "retries" is read when the event is sent. Retries.after_process_message
    # increments it in place before it enqueues the retry, so hooks that run
    # after it report the incremented value.
    return {
        "message_id": message.message_id,
        "redis_message_id": message.options.get("redis_message_id"),
        "queue": message.queue_name,
        "retries": message.options.get("retries", 0),
    }


class WitnessHooks(Middleware):
    """Observation-only hooks. Installed first, so its after_* hooks run after
    every default middleware (Broker.emit_after walks the list in reverse)."""

    consumer_threads = []

    def before_worker_boot(self, broker, worker):
        witness("hook_worker_boot", broker_id=broker.broker_id)
        if REPORT_STATE:
            threading.Thread(target=self.report_state, daemon=True, name="ppcs-state-reporter").start()

    def after_consumer_thread_boot(self, broker, thread):
        self.consumer_threads.append(thread)
        witness("hook_consumer_boot", consumer=thread.queue_name, broker_id=broker.broker_id)

    def report_state(self):
        # Read-only view of the worker's memory, once a second.
        while True:
            consumers = []
            for thread in list(self.consumer_threads):
                consumer = thread.consumer
                consumers.append({
                    "consumer": thread.queue_name,
                    "alive": thread.is_alive(),
                    "delay_queue": thread.delay_queue.qsize(),
                    "queued_ids": len(getattr(consumer, "queued_message_ids", ())),
                    "message_cache": len(getattr(consumer, "message_cache", ())),
                })
            witness("state", consumers=consumers,
                    non_daemon=[t.name for t in threading.enumerate() if not t.daemon])
            time.sleep(1)

    def after_process_message(self, broker, message, *, result=None, exception=None):
        witness(
            "hook_after_process_message",
            failed=message.failed,
            exception=type(exception).__name__ if exception is not None else None,
            **ids(message),
        )

    def after_enqueue(self, broker, message, delay):
        witness("hook_after_enqueue", delay=delay, **ids(message))
        if BARRIER_AFTER_RETRY_ENQUEUE and message.queue_name.endswith(".DQ"):
            witness("hook_after_retry_enqueue_barrier", wait=True, **ids(message))

    def after_ack(self, broker, message):
        witness("hook_after_ack", **ids(message))

    def after_nack(self, broker, message):
        witness("hook_after_nack", **ids(message))

    def before_worker_shutdown(self, broker, worker):
        witness("hook_before_worker_shutdown")

    def before_consumer_thread_shutdown(self, broker, thread):
        if BARRIER_CONSUMER_SHUTDOWN:
            witness("hook_consumer_shutdown_barrier", wait=True, consumer=thread.queue_name)
        else:
            witness("hook_before_consumer_thread_shutdown", consumer=thread.queue_name)

    def after_worker_shutdown(self, broker, worker):
        witness("hook_after_worker_shutdown")


broker_options = {}
if "PPCS_HEARTBEAT_TIMEOUT_MS" in os.environ:
    broker_options["heartbeat_timeout"] = int(os.environ["PPCS_HEARTBEAT_TIMEOUT_MS"])
if "PPCS_MAINTENANCE_CHANCE" in os.environ:
    broker_options["maintenance_chance"] = int(os.environ["PPCS_MAINTENANCE_CHANCE"])

if BROKER_FORM == "url":
    broker = RedisBroker(url="redis://127.0.0.1:%d/0" % REDIS_PORT, **broker_options)
else:
    broker = RedisBroker(host="127.0.0.1", port=REDIS_PORT, db=0, **broker_options)

broker.add_middleware(CurrentMessage())
broker.add_middleware(WitnessHooks(), before=AgeLimit)
if os.environ.get("PPCS_ASYNCIO") in ("1", "first"):
    from dramatiq.middleware import AsyncIO

    if os.environ["PPCS_ASYNCIO"] == "first":
        broker.add_middleware(AsyncIO(), before=AgeLimit)
    else:
        broker.add_middleware(AsyncIO())
dramatiq.set_broker(broker)


@dramatiq.actor(
    queue_name="default",
    max_retries=int(os.environ.get("PPCS_MAX_RETRIES", "3")),
    min_backoff=int(os.environ.get("PPCS_MIN_BACKOFF_MS", "1000")),
    max_backoff=int(os.environ.get("PPCS_MAX_BACKOFF_MS", "2000")),
    throws=(ValueError,),
)
def job(job_id, plan):
    """plan maps an attempt number (as a string) or "default" to a step:
    "ok" (record the effect and return), "raise", "redis" (write the effect to
    the same Redis server, which raises if Redis is unavailable), or "barrier"
    (wait for the harness, which answers with one of the other steps)."""
    message = CurrentMessage.get_current_message()
    fields = {"job_id": job_id, **ids(message)}
    fields["attempt"] = fields["retries"]
    witness("task_start", **fields)
    step = plan.get(str(fields["attempt"]), plan.get("default", "ok"))
    if step == "barrier":
        step = witness("task_barrier", wait=True, **fields).get("action", "ok")
    if step == "redis":
        import redis

        witness("task_redis_write", **fields)
        try:
            redis.Redis(host="127.0.0.1", port=REDIS_PORT).incr("ppcs:effect:%s" % job_id)
        except redis.RedisError as exc:
            witness("task_redis_write_failed", error=type(exc).__name__, **fields)
            raise
        step = "ok"
    if step == "raise":
        witness("task_raise", **fields)
        raise RuntimeError("job %s attempt %s: simulated downstream failure" % (job_id, fields["attempt"]))
    if step == "retry":
        witness("task_raise", kind="Retry", **fields)
        raise dramatiq.Retry("job %s asked to be retried" % job_id, delay=1000)
    if step == "throw":
        witness("task_raise", kind="ValueError", **fields)
        raise ValueError("job %s: an exception listed in throws" % job_id)
    witness("task_effect", **fields)
    witness("task_done", **fields)
