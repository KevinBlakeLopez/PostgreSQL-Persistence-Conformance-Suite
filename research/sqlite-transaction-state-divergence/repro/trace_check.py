"""Methodology check: repeated trace lines for one UPDATE are trigger subprograms.

CPython's Connection.set_trace_callback reports sqlite3_expanded_sql() of the
statement on every SQLITE_TRACE_STMT event. SQLite documents that this event
fires when a statement starts and "possibly at other times during the
execution of the prepared statement, such as at the start of each trigger
subprogram". This check runs one UPDATE per case and counts trace lines,
rows changed (total_changes) and executions.

    .venv/bin/python -I repro/trace_check.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402


CASES = {
    "no-trigger": None,
    "trigger-when-false": "ROLLBACK",  # balance stays >= 0, so the WHEN clause is false
    "trigger-raise-abort": "ABORT",
    "trigger-raise-rollback": "ROLLBACK",
}


def case(name: str, action: str | None):
    def run(work: Path, token: str) -> dict:
        path = work / "db.sqlite"
        setup = sqlite3.connect(str(path), autocommit=True)
        setup.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)")
        if action is not None:
            setup.execute(
                "CREATE TRIGGER reject_invalid_balance BEFORE UPDATE ON accounts "
                f"WHEN NEW.balance < 0 BEGIN SELECT RAISE({action}, 'negative balance'); END")
        setup.execute("INSERT INTO accounts VALUES (1, 100)")
        setup.close()
        conn = sqlite3.connect(str(path), autocommit=True)
        trace: list[str] = []
        conn.set_trace_callback(trace.append)
        conn.execute("BEGIN")
        before = conn.total_changes
        amount = 30 if name in ("no-trigger", "trigger-when-false") else 500
        executions = 0
        error = None
        try:
            executions += 1
            conn.execute(f"UPDATE accounts SET balance = balance - {amount} WHERE id = 1")
        except sqlite3.Error as exc:
            error = common.error_dict(exc)
        changed = conn.total_changes - before
        in_tx = conn.in_transaction
        conn.close()
        update_lines = [line for line in trace if line.startswith("UPDATE")]
        return {
            "observed": {
                "python_executions": executions,
                "update_trace_lines": len(update_lines),
                "total_changes_delta": changed,
                "error": None if error is None else (error.get("driver") or {}).get("sqlite_errorname"),
                "in_transaction_after": in_tx,
            },
            "trace": trace,
        }
    return run


def main() -> None:
    common.run_experiment("trace-check", [(name, case(name, action)) for name, action in CASES.items()])


if __name__ == "__main__":
    main()
