"""Tally the P8 runs per cell. Usage: summarize.py <output-dir>  (writes <output-dir>/summary.json)"""
import collections
import json
import os
import sys

OUT = sys.argv[1]


def load(name):
    with open(os.path.join(OUT, name)) as f:
        return [json.loads(l) for l in f if l.strip()]


# The 2.1.5 psycopg SIGINT rep 3 record in results-sa215.jsonl is invalid (gated false: port 8800 was
# taken by another local service); results-sa215-rerun.jsonl holds its rerun.
sets = {"2.1.6": load("results-sa216.jsonl"),
        "2.1.5": [r for r in load("results-sa215.jsonl") if r.get("gated")] + load("results-sa215-rerun.jsonl")}
rows = []
for sa, runs in sets.items():
    cells = collections.OrderedDict()
    for r in runs:
        cells.setdefault((r["driver"], r["mode"]), []).append(r)
    for (driver, mode), rs in cells.items():
        def frac(pred):
            return f"{sum(1 for r in rs if pred(r))}/{len(rs)}"
        rows.append({
            "SQLAlchemy": sa, "driver": driver, "signal": mode, "runs": len(rs),
            "returncodes": sorted({r["process"]["returncode"] for r in rs}),
            "fate_at_exit": sorted({r["at_process_exit"]["fate"] for r in rs}),
            "fate_final": sorted({r["final"]["fate"] for r in rs}),
            "marker_visible": frac(lambda r: r["final"]["marker_visible"]),
            "after_rollback_before_exit": frac(lambda r: r["fired_before_exit"]["orm.after_rollback"]),
            "after_soft_rollback_before_exit": frac(lambda r: r["fired_before_exit"]["orm.after_soft_rollback"]),
            "after_commit_before_exit": frac(lambda r: r["fired_before_exit"]["orm.after_commit"]),
            "pool_invalidate_before_exit": frac(lambda r: r["fired_before_exit"]["pool.invalidate"]),
            "handler_saw_CancelledError": frac(lambda r: (r["request_raised"] or "").startswith("asyncio.exceptions.CancelledError")),
            "finally_ran": frac(lambda r: r["fired_before_exit"]["request.finally"]),
            "cancel_reached_server": frac(lambda r: any("canceling statement" in s for s in r.get("server_log", []))),
            "client": sorted({r["timeline_s_from_signal"]["client"].get("status_line", "") for r in rs}),
            "exit_after_signal_s": [round(r["timeline_s_from_signal"]["process_exit_observed"], 2) for r in rs],
        })
with open(os.path.join(OUT, "summary.json"), "w") as f:
    json.dump(rows, f, indent=1)
for row in rows:
    print(json.dumps(row))
