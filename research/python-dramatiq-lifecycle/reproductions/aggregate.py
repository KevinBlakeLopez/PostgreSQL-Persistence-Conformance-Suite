"""Aggregate every recorded run into one table row per experiment, variant,
build and platform. Writes outputs/AGGREGATE.md.

  python -I aggregate.py
"""

import json
from collections import defaultdict
from pathlib import Path

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


def held_by(places, suffix):
    return any(h.endswith(suffix) for p in places for h in p["held_by"])


def witnessed_done(r):
    # From the witness record itself: a task_done event for this message.
    path = OUTPUTS.parent / r["dir"] / "witness.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    return any(e["ev"] == "task_done" and e.get("message_id") == r.get("message_id") for e in events)


def d4(runs):
    n = len(runs)
    lost = sum(bool(r.get("message_lost")) for r in runs)
    retried = sum(bool(r.get("retry_enqueued_by_worker")) for r in runs)
    completed = sum(witnessed_done(r) for r in runs)
    dlq = sum(held_by(r.get("places_final", []), ".XQ") for r in runs)
    redelivered = sum(any(a == 0 for a, _ in r.get("attempts_started", [])[1:]) for r in runs)
    durable = [r for r in runs if "places_after_final_redis_restart" in r]
    parts = []
    if lost:
        parts.append("message deleted (no retry, no dead letter, no further attempt) in %d/%d" % (lost, n))
    if retried:
        parts.append("retry enqueued in %d/%d" % (retried, n))
    if completed:
        parts.append("completed in %d/%d" % (completed, n))
    if dlq:
        parts.append("dead-lettered in %d/%d" % (dlq, n))
    if redelivered:
        parts.append("original redelivered after SIGKILL in %d/%d" % (redelivered, n))
    if durable:
        gone = sum(not r["places_after_final_redis_restart"] for r in durable)
        parts.append("after a final Redis restart: %d/%d absent, %d/%d present" % (gone, len(durable), len(durable) - gone, len(durable)))
    return "; ".join(parts) or "-"


def n1(runs):
    n = len(runs)
    observed = [r for r in runs if "checkpoints" in r]
    ran_alive = sum(len(r.get("executed_while_worker1_alive", [])) == len(r.get("message_ids", [1, 2, 3])) for r in observed)
    stranded = [r for r in observed if r["checkpoints"] and r["checkpoints"][-1]["still_in_worker1_dq_ack_set"]]
    parts = ["all delayed jobs ran while worker 1 was alive in %d/%d" % (ran_alive, len(observed))] if observed else ["worker 1 SIGKILLed before the ETA in %d/%d" % (n, n)]
    if stranded:
        last = min(r["checkpoints"][-1]["seconds_after_first_eta"] for r in stranded)
        ages = [c["worker1_heartbeat_age_ms"] for r in stranded for c in r["checkpoints"] if c.get("worker1_heartbeat_age_ms") is not None]
        parts.append("stranded in worker 1's ack set at the last checkpoint (>= %s s after ETA, heartbeat <= %d ms old) in %d/%d" % (last, max(ages), len(stranded), n))
    left = [r for r in runs if r.get("executed_by_replacement") or (r.get("checkpoints") and r["checkpoints"][-1]["still_in_worker1_dq_ack_set"])]
    if left:
        rec = sum(len(r.get("executed_by_replacement", [])) == len(r.get("message_ids", [1, 2, 3])) for r in left)
        parts.append("the jobs left over were all run by a replacement after worker 1 stopped in %d/%d" % (rec, len(left)))
    return "; ".join(parts)


def n2(runs):
    n = len(runs)
    died = sum(r.get("log_markers_worker1", {}).get("Exception in thread", 0) > 0 for r in runs)
    probe = sum(bool(r.get("probe_delayed_executed")) for r in runs)
    ordinary = sum(bool(r.get("probe_now_executed")) for r in runs)
    pauses = sorted({r.get("pause_ms") or 15000 for r in runs})
    return "pause %s ms; delay-queue consumer thread died in %d/%d; delayed probe ran in %d/%d; ordinary probe ran in %d/%d" % (
        "/".join(map(str, pauses)), died, n, probe, n, ordinary, n)


def d7(runs):
    n = len(runs)
    codes = defaultdict(int)
    for r in runs:
        codes["hung" if r.get("worker1_hung") else str(r.get("worker1_exit"))] += 1
    hook = sum(bool(r.get("after_worker_shutdown_hook_ran")) for r in runs)
    warned = sum(r.get("log_markers_worker1", {}).get("Failed to requeue messages", 0) > 0 for r in runs)
    recovered = sum(len(r.get("executed_by_replacement", [])) == 2 for r in runs)
    secs = [r["recovery_seconds_after_replacement_boot"] for r in runs if r.get("recovery_seconds_after_replacement_boot", 0) > 1]
    text = "worker 1 exit %s; after_worker_shutdown ran in %d/%d; requeue warning logged in %d/%d; remaining jobs run by a replacement in %d/%d" % (
        ", ".join("%s: %d" % kv for kv in sorted(codes.items())), hook, n, warned, n, recovered, n)
    if secs:
        text += " (after %s s with default maintenance)" % ", ".join("%.0f" % s for s in secs)
    return text


SUMMARIZE = {"d4": d4, "n1": n1, "n2": n2, "d7": d7}


def main():
    groups = defaultdict(list)
    errors = defaultdict(int)
    for path in sorted(OUTPUTS.rglob("result.json")):
        rel = path.relative_to(OUTPUTS).parts
        platform = "Linux" if rel[0] == "linux" else "macOS"
        rel = rel[1:] if rel[0] == "linux" else rel
        if rel[0] not in SUMMARIZE:
            continue
        r = json.loads(path.read_text())
        build = r.get("environment", {}).get("dramatiq_build", "?")
        key = (rel[0], rel[1], build, platform)
        if r.get("harness_error"):
            errors[key] += 1
            continue
        groups[key].append(r)
    lines = ["| Experiment | Variant | Build | Platform | Runs | Observed |", "| --- | --- | --- | --- | --- | --- |"]
    for key in sorted(set(groups) | set(errors)):
        experiment, variant, build, platform = key
        runs = groups.get(key, [])
        observed = SUMMARIZE[experiment](runs) if runs else "-"
        if errors.get(key):
            observed += " (plus %d run(s) ended by a harness error, not counted)" % errors[key]
        lines.append("| %s | %s | %s | %s | %d | %s |" % (experiment.upper(), variant, build, platform, len(runs), observed))
    text = "# Aggregated results\n\nGenerated by `reproductions/aggregate.py` from every `result.json`.\n\n" + "\n".join(lines) + "\n"
    (OUTPUTS / "AGGREGATE.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
