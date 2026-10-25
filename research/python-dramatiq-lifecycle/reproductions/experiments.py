"""Experiments for the Dramatiq lifecycle study.

  python -I experiments.py <experiment> --variant <name> [--reps N] [--form host|url]
                           [--python /path/to/venv/bin/python] [--ports 56391,56392]

Every repetition gets a fresh redis-server, witness and worker, and writes its
evidence under ../outputs/<experiment>/<variant>/<UTC stamp>-rep<N>/.
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dramatiq import Message  # noqa: E402
from dramatiq.brokers.redis import RedisBroker  # noqa: E402

from harness import AGGRESSIVE_MAINTENANCE, Run, environment, heartbeat_ages, locate  # noqa: E402

LOG_MARKERS = [
    "Unexpected failure in after_process_message",
    "Retrying message",
    "Retries exceeded",
    "Failed to post_process_message",
    "Unhandled error during post_process_message",
    "Consumer encountered a connection error",
    "Consumer encountered an unexpected error",
    "Restarting consumer",
    "Exception in thread",
    "Failed to requeue messages",
    "Re-enqueueing",
    "Worker has been shut down",
    "Acknowledging message",
    "Rejecting message",
]


def producer(run):
    # A separate broker for enqueueing from the harness: no middleware, and
    # maintenance disabled so the harness never requeues anything itself.
    return RedisBroker(host="127.0.0.1", port=run.redis_port, middleware=[], maintenance_chance=0)


def job_message(job_id, plan):
    return Message(queue_name="default", actor_name="job", args=(job_id, plan), kwargs={}, options={})


def markers(text):
    return {marker: text.count(marker) for marker in LOG_MARKERS}


def boot(run, proc, timeout=30):
    mark = len(run.witness.events)
    proc.start()
    for consumer in ("default", "default.DQ"):
        if not run.wait(lambda e, c=consumer: e["seq"] > mark and e["ev"] == "hook_consumer_boot" and e.get("consumer") == c, timeout, "%s consumer booted (%s)" % (consumer, proc.name)):
            raise RuntimeError("worker %s did not boot" % proc.name)
    worker_boot = run.witness.select(lambda e: e["seq"] > mark and e["ev"] == "hook_worker_boot")
    return worker_boot[-1] if worker_boot else None


# ---------------------------------------------------------------------------
# D4: retry publication fails, then the original is acknowledged.
# ---------------------------------------------------------------------------

def d4(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_MAX_RETRIES": "0" if variant == "control-noretries" else "3"}
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1 = run.worker("worker-1", env)
    w1_boot = boot(run, w1)
    run.result["worker1_broker_id"] = w1_boot and w1_boot.get("broker_id")

    sent = producer(run).enqueue(job_message("d4", {"0": "barrier", "default": "ok"}))
    mid = sent.message_id
    run.result["message_id"] = mid
    run.timeline.log("enqueued", message_id=mid, redis_message_id=sent.options["redis_message_id"])

    barrier = run.wait(lambda e: e["ev"] == "task_barrier" and e.get("message_id") == mid and e.get("attempt") == 0, 30, "attempt 0 at its barrier")
    run.result["places_while_executing"] = locate(run.snap("attempt0_executing"), mid)

    # In fault-actor-redis the actor is not told to fail: it writes its effect
    # to the same Redis, which is down, so it fails on its own.
    reply = "redis" if variant == "fault-actor-redis" else "raise"
    if variant in ("fault", "fault-actor-redis", "control-kill", "control-noretries"):
        run.redis.stop()
    run.witness.release(lambda e: e["seq"] == barrier["seq"], reply)
    run.timeline.log("barrier_released", reply=reply)

    def hooks_done(e):
        return e["ev"] == "hook_after_process_message" and e.get("message_id") == mid

    # Unpatched, the hooks finish within seconds while Redis is still down.
    # A build that keeps retrying the enqueue finishes them only once Redis
    # is back, so if they haven't finished after 30 s, restart Redis first.
    hook = run.wait(hooks_done, 30, "after_process_message hooks done")
    run.result["hooks_finished_while_redis_down"] = bool(hook) and not run.redis.running()
    if hook is None and variant != "control-kill" and not run.redis.running():
        run.redis.start()
        hook = run.wait(hooks_done, 120, "after_process_message hooks done after Redis restart")
    run.result["hook_after_process_message"] = hook and {k: hook.get(k) for k in ("failed", "exception", "retries")}

    if variant == "control-ok":
        done = run.wait(lambda e: e["ev"] == "task_done" and e.get("message_id") == mid and e.get("attempt") == 1, 30, "attempt 1 done")
        retry_rid = done and done.get("redis_message_id")
        run.wait(lambda e: e["ev"] == "hook_after_ack" and e.get("redis_message_id") == retry_rid, 30, "attempt 1 acked")
        final = run.snap("final")
    elif variant == "control-kill":
        w1.kill_group()
        run.result["worker1_exit"] = w1.wait(10)
        run.redis.start()
        run.result["places_after_kill"] = locate(run.snap("after_kill_redis_back"), mid)
        mark = len(run.witness.events)
        w2 = run.worker("worker-2-replacement", {**env, **AGGRESSIVE_MAINTENANCE})
        boot(run, w2)
        again = run.wait(lambda e: e["seq"] > mark and e["ev"] == "task_barrier" and e.get("message_id") == mid, 60, "original redelivered to the replacement")
        if again:
            run.witness.release(lambda e: e["seq"] == again["seq"], "ok")
            run.wait(lambda e: e["seq"] > mark and e["ev"] == "hook_after_ack" and e.get("message_id") == mid, 30, "redelivered copy acked")
        final = run.snap("final")
        w2.term()
        run.result["worker2_exit"] = w2.wait(60)
    else:
        # The middleware has finished and, in the fault variant, failed to
        # enqueue the retry. Bring Redis back and let the worker settle the
        # original (its ack/nack is retried every 5 s on connection errors).
        if not run.redis.running():
            run.redis.start()
        settle = run.wait(lambda e: e["ev"] in ("hook_after_ack", "hook_after_nack") and e.get("message_id") == mid, 60, "original settled by the worker")
        run.result["original_settled_by"] = settle and settle["ev"]
        run.result["places_after_settle"] = locate(run.snap("after_settle"), mid)
        retry = run.wait(lambda e: e["ev"] == "task_start" and e.get("message_id") == mid and e.get("attempt", 0) >= 1, 20, "a retry attempt starts")
        run.result["retry_attempt_seen_while_worker1_alive"] = bool(retry)
        run.result["places_after_wait"] = locate(run.snap("after_wait"), mid)
        w1.term()
        run.result["worker1_exit"] = w1.wait(60)
        mark = len(run.witness.events)
        w2 = run.worker("worker-2-replacement", {**env, **AGGRESSIVE_MAINTENANCE})
        boot(run, w2)
        again = run.wait(lambda e: e["seq"] > mark and e["ev"] == "task_start" and e.get("message_id") == mid, 20, "anything redelivered to the replacement")
        run.result["redelivered_to_replacement"] = bool(again)
        final = run.snap("after_replacement")
        w2.term()
        run.result["worker2_exit"] = w2.wait(60)
        # Durability: with no worker running, restart Redis from its
        # append-only file and look for the message once more.
        run.redis.stop()
        run.redis.start()
        run.result["places_after_final_redis_restart"] = locate(run.snap("after_final_redis_restart"), mid)

    events = run.witness.events
    run.result["completed"] = any(e["ev"] == "task_done" and e.get("message_id") == mid for e in events)
    run.result["retry_enqueued_by_worker"] = any(e["ev"] == "hook_after_enqueue" and e.get("message_id") == mid and e.get("queue") == "default.DQ" for e in events)
    run.result["attempts_started"] = [[e.get("attempt"), e["pid"]] for e in events if e["ev"] == "task_start" and e.get("message_id") == mid]
    run.result["places_final"] = locate(final, mid)
    run.result["dead_letter_keys"] = {k: v["value"] for k, v in final["keys"].items() if ".XQ" in k}
    run.result["log_markers_worker1"] = markers(w1.log_text())
    run.result["actor_redis_write_failed"] = [e.get("error") for e in events if e["ev"] == "task_redis_write_failed" and e.get("message_id") == mid]
    if variant.startswith("fault"):
        run.result["message_lost"] = (
            not run.result["retry_enqueued_by_worker"]
            and run.result["original_settled_by"] == "hook_after_ack"
            and not run.result["places_after_wait"]
            and not run.result["places_final"]
            and not run.result["redelivered_to_replacement"]
            and not run.result["completed"]
            and not run.result.get("places_after_final_redis_restart")
        )


# ---------------------------------------------------------------------------
# N1: delayed messages held in memory when the broker connection fails.
# N2: the same, when the error is one Dramatiq does not map (TimeoutError).
# ---------------------------------------------------------------------------

OPTIONS = {"observe": 35.0, "jobs": 3, "delay_ms": 25000, "down": 15.0, "pause_ms": 15000}


def ack_sets(snap):
    return {k: v["value"] for k, v in snap["keys"].items() if k.startswith("dramatiq:__acks__.")}


def hold_delayed(run, env, delay_ms):
    """Boot worker-1, enqueue delayed jobs, and wait until its delay-queue
    consumer has fetched them (they leave the DQ list for its ack set)."""
    w1 = run.worker("worker-1", env)
    w1_boot = boot(run, w1)
    run.result["worker1_broker_id"] = w1_boot and w1_boot.get("broker_id")
    p = producer(run)
    sent = [p.enqueue(job_message("delayed-%d" % i, {"default": "ok"}), delay=delay_ms) for i in range(OPTIONS["jobs"])]
    run.result["message_ids"] = [m.message_id for m in sent]
    run.result["etas_ms"] = [m.options["eta"] for m in sent]
    run.timeline.log("enqueued_delayed", count=len(sent), delay_ms=delay_ms)
    deadline = time.monotonic() + 15
    while True:
        snap = run.snap("waiting_for_prefetch")
        held = ack_sets(snap).get("dramatiq:__acks__.%s.default.DQ" % run.result["worker1_broker_id"], [])
        if len(held) == len(sent) and not snap["keys"].get("dramatiq:default.DQ"):
            break
        if time.monotonic() > deadline:
            raise RuntimeError("delay-queue consumer did not fetch the delayed messages")
        time.sleep(0.2)
    run.result["held_by_worker1_before_fault"] = held
    return w1, sent


def executed(run, message_ids, since=0):
    return sorted({e.get("job_id") for e in run.witness.events if e["seq"] > since and e["ev"] == "task_done" and e.get("message_id") in message_ids})


def n1(run, variant, form):
    env = {"PPCS_BROKER_FORM": form}
    if variant in ("fault-aggressive", "control-norestart", "control-crash"):
        env.update(AGGRESSIVE_MAINTENANCE)
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1, sent = hold_delayed(run, env, OPTIONS["delay_ms"])
    mids = [m.message_id for m in sent]
    wid = run.result["worker1_broker_id"]

    if variant == "control-crash":
        w1.kill_group()
        run.result["worker1_exit"] = w1.wait(10)
        mark = len(run.witness.events)
        w2 = run.worker("worker-2-replacement", env)
        boot(run, w2)
        run.wait(lambda e: len(executed(run, mids, mark)) == len(mids), OPTIONS["delay_ms"] / 1000 + 30, "all delayed jobs executed by the replacement")
        run.result["executed_by_replacement"] = executed(run, mids, mark)
        final = run.snap("final")
        run.result["places_final"] = {m: locate(final, m) for m in mids}
        w2.term()
        run.result["worker2_exit"] = w2.wait(60)
        run.result["log_markers_worker1"] = markers(w1.log_text())
        return

    if variant != "control-norestart":
        run.redis.stop()
        time.sleep(OPTIONS["down"])
        run.redis.start()
    restart_t = time.time()
    first_eta_s = min(run.result["etas_ms"]) / 1000
    observe_until = max(first_eta_s, restart_t) + OPTIONS["observe"]
    checkpoints = []
    while time.time() < observe_until:
        time.sleep(min(10.0, max(0.0, observe_until - time.time())))
        snap = run.snap("observe")
        checkpoints.append({
            "t": snap["t"],
            "seconds_after_first_eta": round(snap["t"] - first_eta_s, 1),
            "executed": executed(run, mids),
            "still_in_worker1_dq_ack_set": sorted(set(ack_sets(snap).get("dramatiq:__acks__.%s.default.DQ" % wid, [])) & set(run.result["held_by_worker1_before_fault"])),
            "dq_list": snap["keys"].get("dramatiq:default.DQ", {}).get("value", []),
            "worker1_heartbeat_age_ms": heartbeat_ages(snap).get(wid),
        })
    run.result["checkpoints"] = checkpoints
    run.result["executed_while_worker1_alive"] = executed(run, mids)
    run.result["log_markers_worker1_before_stop"] = markers(w1.log_text())
    if variant == "control-norestart":
        w1.term()
        run.result["worker1_exit"] = w1.wait(60)
        final = run.snap("final")
        run.result["places_final"] = {m: locate(final, m) for m in mids}
        run.result["log_markers_worker1"] = markers(w1.log_text())
        return

    # Recovery control: stop worker 1 gracefully, then start a replacement
    # whose maintenance runs on every call with a 2 s heartbeat timeout.
    w1.term()
    run.result["worker1_exit"] = w1.wait(60)
    run.result["after_worker1_exit"] = ack_sets(run.snap("after_worker1_exit"))
    mark = len(run.witness.events)
    w2 = run.worker("worker-2-replacement", {**env, **AGGRESSIVE_MAINTENANCE})
    boot(run, w2)
    run.wait(lambda e: len(executed(run, mids, mark)) == len(mids), 30, "all delayed jobs executed by the replacement")
    run.result["executed_by_replacement"] = executed(run, mids, mark)
    final = run.snap("final")
    run.result["places_final"] = {m: locate(final, m) for m in mids}
    w2.term()
    run.result["worker2_exit"] = w2.wait(60)
    run.result["log_markers_worker1"] = markers(w1.log_text())


def n2(run, variant, form):
    """The delayed messages are held, then Redis stops answering writes for
    pause_ms (CLIENT PAUSE ... WRITE). Dispatch calls time out after redis-py's
    5 s socket timeout with redis.TimeoutError, which Dramatiq does not map."""
    env = {"PPCS_BROKER_FORM": form, **AGGRESSIVE_MAINTENANCE}
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1, sent = hold_delayed(run, env, 120000)
    mids = [m.message_id for m in sent]
    wid = run.result["worker1_broker_id"]
    # control-shortpause: the stall outlasts one socket timeout but not two,
    # so close()'s requeue succeeds once the pause ends.
    pause_ms = 7000 if variant == "control-shortpause" else OPTIONS["pause_ms"]
    run.result["pause_ms"] = pause_ms
    run.redis.client().execute_command("CLIENT", "PAUSE", str(pause_ms), "WRITE")
    run.timeline.log("client_pause", ms=pause_ms, mode="WRITE")
    time.sleep(pause_ms / 1000 + 5)
    snap = run.snap("after_pause")
    run.result["held_after_pause"] = ack_sets(snap).get("dramatiq:__acks__.%s.default.DQ" % wid, [])
    run.result["dq_list_after_pause"] = snap["keys"].get("dramatiq:default.DQ", {}).get("value", [])

    # Probe both consumers: a delayed job due in 2 s, and an ordinary job.
    p = producer(run)
    probe_delayed = p.enqueue(job_message("probe-delayed", {"default": "ok"}), delay=2000)
    probe_now = p.enqueue(job_message("probe-now", {"default": "ok"}))
    run.wait(lambda e: e["ev"] == "task_done" and e.get("message_id") == probe_now.message_id, 20, "ordinary probe executed")
    run.wait(lambda e: e["ev"] == "task_done" and e.get("message_id") == probe_delayed.message_id, 30, "delayed probe executed")
    snap = run.snap("after_probes")
    run.result["probe_now_executed"] = bool(run.witness.select(lambda e: e["ev"] == "task_done" and e.get("message_id") == probe_now.message_id))
    run.result["probe_delayed_executed"] = bool(run.witness.select(lambda e: e["ev"] == "task_done" and e.get("message_id") == probe_delayed.message_id))
    run.result["probe_delayed_places"] = locate(snap, probe_delayed.message_id)
    run.result["held_after_probes"] = ack_sets(snap).get("dramatiq:__acks__.%s.default.DQ" % wid, [])
    run.result["worker1_heartbeat_age_ms"] = heartbeat_ages(snap).get(wid)
    run.result["worker1_alive"] = w1.proc.poll() is None
    run.result["log_markers_worker1_before_stop"] = markers(w1.log_text())
    w1.term()
    run.result["worker1_exit"] = w1.wait(60)
    run.result["held_after_worker1_exit"] = ack_sets(run.snap("after_worker1_exit")).get("dramatiq:__acks__.%s.default.DQ" % wid, [])
    run.result["log_markers_worker1"] = markers(w1.log_text())


# ---------------------------------------------------------------------------
# D7: the broker is unavailable when graceful shutdown requeues messages.
# D2 is the same sequence with the broker available.
# ---------------------------------------------------------------------------

def d7(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_BARRIER_CONSUMER_SHUTDOWN": "1"}
    if variant.endswith("-asyncio"):
        env["PPCS_ASYNCIO"] = "1"
    fault = variant.startswith("fault")
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1 = run.worker("worker-1", env)
    w1_boot = boot(run, w1)
    wid = w1_boot and w1_boot.get("broker_id")
    run.result["worker1_broker_id"] = wid
    p = producer(run)
    sent = [p.enqueue(job_message("d7-%d" % i, {"0": "barrier" if i == 0 else "ok", "default": "ok"})) for i in range(3)]
    mids = [m.message_id for m in sent]
    run.result["message_ids"] = mids
    first = run.wait(lambda e: e["ev"] == "task_barrier" and e.get("message_id") == mids[0], 30, "first job at its barrier")
    run.result["held_while_first_executes"] = ack_sets(run.snap("first_executing"))

    w1.term()
    run.wait(lambda e: e["ev"] == "hook_before_worker_shutdown", 30, "worker shutdown began")
    run.witness.release(lambda e: e["seq"] == first["seq"], "ok")
    run.wait(lambda e: e["ev"] == "hook_after_ack" and e.get("message_id") == mids[0], 30, "first job acked")
    for consumer in ("default", "default.DQ"):
        run.wait(lambda e, c=consumer: e["ev"] == "hook_consumer_shutdown_barrier" and e.get("consumer") == c, 30, "%s consumer at its shutdown barrier" % consumer)
    before = run.snap("before_requeue")
    run.result["held_before_requeue"] = ack_sets(before)
    run.result["queue_before_requeue"] = before["keys"].get("dramatiq:default", {}).get("value", [])
    if fault:
        run.redis.stop()
    run.witness.release(lambda e: e["ev"] == "hook_consumer_shutdown_barrier", "ok")
    code = w1.wait(60)
    run.result["worker1_exit"] = code
    run.result["worker1_hung"] = code is None
    if code is None:
        run.result["worker1_pids_still_running"] = w1.group_pids()
        w1.kill_group()
        w1.wait(10)
    run.result["after_worker_shutdown_hook_ran"] = bool(run.witness.select(lambda e: e["ev"] == "hook_after_worker_shutdown"))
    if fault:
        run.redis.start()
    after = run.snap("after_worker1_exit")
    run.result["held_after_exit"] = ack_sets(after)
    run.result["queue_after_exit"] = after["keys"].get("dramatiq:default", {}).get("value", [])
    run.result["worker1_heartbeat_age_ms_after_exit"] = heartbeat_ages(after).get(wid)

    mark = len(run.witness.events)
    # "-defaultrecovery" variants give the replacement Dramatiq's default
    # maintenance settings (60 s heartbeat timeout, 1000 in 1,000,000 calls).
    default_recovery = variant.endswith("-defaultrecovery")
    replacement_env = {"PPCS_BROKER_FORM": form, **({} if default_recovery else AGGRESSIVE_MAINTENANCE)}
    w2 = run.worker("worker-2-replacement", replacement_env)
    boot(run, w2)
    pending = mids[1:]
    started = time.time()
    run.wait(lambda e: len(executed(run, pending, mark)) == len(pending), 1800 if default_recovery else 30, "remaining jobs executed by the replacement")
    run.result["recovery_seconds_after_replacement_boot"] = round(time.time() - started, 1)
    run.result["executed_by_replacement"] = executed(run, pending, mark)
    final = run.snap("final")
    run.result["places_final"] = {m: locate(final, m) for m in mids}
    w2.term()
    run.result["worker2_exit"] = w2.wait(60)
    text = w1.log_text()
    run.result["log_markers_worker1"] = markers(text)
    run.result["worker1_log_tail"] = text.splitlines()[-12:]


EXPERIMENTS = {"d4": d4, "n1": n1, "n2": n2, "d7": d7}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--variant", required=True)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--form", choices=("host", "url"), default="host")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--ports", default="56391,56392")
    parser.add_argument("--observe", type=float, help="N1: seconds to keep observing after the first ETA")
    parser.add_argument("--pause-ms", type=int, help="N2: CLIENT PAUSE duration")
    parser.add_argument("--tag", default="", help="suffix for the variant directory, e.g. master")
    args = parser.parse_args()
    if args.observe is not None:
        OPTIONS["observe"] = args.observe
    if args.pause_ms is not None:
        OPTIONS["pause_ms"] = args.pause_ms
    redis_port, witness_port = (int(p) for p in args.ports.split(","))
    for rep in range(1, args.reps + 1):
        variant_dir = "%s-%s%s" % (args.variant, args.form, "-" + args.tag if args.tag else "")
        run = Run(args.experiment, variant_dir, rep, redis_port, witness_port, python=args.python)
        run.result["argv"] = sys.argv
        try:
            EXPERIMENTS[args.experiment](run, args.variant, args.form)
        except Exception as exc:  # keep the evidence of a failed run
            run.result["harness_error"] = "%s: %s" % (type(exc).__name__, exc)
            run.timeline.log("harness_error", error=run.result["harness_error"])
        finally:
            run.finish()
        time.sleep(1)


if __name__ == "__main__":
    main()
