"""CHK-9: does a real SQLITE_BUSY at COMMIT reach SQLAlchemy's P5a path?

A writer inserts a row, a reader in another process holds a read transaction,
and the writer's COMMIT times out with "database is locked". SQLite documents
that the transaction then stays active. Nothing is injected.

Usage: python -I chk9.py <output dir> [repetitions] [main|rollback]
Writes cases.jsonl and summary.json to <output dir>. The "rollback" set adds an
explicit rollback() after the failed commit(), before close().
"""

import json
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

import sqlalchemy
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]).resolve()
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
CASE_SET = sys.argv[3] if len(sys.argv) > 3 else "main"
DBDIR = OUT / "db"
DBDIR.mkdir(parents=True, exist_ok=True)

item = Table("item", MetaData(), Column("id", Integer, primary_key=True), Column("note", String))


def describe(e):
    return f"{type(e).__module__}.{type(e).__name__}: {str(e).splitlines()[0]}"


def fresh_db(name, wal):
    path = DBDIR / f"{name}.db"
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    c = sqlite3.connect(path)
    c.execute("create table item (id integer primary key, note text)")
    mode = c.execute("pragma journal_mode=wal" if wal else "pragma journal_mode").fetchone()[0]
    c.commit()
    c.close()
    return path, mode


class Reader:
    """A read transaction in another process, holding SQLite's SHARED lock."""

    def __init__(self, path, enabled):
        self.path, self.enabled, self.proc = path, enabled, None

    def start(self):
        if not self.enabled:
            return None
        self.proc = subprocess.Popen(
            [sys.executable, "-I", str(HERE / "reader.py"), str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        )
        line = self.proc.stdout.readline().strip()
        assert line.startswith("READY"), line
        return line

    def release(self):
        if self.proc is None:
            return None
        self.proc.stdin.write("\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().strip()
        self.proc.wait(timeout=10)
        return line


def make_engine(path, config, timeout):
    connect_args = {} if timeout is None else {"timeout": timeout}
    if config == "autocommit-false":
        connect_args["autocommit"] = False
    engine = create_engine(f"sqlite:///{path}", connect_args=connect_args)
    if config == "begin-recipe":
        # The SQLite dialect documentation's recipe for SQLAlchemy-controlled BEGIN.
        @event.listens_for(engine, "connect")
        def _connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _begin(conn):
            conn.exec_driver_sql("BEGIN")

    return engine


def instrument(engine, log):
    """Record pool resets and DBAPI rollbacks without changing either."""

    @event.listens_for(engine, "reset")
    def _reset(dbapi_connection, connection_record, reset_state):
        log.append({
            "event": "pool-reset",
            "transaction_was_reset": reset_state.transaction_was_reset,
            "terminate_only": reset_state.terminate_only,
            "dbapi_in_transaction": dbapi_connection.in_transaction,
        })

    do_rollback = engine.dialect.do_rollback

    def counted_rollback(dbapi_connection):
        log.append({"event": "dbapi-rollback", "in_transaction_before": dbapi_connection.in_transaction})
        return do_rollback(dbapi_connection)

    engine.dialect.do_rollback = counted_rollback


def probe(path):
    """Can an independent connection write, or read, right now?"""
    out = {}
    c = sqlite3.connect(path, isolation_level=None, timeout=0.1)
    for kind, statements in (("write", ["BEGIN IMMEDIATE"]), ("read", ["BEGIN", "SELECT count(*) FROM item"])):
        try:
            for s in statements:
                c.execute(s).fetchall()
            out[kind] = "ok"
        except sqlite3.OperationalError as e:
            out[kind] = str(e)
        finally:
            if c.in_transaction:
                c.execute("ROLLBACK")
    c.close()
    return out


def committed_rows(path):
    c = sqlite3.connect(path)
    rows = [f"{i}:{n}" for i, n in c.execute("select id, note from item order by id")]
    c.close()
    return rows


def unit_core(engine, reader):
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        conn.execute(item.insert().values(id=1, note="doomed"))
        reader_line = reader.start()
        try:
            conn.commit()
            commit = "resolved"
        except Exception as e:
            commit = describe(e)
        after = {
            "dbapi_in_transaction": dbapi.in_transaction,
            "sa_in_transaction": conn.in_transaction(),
            "sa_transaction_marker_present": conn.get_transaction() is not None,
        }
    return commit, after, dbapi, reader_line


def unit_session(engine, reader):
    with Session(engine) as session:
        session.execute(item.insert().values(id=1, note="doomed"))
        dbapi = session.connection().connection.dbapi_connection
        reader_line = reader.start()
        try:
            session.commit()
            commit = "resolved"
        except Exception as e:
            commit = describe(e)
        after = {"dbapi_in_transaction": dbapi.in_transaction}
    return commit, after, dbapi, reader_line


def unit_engine_begin(engine, reader):
    dbapi, reader_line = None, None
    try:
        with engine.begin() as conn:
            dbapi = conn.connection.dbapi_connection
            conn.execute(item.insert().values(id=1, note="doomed"))
            reader_line = reader.start()
        commit = "resolved"
    except Exception as e:
        commit = describe(e)
    after = {"dbapi_in_transaction": dbapi.in_transaction if dbapi is not None else None}
    return commit, after, dbapi, reader_line


def unit_core_rollback(engine, reader):
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        conn.execute(item.insert().values(id=1, note="doomed"))
        reader_line = reader.start()
        rollback = None
        try:
            conn.commit()
            commit = "resolved"
        except Exception as e:
            commit = describe(e)
            try:
                conn.rollback()
                rollback = "resolved"
            except Exception as e2:
                rollback = describe(e2)
        after = {"explicit_rollback": rollback, "dbapi_in_transaction": dbapi.in_transaction}
    return commit, after, dbapi, reader_line


def unit_session_rollback(engine, reader):
    with Session(engine) as session:
        session.execute(item.insert().values(id=1, note="doomed"))
        dbapi = session.connection().connection.dbapi_connection
        reader_line = reader.start()
        rollback = None
        try:
            session.commit()
            commit = "resolved"
        except Exception as e:
            commit = describe(e)
            try:
                session.rollback()
                rollback = "resolved"
            except Exception as e2:
                rollback = describe(e2)
        after = {"explicit_rollback": rollback, "dbapi_in_transaction": dbapi.in_transaction}
    return commit, after, dbapi, reader_line


FLOWS = {
    "core": unit_core,
    "session": unit_session,
    "engine.begin": unit_engine_begin,
    "core+rollback": unit_core_rollback,
    "session+rollback": unit_session_rollback,
}

MAIN_CASES = [
    {"config": c, "flow": f, "reader": True, "wal": False, "timeout": 0.2}
    for c in ("default", "begin-recipe", "autocommit-false")
    for f in ("core", "session", "engine.begin")
] + [
    {"config": "default", "flow": "core", "reader": True, "wal": False, "timeout": None, "note": "sqlite3's default 5 s busy timeout"},
    {"config": "default", "flow": "core", "reader": False, "wal": False, "timeout": 0.2, "note": "control: no reader"},
    {"config": "default", "flow": "core", "reader": True, "wal": True, "timeout": 0.2, "note": "control: WAL"},
]

ROLLBACK_CASES = [
    {"config": c, "flow": f, "reader": True, "wal": False, "timeout": 0.2}
    for c in ("default", "autocommit-false")
    for f in ("core+rollback", "session+rollback")
]

CASES = {"main": MAIN_CASES, "rollback": ROLLBACK_CASES}[CASE_SET]


def run_case(case, rep):
    name = f"{case['config']}-{case['flow']}-{'reader' if case['reader'] else 'noreader'}-{'wal' if case['wal'] else 'delete'}-{case['timeout']}-r{rep}"
    path, journal_mode = fresh_db(name.replace(".", "_"), case["wal"])
    engine = make_engine(path, case["config"], case["timeout"])
    log = []
    instrument(engine, log)
    reader = Reader(path, case["reader"])
    rec = {**case, "rep": rep, "journal_mode": journal_mode}
    commit, after, dbapi, reader_line = FLOWS[case["flow"]](engine, reader)
    rec.update({"reader": reader_line, "commit": commit, "after_commit": after, "events_through_close": list(log)})
    rec["probe_while_reader_holds"] = probe(path) if case["reader"] else None
    rec["reader_released"] = reader.release()
    rec["probe_after_reader_released"] = probe(path)
    log.clear()
    with engine.connect() as conn:
        dbapi2 = conn.connection.dbapi_connection
        rec["next_checkout"] = {"same_dbapi_connection": dbapi2 is dbapi, "dbapi_in_transaction_at_checkout": dbapi2.in_transaction}
        try:
            conn.execute(item.insert().values(id=2, note="next"))
            conn.commit()
            rec["next_checkout"]["commit"] = "resolved"
        except Exception as e:
            rec["next_checkout"]["commit"] = describe(e)
    rec["events_next_unit"] = list(log)
    engine.dispose()
    rec["committed_rows"] = committed_rows(path)
    failed = rec["commit"] != "resolved"
    rec["verdict"] = (
        "P5a: commit() raised, and the next checkout committed the doomed row"
        if failed and "1:doomed" in rec["committed_rows"]
        else "commit() raised; the doomed row did not commit" if failed
        else "commit() resolved"
    )
    return rec


def main():
    env = {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "sqlalchemy": sqlalchemy.__version__,
        "platform": platform.platform(),
        "reps": REPS,
        "case_set": CASE_SET,
    }
    results = []
    with open(OUT / "cases.jsonl", "w") as f:
        for case in CASES:
            for rep in range(1, REPS + 1):
                rec = run_case(case, rep)
                results.append(rec)
                f.write(json.dumps(rec) + "\n")
    summary = []
    for case in CASES:
        reps = [r for r in results if all(r[k] == case[k] for k in ("config", "flow", "wal", "timeout")) and (r["reader"] is not None) == case["reader"]]
        stable = {json.dumps({k: v for k, v in r.items() if k != "rep"}, sort_keys=True) for r in reps}
        summary.append({**case, "reps": len(reps), "reps_agree": len(stable) == 1, "verdict": reps[0]["verdict"], "commit": reps[0]["commit"]})
    (OUT / "summary.json").write_text(json.dumps({"environment": env, "summary": summary}, indent=1))
    print(json.dumps(env))
    for s in summary:
        print(f"{s['config']:17} {s['flow']:13} reader={s['reader']!s:5} wal={s['wal']!s:5} timeout={s['timeout']!s:4} agree={s['reps_agree']!s:5} {s['verdict']}")


if __name__ == "__main__":
    main()
