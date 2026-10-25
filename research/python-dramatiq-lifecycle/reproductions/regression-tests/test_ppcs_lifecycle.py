"""Regression tests for F1-F4, written against Dramatiq's own test fixtures.

Copy into a Dramatiq checkout's tests/ directory and run with pytest. The
redis_broker fixture uses Redis on localhost:6379 and calls flushall(), so run
these only where that Redis is your own (here: inside a disposable container).

Faults are injected by patching the broker's dispatch calls (do_enqueue,
do_fetch, do_requeue) to raise the redis-py exceptions a real outage
produces. Integration reproductions with real outages are in
reproductions/verify.py and reproductions/minimal/.
"""

from __future__ import annotations

import time
from unittest import mock

import pytest
import redis

import dramatiq
import dramatiq.middleware.retries
from dramatiq import Worker


def wait_for(predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def failing_once(broker, name, *, queue_suffix, exc, times=1):
    """Patch broker.<name> so its first `times` calls on a matching queue raise."""
    real = getattr(broker, name)
    state = {"raised": 0}

    def side_effect(queue_name, *args):
        if queue_name.endswith(queue_suffix) and state["raised"] < times:
            state["raised"] += 1
            raise exc
        return real(queue_name, *args)

    return mock.patch.object(broker, name, side_effect=side_effect), state


# F1 ---------------------------------------------------------------------------


def test_f1_failed_message_is_not_deleted_when_its_retry_cannot_be_enqueued(redis_broker, redis_worker, monkeypatch):
    # A fix that retries the enqueue may sleep between attempts; keep it short.
    monkeypatch.setattr(dramatiq.middleware.retries, "RETRY_ENQUEUE_DELAY_SECS", 0.1, raising=False)
    attempts = []

    @dramatiq.actor(max_retries=3, min_backoff=100, max_backoff=100)
    def fails_once():
        attempts.append(time.time())
        if len(attempts) == 1:
            raise RuntimeError("first attempt fails")

    patch, state = failing_once(redis_broker, "do_enqueue", queue_suffix=".DQ",
                                exc=redis.ConnectionError("the retry never reached Redis"))
    with patch:
        fails_once.send()
        assert wait_for(lambda: state["raised"] == 1, 10)
        # The original must not be deleted: it is either retried or dead-lettered.
        wait_for(lambda: len(attempts) == 2 or redis_broker.client.zcard("dramatiq:default.XQ") == 1, 10)

    dead_lettered = redis_broker.client.zcard("dramatiq:default.XQ") == 1
    assert len(attempts) == 2 or dead_lettered, "acknowledged without a retry or a dead letter"


def test_f1_control_retry_works_when_enqueue_succeeds(redis_broker, redis_worker):
    attempts = []

    @dramatiq.actor(max_retries=3, min_backoff=100, max_backoff=100)
    def fails_once():
        attempts.append(time.time())
        if len(attempts) == 1:
            raise RuntimeError("first attempt fails")

    fails_once.send()
    assert wait_for(lambda: len(attempts) == 2, 10)


# F2 ---------------------------------------------------------------------------


def test_f2_delayed_message_survives_a_connection_error_in_the_delay_consumer(redis_broker, redis_worker):
    runs = []

    @dramatiq.actor
    def scheduled():
        runs.append(time.time())

    scheduled.send_with_options(delay=3000)
    held = "dramatiq:__acks__.%s.default.DQ" % redis_broker.broker_id
    assert wait_for(lambda: redis_broker.client.scard(held) == 1, 10), "the delay consumer did not fetch it"

    patch, state = failing_once(redis_broker, "do_fetch", queue_suffix=".DQ",
                                exc=redis.ConnectionError("connection lost"))
    with patch:
        assert wait_for(lambda: state["raised"] == 1, 10)
    # The consumer restarts after dramatiq_restart_delay (3 s by default).
    assert wait_for(lambda: runs, 15), "the delayed message never ran while the worker was alive"


def test_f2_control_delayed_message_runs_without_a_fault(redis_broker, redis_worker):
    runs = []

    @dramatiq.actor
    def scheduled():
        runs.append(time.time())

    scheduled.send_with_options(delay=1000)
    assert wait_for(lambda: runs, 10)


# F3 ---------------------------------------------------------------------------


def test_f3_delay_consumer_survives_a_timeout_while_holding_messages(redis_broker, redis_worker):
    runs = []

    @dramatiq.actor
    def scheduled(tag):
        runs.append(tag)

    scheduled.send_with_options(args=("held",), delay=4000)
    held = "dramatiq:__acks__.%s.default.DQ" % redis_broker.broker_id
    assert wait_for(lambda: redis_broker.client.scard(held) == 1, 10)

    stall = redis.TimeoutError("Timeout reading from socket")
    fetch_patch, fetch_state = failing_once(redis_broker, "do_fetch", queue_suffix=".DQ", exc=stall)
    requeue_patch, _ = failing_once(redis_broker, "do_requeue", queue_suffix=".DQ", exc=stall)
    with fetch_patch, requeue_patch:
        assert wait_for(lambda: fetch_state["raised"] == 1, 10)
        time.sleep(0.5)

    consumer = redis_worker.consumers["default.DQ"]
    assert wait_for(consumer.is_alive, 5), "the delay-queue consumer thread died"
    scheduled.send_with_options(args=("probe",), delay=500)
    assert wait_for(lambda: "probe" in runs, 15), "delayed messages sent later never ran"
    assert wait_for(lambda: "held" in runs, 15), "the delayed message held during the stall never ran"


# F4 ---------------------------------------------------------------------------


def test_f4_worker_stop_finishes_shutdown_when_requeue_fails(redis_broker):
    events = []

    class Recorder(dramatiq.Middleware):
        def after_worker_shutdown(self, broker, worker):
            events.append("after_worker_shutdown")

    redis_broker.add_middleware(Recorder())

    @dramatiq.actor
    def slow():
        time.sleep(0.5)

    worker = Worker(redis_broker, worker_threads=1)
    worker.start()
    slow.send()
    slow.send()  # prefetched into the work queue while the first runs
    assert wait_for(lambda: not worker.work_queue.empty(), 5)

    with mock.patch.object(redis_broker, "do_requeue", side_effect=redis.ConnectionError("Redis is down")):
        worker.stop()  # must not raise

    assert events == ["after_worker_shutdown"]


def test_f4_control_worker_stop_requeues_when_redis_is_up(redis_broker):
    @dramatiq.actor
    def slow():
        time.sleep(0.5)

    worker = Worker(redis_broker, worker_threads=1)
    worker.start()
    slow.send()
    slow.send()
    assert wait_for(lambda: not worker.work_queue.empty(), 5)
    worker.stop()
    assert redis_broker.client.llen("dramatiq:default") == 1


@pytest.fixture(autouse=True)
def fast_restart(monkeypatch):
    # Not a behavior change: the same restart path with a shorter pause.
    import dramatiq.worker

    monkeypatch.setattr(dramatiq.worker, "CONSUMER_RESTART_DELAY_SECS", 1)
