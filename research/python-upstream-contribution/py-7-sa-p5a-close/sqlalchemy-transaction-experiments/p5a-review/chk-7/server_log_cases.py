"""Summarize each run of check/p5a_close_v2.py from the server's statement log.

Usage: python -I server_log_cases.py <server.log>

The server ran with log_statement=all, log_connections, log_disconnections and
log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '. A run starts when a backend sends
`drop table if exists p5a`; that backend is the script's witness. Every other backend
until the next run is a subject backend. For each subject backend this prints its
statements grouped by virtual transaction ID, with the xid logged on each line, and
whether it disconnected. The xids on COMMIT lines are printed last, for a pg_xact_status() check.
"""
import re, sys

LINE = re.compile(r"^(\S+ \S+) UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) LOG:  (.*)$")

runs, current, commits, psql = [], None, [], set()
for raw in open(sys.argv[1], encoding="utf-8"):
    m = LINE.match(raw.rstrip("\n"))
    if not m:
        continue
    ts, pid, app, vxid, xid, msg = m.groups()
    # psql sessions (the setup, and the pg_xact_status check after the runs) are not the script's
    if msg.startswith("connection authorized") and "application_name=psql" in msg:
        psql.add(pid)
    if pid in psql:
        continue
    if msg == "statement: drop table if exists p5a":
        # the next run's witness connected, and initialised, before this line
        if current is not None:
            current["backends"].pop(pid, None)
        current = {"witness": pid, "backends": {}}
        runs.append(current)
        continue
    if current is None or pid == current["witness"]:
        continue
    if msg.startswith(("connection received", "connection authenticated", "connection authorized")):
        continue
    b = current["backends"].setdefault(pid, {"tx": [], "end": None})
    if msg.startswith("disconnection:"):
        b["end"] = f"disconnected at {ts}"
        continue
    text = re.sub(r"^(statement|execute <unnamed>): ", "", msg)
    text = text.replace("insert into p5a (code) values ", "insert ")
    if not b["tx"] or b["tx"][-1][0] != vxid:
        b["tx"].append((vxid, []))
    b["tx"][-1][1].append(text + (f" [xid {xid}]" if xid != "0" else ""))
    if text == "COMMIT" and xid != "0":
        commits.append(xid)

for n, run in enumerate(runs, 1):
    print(f"run {n}: witness backend {run['witness']}")
    for pid, b in run["backends"].items():
        print(f"  subject backend {pid}:")
        for vxid, stmts in b["tx"]:
            print(f"    vxid {vxid}: " + " | ".join(stmts))
        print(f"    {b['end'] or 'still connected at the end of the log'}")
print("xids on subject COMMIT lines:", " ".join(commits))
