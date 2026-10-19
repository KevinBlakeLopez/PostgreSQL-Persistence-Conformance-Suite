"""Run every SQLite Phase 0 variant three times, each on a fresh database file.

Usage, from the repository root of the sqlite worktree:

    /opt/homebrew/bin/python3.13 research/sqlite-phase0/controls/run_all.py

Evidence is written under research/sqlite-phase0/evidence/<run-id>/.
The script does not delete other runs and does not touch PostgreSQL.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness
import sqlite_01_constraint
import sqlite_02_commit_busy
import sqlite_03_savepoint
import sqlite_04_cleanup
import sqlite_05_ddl
import sqlite_06_reporting


REPETITIONS = 3
ROOT = Path(__file__).resolve().parents[1]


def all_variants() -> list[tuple[str, str, object]]:
    groups = [
        ("SQLITE-01", sqlite_01_constraint.variants()),
        ("SQLITE-02", sqlite_02_commit_busy.variants()),
        ("SQLITE-03", sqlite_03_savepoint.variants()),
        ("SQLITE-04", sqlite_04_cleanup.variants()),
        ("SQLITE-05", sqlite_05_ddl.variants()),
        ("SQLITE-06", sqlite_06_reporting.variants()),
    ]
    found = []
    for experiment, variants in groups:
        for name, function in variants:
            found.append((experiment, name, function))
    return found


def main() -> None:
    harness.require_python()
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ") + f"-py{sys.version_info[0]}{sys.version_info[1]}"
    run_dir = ROOT / "evidence" / run_id
    db_dir = run_dir / "db"
    case_dir = run_dir / "cases"
    db_dir.mkdir(parents=True, exist_ok=True)
    environment = harness.environment_report(db_dir / "environment-sample.sqlite")
    harness.write_json(run_dir / "environment.json", environment)

    summary_cases = []
    for experiment, variant, function in all_variants():
        fingerprints = []
        for repetition in range(1, REPETITIONS + 1):
            db_path = db_dir / f"{experiment}.{variant}.rep{repetition}.sqlite"
            label = f"{experiment}.{variant}.rep{repetition}"
            try:
                result = function(db_path)
            except Exception as exc:
                result = harness.experiment_error(exc)
                traceback.print_exc()
            result["experiment"] = experiment
            result["variant"] = variant
            result["repetition"] = repetition
            result["database"] = str(db_path)
            result["sidecars"] = harness.sidecars(db_path)
            if not result.get("fingerprint"):
                result["fingerprint"] = harness.fingerprint(result.get("observed") or result.get("error"))
            harness.write_json(case_dir / f"{label}.json", result)
            fingerprints.append(result.get("fingerprint"))
            status = result.get("status")
            print(f"{label} {status}", flush=True)
        unique = sorted({item for item in fingerprints if item is not None})
        summary_cases.append({
            "experiment": experiment,
            "variant": variant,
            "repetitions": REPETITIONS,
            "fingerprint_count": len(unique),
            "agreed": len(unique) == 1,
            "statuses": "recorded in case files",
        })
        if len(unique) != 1:
            print(f"NONDETERMINISTIC {experiment}.{variant} fingerprints={len(unique)}", flush=True)

    summary = {
        "run_id": run_id,
        "repetitions": REPETITIONS,
        "python": sys.version,
        "sqlite": harness.sqlite3.sqlite_version if hasattr(harness, "sqlite3") else __import__("sqlite3").sqlite_version,
        "cases": summary_cases,
        "agreement": all(item["agreed"] for item in summary_cases),
    }
    harness.write_json(run_dir / "summary.json", summary)
    print(f"evidence {run_dir}", flush=True)
    print(f"agreement {summary['agreement']}", flush=True)


if __name__ == "__main__":
    main()
