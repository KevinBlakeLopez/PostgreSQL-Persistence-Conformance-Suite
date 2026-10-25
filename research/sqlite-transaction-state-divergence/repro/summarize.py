"""Render output/RESULTS.md from the latest recorded run of each experiment.

Every cell comes from a run's summary.json (the first repetition's observed
section; the agreement column says whether all three repetitions matched).
Nothing here re-runs an experiment.

    .venv/bin/python -I repro/summarize.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402


EXPERIMENTS = ("trace-check", "sqlite01-raw", "sqlite02-core", "sqlite03-session", "sqlite04-savepoint",
               "sqlite05-realistic", "sqlite05b-batch", "sqlite05c-enospc", "sqlite06-django")


def latest(experiment: str) -> Path | None:
    root = common.OUTPUT / experiment
    runs = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    return runs[-1] if runs else None


def load(experiment: str) -> tuple[str, dict[str, Any]] | None:
    run = latest(experiment)
    if run is None:
        return None
    return run.name, json.loads((run / "summary.json").read_text(encoding="utf-8"))


def st(value: Any) -> str:
    """A step outcome in a few words."""
    if value in (None, "not-run"):
        return "–"
    if isinstance(value, str):
        return value
    name = value.get("sqlite_errorname") or value.get("error") or (value.get("type") or "").split(".")[-1]
    message = value.get("message") or ""
    return f"{name}: {message}" if message else str(name)


def steps(rows: Any) -> str:
    if not isinstance(rows, list):
        return str(rows)
    flat = [row[0] if isinstance(row, list) else row for row in rows]
    return ", ".join(str(x) for x in flat) if flat else "none"


def b_ran(write_b: dict[str, Any] | None, early_key: str) -> str:
    if not write_b:
        return "–"
    if write_b.get(early_key):
        return "autocommit (visible before completion)"
    sql = write_b.get("sql_started") or []
    if any(s.strip().upper() == "BEGIN" or s.startswith("BEGIN ") for s in sql[:-1]):
        return "new implicit transaction"
    return "same transaction"


def table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |")
    return out


def section(title: str, experiment: str, render) -> list[str]:
    loaded = load(experiment)
    if loaded is None:
        return [f"## {title}", "", f"No recorded run of `{experiment}`.", ""]
    run_id, summary = loaded
    lines = [f"## {title}", "",
             f"Run `output/{experiment}/{run_id}/`, {len(summary['variants'])} variants, "
             f"{summary['repetitions']} repetitions each, all repetitions agree: {summary['agreement']}.", ""]
    lines += render(summary["variants"])
    lines.append("")
    return lines


def r_trace(variants: dict) -> list[str]:
    rows = [[n, v["agreement"], o["python_executions"], o["update_trace_lines"], o["total_changes_delta"],
             o["error"] or "–", o["in_transaction_after"]]
            for n, v in variants.items() for o in [v["observed"]]]
    return table(["Variant", "Agree", "Executions", "Trace lines for the UPDATE", "Rows changed", "Error",
                  "in_transaction after"], rows)


def r_raw(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        fault = "no error" if o["fault"] == "ok" else f"{o['fault']['error']} ({o['fault_error_code']})"
        recovery = "" if not o.get("recovery") else f"; recovery {o['recovery']['method']}: {st(o['recovery']['status'])}"
        rows.append([n, v["agreement"], fault, o["in_transaction"]["after-fault"],
                     steps(o["writer_view"]["after-fault"]["ledger"]),
                     b_ran(o["write_b"], "observer_saw_b_before_complete"),
                     st(o["complete"]) + recovery, steps(o["persisted_after_complete"]["ledger"]),
                     f"write {st(o['next_unit']['write'])}, rollback {st(o['next_unit']['rollback'])}",
                     steps(o["persisted_final"]["ledger"])])
    return table(["Variant", "Agree", "Fault error", "SQLite in_transaction after fault", "Writer still sees",
                  "Write B ran in", "Completion", "Committed after completion", "Next unit (writes N, rolls back)",
                  "Committed at end"], rows)


def later(units: list[dict], same_key: str | None) -> str:
    parts = []
    for u in units:
        reuse = ""
        if same_key and u.get(same_key) is not None:
            reuse = " same conn" if u[same_key] else " new conn"
        parts.append(f"{u['unit']} {u['ending']}{reuse}: {st(u['outcome'])}")
    return "; ".join(parts)


def r_core(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        af = o["state_after_fault"] or {}
        rows.append([n, v["agreement"], st(o["fault"]),
                     af.get("sqlite_in_transaction", "–"), af.get("sa_in_transaction", "–"),
                     b_ran(o["write_b"], "observer_saw_b_before_completion"),
                     st(o["unit_1"]["outcome"]), " / ".join(o["unit_1"]["end_sql_started"]) or "no SQL",
                     steps(o["unit_1"]["persisted"]["ledger"]),
                     later(o["later_units"], "same_dbapi_as_unit_1"),
                     steps(o["persisted_final"]["ledger"]), o["pool_at_end"]["checked_out_before_gc"]])
    return table(["Variant", "Agree", "Fault", "SQLite in_transaction after fault", "SQLAlchemy in_transaction()",
                  "Write B ran in", "Unit 1 completion", "SQL at completion", "Committed after unit 1",
                  "Later units", "Committed at end", "Checked out at end"], rows)


def r_session(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        af = o["after_fault_session"] or {}
        acc1 = ((o.get("after_fault_objects") or {}).get("acc1") or {}).get("loaded", {}).get("balance", "–")
        hooks = sorted({e[0].split(":")[1] for e in o["sink"] if e[0].startswith("unit-1:") and e[0] != "unit-1:after_begin"})
        rows.append([n, v["agreement"], st(o["fault"]),
                     (af.get("sqlite_in_transaction") or {}).get("dbapi0", "–") if af else "–",
                     af.get("sa_session_is_active", "–"), acc1,
                     st(o["unit_1"]["outcome"]), steps(o["unit_1"]["persisted"]["ledger"]),
                     ", ".join(hooks) or "none",
                     "yes" if any("Identity map already had an identity" in w for w in o["unit_1"]["warnings"]) else "no",
                     later(o["later_units"], None), o["pool_at_end"]["checked_out_before_gc"]])
    return table(["Variant", "Agree", "Fault", "SQLite in_transaction after fault", "Session.is_active after fault",
                  "acc1.balance in identity map", "Unit 1 outcome", "Committed after unit 1", "Unit 1 hooks",
                  "Identity replaced warning", "Later units", "Checked out at end"], rows)


def r_savepoint(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        h = o["handled_by_outer"]
        an = o["after_nested"] or {}
        sqlite = an.get("sqlite_in_transaction") or {}
        hooks = sorted({e[0].split(":")[1] for e in o["sink"] if e[0].startswith("unit-1:")})
        rows.append([n, v["agreement"], "not caught" if h is None else h["chain"][0],
                     sqlite.get("dbapi0", "–") if isinstance(sqlite, dict) else sqlite,
                     an.get("sa_in_transaction", an.get("sa_session_in_transaction", "–")),
                     st(o["unit_1"]["outcome"]), steps(o["unit_1"]["persisted"]["ledger"]),
                     ", ".join(hooks) or "none", st(o["later_unit_N1"]["outcome"])])
    return table(["Variant", "Agree", "Error the outer scope caught", "SQLite in_transaction after nested scope",
                  "SQLAlchemy in_transaction after nested scope", "Unit 1 outcome", "Committed",
                  "Unit 1 hooks", "Later unit N1"], rows)


def r_realistic(variants: dict) -> list[str]:
    rows = [[n, v["agreement"], f"{o['fault_error']} ({o['fault_error_code']})" if o["fault_error_code"] else o["fault_error"],
             o["in_transaction_after_fault"], o["writer_sees_a_after_fault"], st(o["write_b"]),
             o["write_b_in_transaction_after"], st(o["commit"]), steps(o["persisted_ledger"])]
            for n, v in variants.items() for o in [v["observed"]]]
    return table(["Variant", "Agree", "Error", "SQLite in_transaction after the error", "Writer still sees A",
                  "Write B", "in_transaction after B", "COMMIT", "Committed"], rows)


def r_batch(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        rows.append([n, v["agreement"], st(o["import_outcome"]), o["application_skipped"],
                     o["application_claims_committed"], o["persisted_seqs"], o["claim_matches_database"]])
    return table(["Variant", "Agree", "Import outcome", "Application skipped", "Application reports committed",
                  "Committed", "Report matches database"], rows)


def r_enospc(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        c = o["container"]
        env = f"Python {c['python']}, SQLite {c['sqlite']}" + (f", SQLAlchemy {c['sqlalchemy']}" if c.get("sqlalchemy") else "")
        if n == "raw":
            rows.append([n, v["agreement"], env, f"record {o['failed_seq']}: {o['first_error']}",
                         f"in_transaction {o['in_transaction_after_error']}", "; ".join(o["commit_error"] or ["ok"]),
                         "–", o["committed_seqs"]])
        else:
            rows.append([n, v["agreement"], env, f"skipped {o['skipped_seqs']}: {'; '.join(o['skipped_errors'])}",
                         "–", "; ".join(o["commit_error"] or ["returned normally"]),
                         o["application_claims_committed"], o["committed_seqs"]])
    return table(["Variant", "Agree", "Container", "Failure", "SQLite state", "Commit",
                  "Application reports committed", "Committed"], rows)


def r_django(variants: dict) -> list[str]:
    rows = []
    for n, v in variants.items():
        o = v["observed"]
        sf = o["state_after_fault"] or {}
        rows.append([n, v["agreement"], (o["handled"] or ["not caught"])[0], sf.get("needs_rollback", "–"),
                     sf.get("sqlite_in_transaction", "–"), st(o["write_b"]), st(o["atomic_outcome"]),
                     ", ".join(o["on_commit_ran"]) or "not run", steps(o["persisted"]["ledger"])])
    return table(["Variant", "Agree", "Error the application caught", "needs_rollback after fault",
                  "SQLite in_transaction after fault", "Write B", "atomic() outcome", "on_commit", "Committed"], rows)


def minimal_matrix() -> list[str]:
    root = common.OUTPUT / "minimal-matrix"
    runs = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    if not runs:
        return ["## Minimal reproductions", "", "No recorded run.", ""]
    run = runs[-1]
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    lines = ["## Minimal reproductions across environments", "", f"Run `output/minimal-matrix/{run.name}/`.", ""]
    lines += table(["Environment", "Python, SQLite, SQLAlchemy"], [[k, v] for k, v in summary["environments"].items()])
    lines.append("")
    rows = [[key, *(by_env[e]["three_runs_identical"] for e in summary["environments"]), by_env["all_environments_identical"]]
            for key, by_env in summary["scripts"].items()]
    lines += table(["Script", *(f"{e}: 3 runs identical" for e in summary["environments"]), "All environments identical"], rows)
    lines.append("")
    first = next(iter(summary["environments"]))
    for key in summary["scripts"]:
        lines += [f"`{key}`, {first}, repetition 1:", "", "```"]
        lines += (run / first / f"{key}.rep1.out").read_text(encoding="utf-8").rstrip("\n").splitlines()
        lines += ["```", ""]
    return lines


def main() -> None:
    lines = ["# Results (generated)", "",
             "Generated by `repro/summarize.py` from the latest run of each experiment. Do not edit by hand.",
             "The raw records are the `cases/*.json` files in each run directory.", ""]
    lines += section("Trace callback check", "trace-check", r_trace)
    lines += section("SQLITE-01: sqlite3", "sqlite01-raw", r_raw)
    lines += section("SQLITE-02: SQLAlchemy Core", "sqlite02-core", r_core)
    lines += section("SQLITE-03: SQLAlchemy ORM Session", "sqlite03-session", r_session)
    lines += section("SQLITE-04: savepoints", "sqlite04-savepoint", r_savepoint)
    lines += section("SQLITE-05: realistic failures, sqlite3", "sqlite05-realistic", r_realistic)
    lines += section("SQLITE-05b: SQLAlchemy's documented SAVEPOINT loops", "sqlite05b-batch", r_batch)
    lines += section("SQLITE-05c: a real ENOSPC, in a container", "sqlite05c-enospc", r_enospc)
    lines += section("SQLITE-06: Django atomic()", "sqlite06-django", r_django)
    lines += minimal_matrix()
    target = common.OUTPUT / "RESULTS.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(target.relative_to(common.STUDY))


if __name__ == "__main__":
    main()
