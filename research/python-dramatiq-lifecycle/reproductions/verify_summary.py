"""Summaries for the adversarial verification: outputs/verify/SUMMARY.md.

  python -I verify_summary.py

One row per experiment, variant and build, with counts taken from each run's
result.json, and the regression-test matrix from linux-regression/.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

VERIFY = Path(__file__).resolve().parent.parent / "outputs" / "verify"


def f1_row(runs):
    outcomes = Counter(r.get("outcome") for r in runs)
    dup = sum(1 for r in runs if r.get("executions", 0) > 1)
    crit = sum(1 for r in runs if r.get("log_markers_worker1", {}).get("Unexpected failure in after_process_message"))
    return "; ".join("%s %d/%d" % (k, v, len(runs)) for k, v in sorted(outcomes.items())) + \
        "; more than one execution %d/%d; CRITICAL 'Unexpected failure' logged %d/%d" % (dup, len(runs), crit, len(runs))


def f1send_row(runs):
    return "; ".join(sorted({r.get("send_raised", "?") for r in runs}))


def f2_row(runs):
    alive_all = sum(1 for r in runs if r.get("executions_while_alive") and all(v >= 1 for v in r["executions_while_alive"].values()))
    alive_none = sum(1 for r in runs if r.get("executions_while_alive") and all(v == 0 for v in r["executions_while_alive"].values()))
    dup = sum(1 for r in runs if any(v > 1 for v in r.get("total_executions", {}).values()))
    lost = sum(1 for r in runs if any(v == 0 for v in r.get("total_executions", {}).values()))
    dropped = sum(1 for r in runs if r.get("worker1_dq_delay_queue_sizes") and min(r["worker1_dq_delay_queue_sizes"]) == 0
                  and r.get("executions_while_alive") and all(v == 0 for v in r["executions_while_alive"].values()))
    return ("all ran while worker 1 alive %d/%d; none ran while alive %d/%d; worker 1's in-memory delay queue emptied while unrun %d/%d; "
            "a message ran more than once %d/%d; a message never ran %d/%d") % (alive_all, len(runs), alive_none, len(runs), dropped, len(runs), dup, len(runs), lost, len(runs))


def f3_row(runs):
    dead = 0
    for r in runs:
        states = r.get("last_reported_consumer_state_by_pid", {})
        if any(not alive for st in states.values() for consumer, alive, _ in st if consumer == "default.DQ"):
            dead += 1
    probe = sum(1 for r in runs if r.get("probe_delayed_executed"))
    ordinary = sum(1 for r in runs if r.get("probe_now_executed"))
    held = sum(1 for r in runs if any(v for v in r.get("held_after", {}).values()))
    return "delay-queue consumer reported dead %d/%d; later delayed probe ran %d/%d; ordinary probe ran %d/%d; held messages still in an ack set %d/%d" % (
        dead, len(runs), probe, len(runs), ordinary, len(runs), held, len(runs))


def f4_row(runs):
    codes = Counter("hung" if r.get("worker1_hung") else str(r.get("worker1_exit")) for r in runs)
    hook = sum(1 for r in runs if r.get("after_worker_shutdown_hook_ran"))
    warn = sum(1 for r in runs if r.get("log_markers_worker1", {}).get("Failed to requeue messages"))
    recovered = sum(1 for r in runs if r.get("executions") and all(v >= 1 for v in r["executions"].values()))
    return "exit %s; after_worker_shutdown ran %d/%d; requeue warning %d/%d; all jobs ran eventually %d/%d" % (
        ", ".join("%s: %d" % kv for kv in sorted(codes.items())), hook, len(runs), warn, len(runs), recovered, len(runs))


ROWS = {"f1": f1_row, "f1send": f1send_row, "f2": f2_row, "f3": f3_row, "f4": f4_row}


def regression_matrix():
    base = VERIFY / "linux-regression"
    tests, trees = [], {}
    for path in sorted(base.glob("regression-*.txt")):
        tree = path.stem[len("regression-"):]
        results = {}
        for line in path.read_text().splitlines():
            m = re.match(r"^(PASSED|FAILED|ERROR) tests/test_ppcs_lifecycle.py::(test_\w+)", line)
            if m:
                results[m.group(2)] = m.group(1)
                if m.group(2) not in tests:
                    tests.append(m.group(2))
        trees[tree] = results
    order = ["master", "fix-d4-a1", "fix-d4-a2", "fix-redis-reconnect", "fix-redis-requeue-mapping", "pr895", "combo-a1-reconnect", "combo-a2-reconnect"]
    cols = [t for t in order if t in trees]
    lines = ["| Test | " + " | ".join(cols) + " |", "| --- | " + " | ".join("---" for _ in cols) + " |"]
    for test in tests:
        lines.append("| `%s` | %s |" % (test, " | ".join(trees[c].get(test, "-") for c in cols)))
    suites = []
    for path in sorted(base.glob("suite-*.txt")):
        last = [line for line in path.read_text().splitlines() if line.strip()][-1:]
        suites.append("| %s | %s |" % (path.stem[len("suite-"):], last[0] if last else "-"))
    return lines, suites


def main():
    groups = defaultdict(list)
    errors = Counter()
    for path in sorted(VERIFY.glob("*/*/*/result.json")):
        exp, variant = path.parts[-4], path.parts[-3]
        if exp not in ROWS:
            continue
        r = json.loads(path.read_text())
        key = (exp, variant, r.get("environment", {}).get("dramatiq_build", "?"))
        if r.get("harness_error"):
            errors[key] += 1
            continue
        groups[key].append(r)
    out = ["# Adversarial verification: grouped results", "",
           "Generated by `reproductions/verify_summary.py`. One row per experiment, variant and build; macOS.", "",
           "| Experiment | Variant | Build | Runs | Observed |", "| --- | --- | --- | --- | --- |"]
    for key in sorted(set(groups) | set(errors)):
        runs = groups.get(key, [])
        text = ROWS[key[0]](runs) if runs else "-"
        if errors.get(key):
            text += " (plus %d run(s) ended by a harness error, not counted)" % errors[key]
        out.append("| %s | %s | %s | %d | %s |" % (key[0].upper(), key[1], key[2], len(runs), text))
    lines, suites = regression_matrix()
    out += ["", "## Regression tests (Linux container, Dramatiq's own fixtures)", ""] + lines
    if suites:
        out += ["", "## Dramatiq's test suite, minus benchmarks (RabbitMQ and memcached tests skip without servers)", "",
                "| Tree | Result |", "| --- | --- |"] + suites
    text = "\n".join(out) + "\n"
    (VERIFY / "SUMMARY.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
