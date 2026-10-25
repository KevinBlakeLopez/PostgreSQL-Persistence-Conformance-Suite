"""Summarize the demo's sessions from the demo server's statement log.

Usage: python -I demo_server_log.py <server.log>

The demo sets no application_name, so its sessions are found by login: every session of
user app_login, in log order. For each it prints the statements grouped by virtual transaction
ID, with the xid logged on each line, and how the session ended. It refuses to print a line that
mentions a password.
"""
import collections, re, sys

PREFIX = re.compile(r"^(\S+ \S+) UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) (\w+):  (.*)$")
sessions = collections.OrderedDict()
for raw in open(sys.argv[1], encoding="utf-8"):
    m = PREFIX.match(raw.rstrip("\n"))
    if not m:
        continue
    ts, pid, app, vxid, xid, level, msg = m.groups()
    if re.search(r"password", msg, re.I):
        sys.exit("refusing: a log line mentions a password")
    if msg.startswith("connection authorized:"):
        if "user=app_login" in msg and "application_name=psql" not in msg:
            sessions[pid] = {"tx": [], "end": "still connected"}
        continue
    if pid not in sessions or msg.startswith(("connection received", "connection authenticated")):
        continue
    s = sessions[pid]
    if msg.startswith("disconnection:"):
        s["end"] = "disconnected"
        continue
    text = re.sub(r"^(statement|execute <unnamed>): ", "", msg) if level == "LOG" else f"{level}: {msg}"
    text = text if len(text) <= 50 else text[:47] + "..."
    if not s["tx"] or s["tx"][-1][0] != vxid:
        s["tx"].append((vxid, []))
    s["tx"][-1][1].append(text + (f" [xid {xid}]" if xid != "0" else ""))

for n, (pid, s) in enumerate(sessions.items(), 1):
    print(f"session {n} (backend {pid}):")
    for vxid, stmts in s["tx"]:
        print(f"  vxid {vxid}: " + " | ".join(stmts))
    print(f"  {s['end']}")
