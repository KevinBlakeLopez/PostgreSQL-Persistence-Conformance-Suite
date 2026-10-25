"""Runner for the Uvicorn graceful-shutdown check (P8).

Question: when Uvicorn's graceful-shutdown timeout expires while a request's COMMIT is in
flight, what does PostgreSQL finally do, and does SQLAlchemy's after_rollback fire before the
process exits?

One run:
  1. A fresh database, with the P3 commit gate: a DEFERRABLE INITIALLY DEFERRED constraint
     trigger that runs pg_advisory_xact_lock(777). This runner holds pg_advisory_lock(777) in
     the same database, so the request's COMMIT waits.
  2. Uvicorn 0.54.0 serves chk_app with --timeout-graceful-shutdown 1. One HTTP request starts
     an AsyncSession transaction that inserts a gated row.
  3. Once pg_stat_activity shows that backend active in COMMIT and waiting on the advisory
     lock, the runner sends SIGTERM or SIGINT to Uvicorn.
     Control mode TERM-in-time instead releases the gate 0.3 s after SIGTERM, within the 1 s
     graceful window.
  4. The runner waits for the process to exit, then records the backend and pg_xact_status.
  5. It releases the gate, waits for the backend, and records the final fate and the marker.
The app's event log (written with os.write) shows which SQLAlchemy events fired before exit.
Usage: run_uvicorn_check.py <asyncpg|psycopg> <TERM|INT|TERM-in-time> <rep> <http-port>
"""
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PGPORT = 55493
assert PGPORT == 55493
CONTAINER = "ppcs-gap-uvicorn-pg"
GATE = 777


def dsn(db):
    return f"postgresql://postgres:{PW}@127.0.0.1:{PGPORT}/{db}"


def q(db, sql, args=()):
    with psycopg.connect(dsn(db), autocommit=True) as c:
        cur = c.execute(sql, args) if args else c.execute(sql)
        return cur.fetchall() if cur.description else []


def backend(db, pid):
    rows = q(db, "select state, wait_event_type, wait_event, query from pg_stat_activity where pid = %s", (pid,))
    if not rows:
        return "gone"
    s, wet, we, query = rows[0]
    return f"{s} / {wet}:{we} / {query.strip()[:30]}"


def server_log(since_iso, pid):
    out = subprocess.run(["docker", "logs", "--since", since_iso, CONTAINER], capture_output=True, text=True,
                         env={**os.environ, "DOCKER_CONTEXT": "colima"})
    lines = (out.stdout + out.stderr).splitlines()
    keep = []
    for line in lines:
        if f"[{pid}]" in line and ("statement:" in line or "ERROR" in line or "FATAL" in line
                                   or "LOG:  could not" in line or "unexpected EOF" in line or "DETAIL" in line):
            keep.append(line.split(" UTC ", 1)[-1][:200])
    return keep


def main(driver, mode, rep, port):
    tag = f"{driver}-{mode}-{rep}".lower()
    db = "chkuv_" + tag.replace("-", "_")
    appname = f"chkuv-{tag}"
    marker = f"slow-{tag}"
    evlog = os.path.join(HERE, "events", f"{tag}.jsonl")
    os.makedirs(os.path.dirname(evlog), exist_ok=True)
    if os.path.exists(evlog):
        os.remove(evlog)

    q("postgres", f"drop database if exists {db} with (force)")
    q("postgres", f"create database {db}")
    q(db, """create table item (id serial primary key, name text not null);
             create function gate() returns trigger language plpgsql as
               $$ begin perform pg_advisory_xact_lock(777); return null; end $$;
             create constraint trigger gate after insert on item deferrable initially deferred
               for each row when (new.name like 'slow%') execute function gate();""")
    gate = psycopg.connect(dsn(db), autocommit=True)
    gate.execute("select pg_advisory_lock(%s)", (GATE,))

    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8",
           "CHK_DSN": dsn(db).replace("postgresql://", f"postgresql+{driver}://"), "CHK_DRIVER": driver,
           "CHK_MARKER": marker, "CHK_APPNAME": appname, "CHK_EVENT_LOG": evlog}
    cmd = [sys.executable, "-I", "-B", "-m", "uvicorn", "--app-dir", HERE, "chk_app:app",
           "--host", "127.0.0.1", "--port", str(port), "--timeout-graceful-shutdown", "1",
           "--lifespan", "on", "--log-level", "info"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=HERE,
                            text=True, bufsize=1)
    lines = []

    def reader():
        for line in proc.stdout:
            lines.append((time.time(), line.rstrip("\n")))

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.time() + 15
    while time.time() < deadline and not any("Application startup complete" in l for _, l in lines):
        time.sleep(0.02)

    client = {}

    def http():
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=60)
            s.sendall(b"GET /work HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            client["ended"] = "EOF"
            client["status_line"] = data.split(b"\r\n", 1)[0].decode(errors="replace") if data else "(no response bytes)"
        except Exception as e:  # noqa
            client["ended"] = f"{type(e).__name__}"
        client["t"] = time.time()

    threading.Thread(target=http, daemon=True).start()

    gated = None
    deadline = time.time() + 10
    while time.time() < deadline and gated is None:
        for pid, bxid, state, we, query in q(db, "select pid, backend_xid::text, state, wait_event, query"
                                              " from pg_stat_activity where application_name = %s", (appname,)):
            if state == "active" and we == "advisory" and query.strip().rstrip(";").upper() == "COMMIT":
                gated = {"pid": pid, "backend_xid": bxid, "t": time.time()}
        if gated is None:
            time.sleep(0.02)

    result = {"driver": driver, "mode": mode, "rep": rep, "gated": gated is not None}
    t_signal = time.time()
    gate_released = None
    if gated is not None:
        if mode == "INT":
            proc.send_signal(signal.SIGINT)
        else:
            proc.send_signal(signal.SIGTERM)
        if mode == "TERM-in-time":
            time.sleep(0.3)
            gate.execute("select pg_advisory_unlock(%s)", (GATE,))
            gate_released = time.time()
    try:
        rc = proc.wait(timeout=20)
        result["process"] = {"exited": True, "returncode": rc}
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = proc.wait()
        result["process"] = {"exited": False, "returncode": rc, "note": "killed after 20 s"}
    t_exit = time.time()
    time.sleep(0.2)

    events = []
    if os.path.exists(evlog):
        events = [json.loads(l) for l in open(evlog) if l.strip()]
    xid = next((e["xid"] for e in events if e["ev"] == "request.in_transaction"), None)
    pid = gated["pid"] if gated else next((e["pid"] for e in events if e["ev"] == "request.in_transaction"), None)
    if gated is not None and xid is not None:
        result["xid_matches_backend_xid"] = str(int(xid) & 0xFFFFFFFF) == gated["backend_xid"]
        result["at_process_exit"] = {"fate": q(db, "select pg_xact_status(%s::xid8)", (xid,))[0][0],
                                     "backend": backend(db, pid)}
    if gate_released is None:
        gate.execute("select pg_advisory_unlock_all()")
        gate_released = time.time()
    for _ in range(250):
        if pid is None or backend(db, pid) == "gone" or ":advisory" not in backend(db, pid):
            break
        time.sleep(0.02)
    time.sleep(0.3)
    if xid is not None:
        result["final"] = {"fate": q(db, "select pg_xact_status(%s::xid8)", (xid,))[0][0],
                           "marker_visible": bool(q(db, "select 1 from item where name = %s", (marker,))),
                           "backend": backend(db, pid)}
    gate.close()

    def rel(t):
        return round(t - t_signal, 3)

    result["timeline_s_from_signal"] = {
        "events": [f"{rel(e['t']):+.3f} {e['ev']}" + (f" ({e['err']})" if "err" in e else "") for e in events],
        "uvicorn_log": [f"{rel(t):+.3f} {l[:110]}" for t, l in lines if not l.startswith("INFO:     127.0.0.1")],
        "gate_released": rel(gate_released),
        "process_exit_observed": rel(t_exit),
        "client": {**{k: v for k, v in client.items() if k != "t"}, "at": rel(client["t"]) if "t" in client else None},
    }
    names = [e["ev"] for e in events]
    result["fired_before_exit"] = {n: (n in names) for n in ("orm.after_rollback", "orm.after_soft_rollback",
                                                             "orm.after_commit", "core.rollback", "pool.invalidate",
                                                             "request.finally", "lifespan.shutdown.complete")}
    result["request_raised"] = next((e.get("err") for e in events if e["ev"] == "request.raised"), None)
    if pid is not None:
        result["server_log"] = server_log(since, pid)
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
