"""Count repetitions per evidence category across every recorded run.

The categories are the ones findings.md quotes; each is defined here by case name,
so the totals there can be recomputed from outputs/ with:  python tally.py ../outputs
"""

import json
import statistics
import sys
from pathlib import Path

RUNS = ("e1-run1", "e1-run2", "e1-run3-standard", "e3-run1")
# Run 1's Hypercorn cases are excluded everywhere: the harness lost track of the worker process.
EXCLUDED = {("e1-run1", "e1-08-hypercorn-exceeds-term"), ("e1-run1", "e1-09-hypercorn-exceeds-int")}

CATEGORIES = {
    "A. unpatched, work outlives timeout, 0.5 s cleanup": [
        "e1-03-exceeds-term", "e1-04-exceeds-int", "e1-06-fastapi-bg-exceeds-term", "e1-10-main-exceeds-term",
        "e1-11-main-exceeds-int", "e1-15-py314-exceeds-term", "e1-16-exceeds-term-shielded",
        "e1-17-exceeds-int-shielded", "e1-18-standard-exceeds-term", "e1-19-standard-exceeds-int",
        "e3-01-release-exceeds-term", "e3-02-release-exceeds-int", "e3-07-release-shared-term",
        "e3-08-release-shared-int"],
    "B. unpatched, release answered at once": ["e1-05-exceeds-term-fast-release"],
    "C. unpatched, 5 s cleanup": ["e3-17-release-long-cleanup-term", "e3-20-release-long-cleanup-int-int"],
    "D. unbounded fix, 0.5 s cleanup": [
        "e1-12-fix-exceeds-term", "e1-13-fix-exceeds-int", "e1-14-fix-fastapi-bg-exceeds-term",
        "e3-03-fix-exceeds-term", "e3-04-fix-exceeds-int", "e3-09-fix-shared-term"],
    "E. bounded fix, 0.5 s cleanup": ["e3-05-fixb-exceeds-term", "e3-06-fixb-exceeds-int", "e3-10-fixb-shared-term"],
    "F. controls: work finishes in time / no timeout": [
        "e1-01-in-time-term", "e1-02-in-time-int", "e1-07-fastapi-bg-no-timeout-term"],
}


def main() -> None:
    root = Path(sys.argv[1])
    by_case: dict[str, list[dict]] = {}
    for run in RUNS:
        for path in sorted((root / run).glob("*/results.json")):
            data = json.loads(path.read_text())
            case = data["meta"]["case"]
            if (run, case) in EXCLUDED:
                continue
            by_case.setdefault(case, []).extend(data["results"])
    for name, cases in CATEGORIES.items():
        reps = [r for case in cases for r in by_case.get(case, [])]
        gaps = []
        for r in reps:
            seen: dict[str, float] = {}
            for line in r["witness"]:
                t, _, event = line.split(" ", 2)
                seen.setdefault(event.split()[0], float(t))
            begin = next((t for e, t in seen.items() if e.endswith(".cleanup.begin")), None)
            lifespan = seen.get("lifespan.shutdown.begin")
            if begin is not None and lifespan is not None:
                gaps.append((lifespan - begin) * 1000)
        finished = sum(r["cleanup_finished"] for r in reps)
        before = sum(r["lifespan_shutdown_before_cleanup_finished"] for r in reps)
        incomplete = sum(1 for r in reps if r.get("observation_complete") is False)
        gap = f"{min(gaps):.2f}-{max(gaps):.2f} ms (median {statistics.median(gaps):.2f})" if gaps else "n/a"
        print(f"{name}: {len(reps)} reps; cleanup finished {finished}; lifespan shutdown began before cleanup "
              f"finished {before}; incomplete observation {incomplete}; lifespan shutdown after cleanup began: {gap}")


if __name__ == "__main__":
    main()
