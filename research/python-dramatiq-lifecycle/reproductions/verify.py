"""Adversarial verification experiments: attempts to overturn F1-F4.

  python -I verify.py <experiment> --variant <name> [--reps N] [--form host|url]
                      [--python PY] [--ports REDIS,WITNESS[,PROXY]] [--tag TAG]

Evidence goes to ../outputs/verify/<experiment>/<variant>-<form>[-<tag>]/.
Variants are listed in VARIANTS at the bottom.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PPCS_OUTPUTS_SUBDIR", "verify")

from experiments import ack_sets, boot, executed, hold_delayed, job_message, markers, producer  # noqa: E402
from harness import AGGRESSIVE_MAINTENANCE, Run, environment, heartbeat_ages, locate  # noqa: E402

SHORT_HB = {"PPCS_HEARTBEAT_TIMEOUT_MS": "2000", "PPCS_MAINTENANCE_CHANCE": "1000000"}
LONG_HB = {"PPCS_HEARTBEAT_TIMEOUT_MS": "60000", "PPCS_MAINTENANCE_CHANCE": "1000000"}


def done_count(run, mid, since=0):
    return sum(1 for e in run.witness.events if e["seq"] > since and e["ev"] == "task_done" and e.get("message_id") == mid)


def starts(run, mid):
    return [[e.get("attempt"), e["pid"]] for e in run.witness.events if e["ev"] == "task_start" and e.get("message_id") == mid]


def monitor(run, label):
    """Independent observer: Redis's MONITOR stream, to a file."""
    out = open(run.dir / ("monitor-%s.log" % label), "ab")
    return subprocess.Popen(["/opt/homebrew/bin/redis-cli" if os.path.exists("/opt/homebrew/bin/redis-cli") else "redis-cli",
                             "-p", str(run.redis_port), "MONITOR"], stdout=out, stderr=subprocess.STDOUT)


def settle_after(run, seconds):
    run.timeline.log("observe", seconds=seconds)
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# F1: what exactly happens around the retry enqueue and the original's ack.
# ---------------------------------------------------------------------------

def f1(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_MAX_RETRIES": "1" if variant in ("lastretry", "exhausted") else "3"}
    if variant.startswith("ackfail"):
        env["PPCS_BARRIER_AFTER_RETRY_ENQUEUE"] = "1"
    extra = ("--worker-shutdown-timeout", "4000") if variant == "a2-shutdown" else ()
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1 = run.worker("worker-1", env, extra_args=extra)
    w1_boot = boot(run, w1)
    run.result["worker1_broker_id"] = w1_boot and w1_boot.get("broker_id")
    mon = monitor(run, "1")

    if variant.startswith("lostreply") or variant == "a2-lostreply":
        run.proxy.add_rule("drop_reply", "enqueue", "default.DQ", count=1)
    plan = {"0": "barrier", "default": "ok"}
    if variant == "exhausted":
        plan = {"0": "raise", "1": "barrier", "default": "ok"}
    sent = producer(run).enqueue(job_message("f1-" + variant, plan))
    mid = sent.message_id
    run.result["message_id"] = mid
    first_attempt = 1 if variant == "exhausted" else 0
    barrier = run.wait(lambda e: e["ev"] == "task_barrier" and e.get("message_id") == mid and e.get("attempt") == first_attempt, 30, "attempt %d at its barrier" % first_attempt)
    run.result["places_while_executing"] = locate(run.snap("executing"), mid)

    reply = {"retryexc": "retry", "throws": "throw"}.get(variant, "raise")
    outage = variant in ("fault", "retryexc", "lastretry", "exhausted", "throws", "a1-nackfail-kill", "a2-shutdown")
    if outage:
        run.redis.stop()
    run.witness.release(lambda e: e["seq"] == barrier["seq"], reply)
    run.timeline.log("barrier_released", reply=reply)

    if variant.startswith("ackfail"):
        held = run.wait(lambda e: e["ev"] == "hook_after_retry_enqueue_barrier" and e.get("message_id") == mid, 30, "retry enqueued; worker paused before acking the original")
        run.result["after_retry_enqueued"] = {"original": locate(run.snap("retry_enqueued"), mid)}
        run.redis.stop()
        run.witness.release(lambda e: e["seq"] == held["seq"], "ok")
        if variant == "ackfail-kill":
            settle_after(run, 3)
            w1.kill_group()
            run.result["worker1_exit"] = w1.wait(10)
        else:
            settle_after(run, 8)
        run.redis.start()
    elif variant == "a1-nackfail-kill":
        run.wait(lambda e: e["ev"] == "hook_after_process_message" and e.get("message_id") == mid, 60, "hooks done (Redis still down)")
        settle_after(run, 3)
        w1.kill_group()
        run.result["worker1_exit"] = w1.wait(10)
        run.redis.start()
    elif variant == "a2-shutdown":
        settle_after(run, 3)
        w1.term()
        run.result["worker1_exit"] = w1.wait(60)
        run.result["hooks_done_before_exit"] = bool(run.witness.select(lambda e: e["ev"] == "hook_after_process_message" and e.get("message_id") == mid))
        run.redis.start()
    else:
        hook = run.wait(lambda e: e["ev"] == "hook_after_process_message" and e.get("message_id") == mid, 60, "hooks done")
        run.result["hook_after_process_message"] = hook and {k: hook.get(k) for k in ("failed", "exception", "retries")}
        if outage:
            run.redis.start()

    if run.proxy:
        run.result["proxy_rules_fired"] = [len(r["fired"]) for r in run.proxy.rules]
    settle_after(run, 12)
    mon.terminate()
    mon = monitor(run, "2")
    after = run.snap("after_settle")
    run.result["places_after_settle"] = locate(after, mid)
    run.result["dq_entries_for_message"] = [p for p in run.result["places_after_settle"] if p["payload_hash"].endswith(".DQ.msgs")]

    if w1.proc.poll() is None:
        w1.term()
        run.result["worker1_exit"] = w1.wait(60)
    mark = len(run.witness.events)
    w2 = run.worker("worker-2-replacement", {**env, **AGGRESSIVE_MAINTENANCE, "PPCS_BARRIER_AFTER_RETRY_ENQUEUE": "0"})
    boot(run, w2)
    again = run.wait(lambda e: e["seq"] > mark and e["ev"] == "task_barrier" and e.get("message_id") == mid, 15, "original redelivered to the replacement")
    if again:
        run.witness.release(lambda e: e["seq"] == again["seq"], "ok")
    settle_after(run, 8)
    final = run.snap("final")
    w2.term()
    run.result["worker2_exit"] = w2.wait(60)
    mon.terminate()
    run.result["attempts_started"] = starts(run, mid)
    run.result["executions"] = done_count(run, mid)
    run.result["retry_enqueues_seen_by_worker"] = sum(1 for e in run.witness.events if e["ev"] == "hook_after_enqueue" and e.get("message_id") == mid and e.get("queue") == "default.DQ")
    run.result["places_final"] = locate(final, mid)
    run.result["dead_letter"] = [p for p in run.result["places_final"] if p["payload_hash"].endswith(".XQ.msgs")]
    run.result["redelivered_to_replacement"] = bool(again)
    run.result["log_markers_worker1"] = markers(w1.log_text())
    run.result["outcome"] = (
        "dead-lettered" if run.result["dead_letter"]
        else "executed x%d" % run.result["executions"] if run.result["executions"]
        else "lost" if not run.result["places_final"] else "present, not executed"
    )


def f1_send(run, variant, form):
    """What actor.send() raises during an outage (exception mapping in fix a2)."""
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.redis.stop()
    probe = (
        "import os, dramatiq\n"
        "from dramatiq.brokers.redis import RedisBroker\n"
        "b = RedisBroker(%s, middleware=[])\n"
        "dramatiq.set_broker(b)\n"
        "@dramatiq.actor\n"
        "def job(): pass\n"
        "try:\n"
        "    job.send()\n"
        "except Exception as e:\n"
        "    import redis\n"
        "    print(type(e).__module__ + '.' + type(e).__name__, 'is redis.ConnectionError:', isinstance(e, redis.ConnectionError))\n"
    ) % ("url='redis://127.0.0.1:%d/0'" % run.redis_port if form == "url" else "host='127.0.0.1', port=%d" % run.redis_port)
    out = subprocess.run([run.python, "-I", "-c", probe], capture_output=True, text=True, timeout=120)
    run.result["send_raised"] = out.stdout.strip()
    run.result["stderr_tail"] = out.stderr.strip().splitlines()[-3:]
    run.timeline.log("send_probe", result=run.result["send_raised"])


# ---------------------------------------------------------------------------
# F2: ownership and recovery of delayed messages after a reconnect.
# ---------------------------------------------------------------------------

def f2(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_REPORT_STATE": "1", **AGGRESSIVE_MAINTENANCE}
    if variant.startswith("secondworker") or variant == "sigstop":
        env = {"PPCS_BROKER_FORM": form, "PPCS_REPORT_STATE": "1"}  # worker 1: defaults
    delay = {"eta-during-outage": 8000, "repeated": 40000}.get(variant, 25000)
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    mon = monitor(run, "1")
    w1, sent = hold_delayed(run, env, delay)
    mids = [m.message_id for m in sent]
    wid = run.result["worker1_broker_id"]
    w2 = None
    if variant.startswith("secondworker") or variant == "sigstop":
        env2 = {"PPCS_BROKER_FORM": form, **(LONG_HB if variant == "secondworker" else SHORT_HB)}
        w2 = run.worker("worker-2-concurrent", env2)
        boot(run, w2)
        run.result["worker2_env"] = env2
    if variant == "promotion-lostreply":
        run.proxy.add_rule("drop_reply", "enqueue", "default", count=1)

    def outage(seconds):
        run.redis.stop()
        time.sleep(seconds)
        mon_restart = run.redis.start()
        return mon_restart

    if variant in ("fault", "secondworker", "secondworker-shorthb", "sigstop", "shutdown-during-outage"):
        if variant == "shutdown-during-outage":
            run.redis.stop()
            time.sleep(4)
            w1.term()
            run.result["worker1_exit"] = w1.wait(60)
            time.sleep(4)
            run.redis.start()
        else:
            outage(15)
    elif variant == "repeated":
        outage(8)
        time.sleep(4)
        outage(8)
    elif variant == "eta-during-outage":
        time.sleep(max(0, sent[0].options["eta"] / 1000 - time.time() - 3))
        outage(15)  # the ETA passes while Redis is down
    mon.terminate()
    mon = monitor(run, "2")

    if variant == "sigstop":
        time.sleep(5)
        run.result["before_sigstop"] = sorted(set(ack_sets(run.snap("before_sigstop")).get("dramatiq:__acks__.%s.default.DQ" % wid, [])))
        os.killpg(w1.proc.pid, signal.SIGSTOP)
        run.timeline.log("worker1_sigstop")
        time.sleep(6)
        os.killpg(w1.proc.pid, signal.SIGCONT)
        run.timeline.log("worker1_sigcont")

    first_eta = min(m.options["eta"] for m in sent) / 1000
    deadline = max(first_eta, time.time()) + 35
    checkpoints = []
    while time.time() < deadline:
        time.sleep(min(10, max(0, deadline - time.time())))
        snap = run.snap("observe")
        checkpoints.append({
            "seconds_after_first_eta": round(snap["t"] - first_eta, 1),
            "executions": {m: done_count(run, m) for m in mids},
            "in_worker1_dq_ack_set": len(ack_sets(snap).get("dramatiq:__acks__.%s.default.DQ" % wid, [])),
            "worker1_heartbeat_age_ms": heartbeat_ages(snap).get(wid),
        })
    run.result["checkpoints"] = checkpoints
    w1_pid = next((e["pid"] for e in run.witness.events if e["ev"] == "hook_worker_boot" and e.get("broker_id") == wid), None)
    states = [e for e in run.witness.events if e["ev"] == "state" and e["pid"] == w1_pid]
    # Worker 1's own view of its delay queue, against Redis's view of its ack set.
    run.result["worker1_dq_delay_queue_series"] = [
        [round(e["t_server"], 1), c["delay_queue"], c["alive"]]
        for e in states for c in e["consumers"] if c["consumer"] == "default.DQ"
    ][::5]
    run.result["worker1_dq_delay_queue_sizes"] = sorted({c["delay_queue"] for e in states for c in e["consumers"] if c["consumer"] == "default.DQ"})
    run.result["executions_while_alive"] = {m: done_count(run, m) for m in mids}
    run.result["executed_by"] = sorted({e["pid"] for e in run.witness.events if e["ev"] == "task_done" and e.get("message_id") in mids})

    for proc in (w1, w2):
        if proc is not None and proc.proc.poll() is None:
            proc.term()
            proc.wait(60)
    after_exit = run.snap("after_workers_exit")
    run.result["after_workers_exit"] = ack_sets(after_exit)
    mark = len(run.witness.events)
    w3 = run.worker("worker-3-replacement", {"PPCS_BROKER_FORM": form, **AGGRESSIVE_MAINTENANCE})
    boot(run, w3)
    settle_after(run, 8)
    run.result["executions_by_replacement"] = {m: done_count(run, m, mark) for m in mids}
    final = run.snap("final")
    run.result["places_final"] = {m: locate(final, m) for m in mids}
    w3.term()
    w3.wait(60)
    mon.terminate()
    run.result["total_executions"] = {m: done_count(run, m) for m in mids}
    run.result["log_markers_worker1"] = markers(w1.log_text())


# ---------------------------------------------------------------------------
# F3: delay-queue consumer death under other timeouts and with two workers.
# ---------------------------------------------------------------------------

def f3(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_REPORT_STATE": "1", **AGGRESSIVE_MAINTENANCE}
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1, sent = hold_delayed(run, env, 120000)
    workers = [w1]
    if variant == "twoworkers-pause":
        # Pause worker 1 so that worker 2 fetches the second batch.
        os.killpg(w1.proc.pid, signal.SIGSTOP)
        w2 = run.worker("worker-2", env)
        boot(run, w2)
        p = producer(run)
        batch = [p.enqueue(job_message("delayed-w2-%d" % i, {"default": "ok"}), delay=120000) for i in range(3)]
        deadline = time.time() + 15
        while time.time() < deadline and run.snap("waiting")["keys"].get("dramatiq:default.DQ"):
            time.sleep(0.2)
        os.killpg(w1.proc.pid, signal.SIGCONT)
        workers.append(w2)
        run.result["held"] = {k: len(v) for k, v in ack_sets(run.snap("both_holding")).items()}
        sent = sent + batch
    if variant.startswith("blackhole"):
        run.proxy.blackhole(15)
    else:
        run.redis.client().execute_command("CLIENT", "PAUSE", "15000", "WRITE")
        run.timeline.log("client_pause", ms=15000)
        time.sleep(15)
    time.sleep(5)
    p = producer(run)
    probe_delayed = p.enqueue(job_message("probe-delayed", {"default": "ok"}), delay=2000)
    probe_now = p.enqueue(job_message("probe-now", {"default": "ok"}))
    settle_after(run, 40)
    run.result["probe_now_executed"] = done_count(run, probe_now.message_id) > 0
    run.result["probe_delayed_executed"] = done_count(run, probe_delayed.message_id) > 0
    snap = run.snap("after_probes")
    run.result["probe_delayed_places"] = locate(snap, probe_delayed.message_id)
    run.result["held_after"] = {k: len(v) for k, v in ack_sets(snap).items()}
    last_state = {}
    for e in run.witness.events:
        if e["ev"] == "state":
            last_state[e["pid"]] = [(c["consumer"], c["alive"], c["delay_queue"]) for c in e["consumers"]]
    run.result["last_reported_consumer_state_by_pid"] = last_state
    run.result["log_markers"] = {w.name: markers(w.log_text()) for w in workers}
    for w in workers:
        w.term()
        w.wait(60)


# ---------------------------------------------------------------------------
# F4: shutdown requeue failure without the study's shutdown barrier, with a
# timeout instead of a refused connection, and with AsyncIO installed first.
# ---------------------------------------------------------------------------

def f4(run, variant, form):
    env = {"PPCS_BROKER_FORM": form, "PPCS_REPORT_STATE": "1"}
    if "asyncio" in variant:
        env["PPCS_ASYNCIO"] = "first" if "asyncio-first" in variant else "1"
    barrier_mode = variant.startswith("pause-boundary") or variant.startswith("barrier")
    if barrier_mode:
        env["PPCS_BARRIER_CONSUMER_SHUTDOWN"] = "1"
    run.redis.start()
    run.result["environment"] = environment(run.python, run.redis.client())
    run.result["worker_env"] = env
    w1 = run.worker("worker-1", env, extra_args=("--worker-shutdown-timeout", "3000"))
    boot(run, w1)
    p = producer(run)
    sent = [p.enqueue(job_message("f4-%d" % i, {"0": "barrier" if i == 0 else "ok", "default": "ok"})) for i in range(2)]
    mids = [m.message_id for m in sent]
    first = run.wait(lambda e: e["ev"] == "task_barrier" and e.get("message_id") == mids[0], 30, "first job at its barrier")
    run.result["held_before"] = ack_sets(run.snap("before"))
    if variant.startswith("nobarrier"):
        # Redis is already down when the worker is asked to stop.
        run.redis.stop()
        w1.term()
        run.witness.release(lambda e: e["seq"] == first["seq"], "ok")
    else:
        w1.term()
        # Wait until Worker.stop() has stopped the worker threads, so the
        # prefetched job stays in the work queue (the CLI checks for the
        # signal once a second). Without this wait, the first runs of
        # pause-boundary processed both jobs and had nothing to requeue.
        run.wait(lambda e: e["ev"] == "hook_before_worker_shutdown", 30, "worker shutdown began")
        run.witness.release(lambda e: e["seq"] == first["seq"], "ok")
        for consumer in ("default", "default.DQ"):
            run.wait(lambda e, c=consumer: e["ev"] == "hook_consumer_shutdown_barrier" and e.get("consumer") == c, 30, "%s at its shutdown barrier" % consumer)
        if variant.startswith("pause-boundary"):
            run.redis.client().execute_command("CLIENT", "PAUSE", "20000", "WRITE")
            run.timeline.log("client_pause", ms=20000)
        else:
            run.redis.stop()
        run.witness.release(lambda e: e["ev"] == "hook_consumer_shutdown_barrier", "ok")
    code = w1.wait(60)
    run.result["worker1_exit"] = code
    run.result["worker1_hung"] = code is None
    states = [e for e in run.witness.events if e["ev"] == "state"]
    run.result["last_non_daemon_threads"] = states[-1]["non_daemon"] if states else None
    if code is None:
        run.result["worker1_pids_still_running"] = w1.group_pids()
        w1.kill_group()
        w1.wait(10)
    run.result["after_worker_shutdown_hook_ran"] = bool(run.witness.select(lambda e: e["ev"] == "hook_after_worker_shutdown"))
    if not run.redis.running():
        run.redis.start()
    else:
        run.redis.client().execute_command("CLIENT", "UNPAUSE")
    run.result["held_after_exit"] = ack_sets(run.snap("after_exit"))
    mark = len(run.witness.events)
    w2 = run.worker("worker-2-replacement", {"PPCS_BROKER_FORM": form, **AGGRESSIVE_MAINTENANCE})
    boot(run, w2)
    again = run.wait(lambda e: e["seq"] > mark and e["ev"] == "task_barrier" and e.get("message_id") == mids[0], 10, "first job redelivered")
    if again:
        run.witness.release(lambda e: e["seq"] == again["seq"], "ok")
    settle_after(run, 6)
    run.result["executions"] = {m: done_count(run, m) for m in mids}
    run.result["places_final"] = {m: locate(run.snap("final"), m) for m in mids}
    w2.term()
    w2.wait(60)
    text = w1.log_text()
    run.result["log_markers_worker1"] = markers(text)
    run.result["worker1_log_tail"] = text.splitlines()[-8:]


VARIANTS = {
    "f1": ["fault", "lostreply", "ackfail-recover", "ackfail-kill", "retryexc", "lastretry", "exhausted", "throws",
           "a1-nackfail-kill", "a2-shutdown", "a2-lostreply"],
    "f1send": ["outage"],
    "f2": ["fault", "secondworker", "secondworker-shorthb", "sigstop", "repeated", "eta-during-outage",
           "promotion-lostreply", "shutdown-during-outage"],
    "f3": ["pause", "blackhole", "twoworkers-pause"],
    "f4": ["nobarrier", "nobarrier-asyncio", "pause-boundary", "pause-boundary-asyncio", "barrier-asyncio-first"],
}
EXPERIMENTS = {"f1": f1, "f1send": f1_send, "f2": f2, "f3": f3, "f4": f4}
NEEDS_PROXY = {("f1", "lostreply"), ("f1", "a2-lostreply"), ("f2", "promotion-lostreply"), ("f3", "blackhole")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--variant", required=True)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--form", choices=("host", "url"), default="host")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--ports", default="56391,56392,56393")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    assert args.variant in VARIANTS[args.experiment], "unknown variant"
    ports = [int(p) for p in args.ports.split(",")]
    proxy_port = ports[2] if (args.experiment, args.variant) in NEEDS_PROXY else None
    for rep in range(1, args.reps + 1):
        variant_dir = "%s-%s%s" % (args.variant, args.form, "-" + args.tag if args.tag else "")
        run = Run(args.experiment, variant_dir, rep, ports[0], ports[1], python=args.python, proxy_port=proxy_port)
        run.result["argv"] = sys.argv
        try:
            EXPERIMENTS[args.experiment](run, args.variant, args.form)
        except Exception as exc:
            run.result["harness_error"] = "%s: %s" % (type(exc).__name__, exc)
            run.timeline.log("harness_error", error=run.result["harness_error"])
        finally:
            run.finish()
        time.sleep(1)


if __name__ == "__main__":
    main()
