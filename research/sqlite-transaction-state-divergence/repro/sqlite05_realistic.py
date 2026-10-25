"""SQLITE-05: do realistic SQLite failures end the transaction?

Each variant opens an explicit transaction (autocommit=True, SQL BEGIN), writes
ledger row A, then runs one statement that fails for a reason that is not a
deliberate RAISE(ROLLBACK):

    full-*       SQLITE_FULL from PRAGMA max_page_count (the database may not
                 grow past a page count; SQLite's own limit, not a fault hook)
    interrupt-*  SQLITE_INTERRUPT from a progress handler that asks SQLite to
                 stop (a statement time limit), or from Connection.interrupt()
                 called by another thread
    fsize-*      a real write failure: a child process runs under a file-size
                 limit (RLIMIT_FSIZE, SIGXFSZ ignored), so write() fails with
                 EFBIG or writes short; a small cache_size makes SQLite write
                 pages during the statement

The record says whether SQLite still has the transaction (in_transaction),
whether the writer still sees A, what a later write B does, and what COMMIT
returns. A second connection reads the file afterwards.

    .venv/bin/python -I repro/sqlite05_realistic.py
"""

from __future__ import annotations

import json
import os
import resource
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402


SCHEMA = (
    "CREATE TABLE ledger (id INTEGER PRIMARY KEY, token TEXT NOT NULL, step TEXT NOT NULL)",
    "CREATE TABLE blobs (id INTEGER PRIMARY KEY, data BLOB)",
    "CREATE TABLE blobs_unique (id INTEGER PRIMARY KEY, k TEXT UNIQUE, data BLOB)",
    "CREATE TABLE nums (n INTEGER)",
)
SERIES = "WITH RECURSIVE s(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM s WHERE i < {n}) "

FAULTS: dict[str, dict[str, Any]] = {
    # SQLITE_FULL: the page limit is set a few pages above the current size.
    "full-insert-one-row": {"kind": "full", "sql": "INSERT INTO blobs(data) VALUES (randomblob(262144))"},
    "full-insert-one-row-unique": {"kind": "full", "sql": "INSERT INTO blobs_unique(k, data) VALUES ('k1', randomblob(262144))"},
    "full-insert-select": {"kind": "full", "sql": SERIES.format(n=64) + "INSERT INTO blobs(data) SELECT randomblob(8192) FROM s"},
    "full-insert-select-unique": {"kind": "full", "sql": SERIES.format(n=64) + "INSERT INTO blobs_unique(k, data) SELECT 'k' || i, randomblob(8192) FROM s"},
    "full-update-one-row": {"kind": "full", "sql": "UPDATE blobs SET data = randomblob(262144) WHERE id = 1"},
    # SQLITE_INTERRUPT on a write statement and on a read statement.
    "interrupt-progress-write": {"kind": "progress", "sql": SERIES.format(n=200000) + "INSERT INTO nums SELECT i FROM s"},
    "interrupt-progress-read": {"kind": "progress", "sql": SERIES.format(n=2000000) + "SELECT count(*) FROM s"},
    "interrupt-thread-write": {"kind": "thread", "sql": SERIES.format(n=20000000) + "INSERT INTO nums SELECT i FROM s"},
    # A real write failure under a file-size limit, in a child process.
    "fsize-insert-one-row": {"kind": "fsize", "sql": "INSERT INTO blobs(data) VALUES (randomblob(1048576))"},
    # The rows grow from 4000 to 12000 bytes, so the database must grow past the limit.
    "fsize-update-many": {"kind": "fsize", "sql": "UPDATE blobs SET data = randomblob(12000)"},
}
JOURNALS = ("delete", "wal")


def queries(token: str) -> dict[str, str]:
    return {
        "ledger": f"SELECT step FROM ledger WHERE token = '{token}' ORDER BY id",
        "blob_rows": "SELECT count(*) FROM blobs",
        "nums_rows": "SELECT count(*) FROM nums",
    }


def setup(path: Path, journal: str, preload_blobs: int) -> None:
    conn = sqlite3.connect(str(path), autocommit=True)
    try:
        conn.execute(f"PRAGMA journal_mode={journal}")
        for statement in SCHEMA:
            conn.execute(statement)
        for _ in range(preload_blobs):
            conn.execute("INSERT INTO blobs(data) VALUES (randomblob(4000))")
    finally:
        conn.close()


def run_transaction(path: Path, token: str, fault: str, journal: str) -> dict[str, Any]:
    """The transaction itself. Runs in this process, or in the fsize child."""
    spec = FAULTS[fault]
    conn = sqlite3.connect(str(path), timeout=0.0, autocommit=True)
    trace = common.Trace(conn)
    steps: list[dict[str, Any]] = []
    out: dict[str, Any] = {"steps": steps}

    def step(label: str, fn: Callable[[], Any]) -> dict[str, Any]:
        start = len(trace.events)
        before = conn.in_transaction
        entry = common.call(label, fn)
        entry["in_transaction_before"] = before
        entry["in_transaction_after"] = common.in_transaction(conn)
        entry["sql_started"] = [e["sql"] for e in trace.events[start:]]
        steps.append(entry)
        return entry

    def writer_view() -> dict[str, Any]:
        return {"ledger": [r[0] for r in conn.execute(
            "SELECT step FROM ledger WHERE token = ? ORDER BY id", (token,))]}

    out["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if spec["kind"] == "full":
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        out["page_count_before"] = pages
        out["max_page_count_set"] = conn.execute(f"PRAGMA max_page_count = {pages + 8}").fetchone()[0]
    if spec["kind"] == "fsize":
        out["cache_size_set"] = 4
        conn.execute("PRAGMA cache_size = 4")
    step("begin", lambda: conn.execute("BEGIN").rowcount)
    step("write-a", lambda: conn.execute("INSERT INTO ledger(token, step) VALUES (?, 'A')", (token,)).rowcount)

    if spec["kind"] == "progress":
        calls = {"n": 0}

        def handler() -> int:
            calls["n"] += 1
            return 1 if calls["n"] > 20 else 0  # ask SQLite to stop after 20 callbacks

        conn.set_progress_handler(handler, 1000)
        fault_entry = step("fault", lambda: conn.execute(spec["sql"]).fetchall())
        conn.set_progress_handler(None, 1000)
        out["progress_callbacks"] = calls["n"]
    elif spec["kind"] == "thread":
        timer = threading.Timer(0.2, conn.interrupt)  # another thread asks SQLite to stop
        timer.start()
        started = time.monotonic()
        fault_entry = step("fault", lambda: conn.execute(spec["sql"]).fetchall())
        out["statement_ran_at_least_200ms"] = time.monotonic() - started >= 0.2
        timer.cancel()
    else:
        fault_entry = step("fault", lambda: conn.execute(spec["sql"]).fetchall())

    out["after_fault"] = {"in_transaction": conn.in_transaction, "writer_view": writer_view()}
    step("write-b", lambda: conn.execute("INSERT INTO ledger(token, step) VALUES (?, 'B')", (token,)).rowcount)
    out["after_write_b"] = {"in_transaction": conn.in_transaction}
    step("commit", lambda: conn.execute("COMMIT").rowcount)
    out["after_commit"] = {"in_transaction": conn.in_transaction}
    if conn.in_transaction:
        step("rollback-leftover", lambda: conn.execute("ROLLBACK").rowcount)
    conn.close()
    out["trace"] = trace.statements()
    out["fault"] = fault_entry
    return out


def child_main(args: list[str]) -> None:
    """--child <db> <token> <fault> <journal> <limit-bytes>: run under RLIMIT_FSIZE."""
    db, token, fault, journal, limit = args
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)  # so write() fails with EFBIG instead of killing us
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (int(limit), hard))
    out = run_transaction(Path(db), token, fault, journal)
    out["rlimit_fsize"] = int(limit)
    print(json.dumps(common.jsonable(out)))


def scenario(fault: str, journal: str) -> Callable[[Path, str], dict[str, Any]]:
    spec = FAULTS[fault]

    def run(work: Path, token: str) -> dict[str, Any]:
        path = work / "db.sqlite"
        setup(path, journal, preload_blobs=24 if spec["kind"] == "fsize" else (1 if fault == "full-update-one-row" else 0))
        if spec["kind"] == "fsize":
            sizes = {name: (work / name).stat().st_size for name in os.listdir(work)}
            limit = max(sizes.values()) + 16384  # room for A; not for the fault's writes
            proc = subprocess.run(
                [sys.executable, "-I", __file__, "--child", str(path), token, fault, journal, str(limit)],
                capture_output=True, text=True, timeout=120)
            child: dict[str, Any] = {"returncode": proc.returncode, "stderr_tail": proc.stderr.splitlines()[-3:]}
            try:
                out = json.loads(proc.stdout)
            except json.JSONDecodeError:
                out = {"child_stdout": proc.stdout[-2000:]}
            out["child"] = child
            out["file_sizes_before"] = sizes
        else:
            out = run_transaction(path, token, fault, journal)
        observed_final = common.observe(path, queries(token))
        fault_entry = out.get("fault") or {}
        driver = ((fault_entry.get("error") or {}).get("driver") or {})
        steps = {s["step"]: s for s in out.get("steps", [])}

        def status(name: str) -> Any:
            entry = steps.get(name)
            if entry is None:
                return "not-run"
            if entry["status"] == "ok":
                return "ok"
            d = (entry["error"] or {}).get("driver") or {}
            return {"error": d.get("sqlite_errorname"), "message": d.get("message")}

        observed = {
            "journal_mode": out.get("journal_mode"),
            "fault_error": driver.get("sqlite_errorname") if fault_entry.get("status") == "error" else "no error",
            "fault_error_code": driver.get("sqlite_errorcode"),
            "fault_message": driver.get("message"),
            "in_transaction_after_fault": (out.get("after_fault") or {}).get("in_transaction"),
            "writer_sees_a_after_fault": "A" in ((out.get("after_fault") or {}).get("writer_view") or {}).get("ledger", []),
            "write_b": status("write-b"),
            "write_b_in_transaction_after": (out.get("after_write_b") or {}).get("in_transaction"),
            "commit": status("commit"),
            "persisted_ledger": observed_final.get("ledger"),
            "child_returncode": (out.get("child") or {}).get("returncode"),
        }
        return {"observed": observed, "detail": out, "observer_final": observed_final, "trace": out.get("trace")}

    return run


def main() -> None:
    variants = [
        (f"{fault}.{journal}", scenario(fault, journal))
        for fault in FAULTS
        for journal in JOURNALS
    ]
    common.run_experiment("sqlite05-realistic", variants)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child_main(sys.argv[2:])
    else:
        main()
