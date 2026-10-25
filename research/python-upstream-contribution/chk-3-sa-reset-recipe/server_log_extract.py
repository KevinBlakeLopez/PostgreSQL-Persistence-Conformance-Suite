"""Extract each CHK-3 run's sessions from the server log, and summarize them.

Usage: python -I server_log_extract.py <server.log> <output dir>

The server ran with log_statement=all, log_connections, log_disconnections and
log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '. Sessions are attributed by the
application_name in their "connection authorized" line: chk3-<driver>-<arm>-r<rep> for the
program's engines, and chk3-witness-<driver>-r<rep> for its witness. The setup sessions
(chk3-setup) and psql are not extracted.

For each run this writes:
  server-log.<driver>.rep<rep>.txt          every line of the run's sessions, in log order;
  server-log-summary.<driver>.rep<rep>.txt  per subject session, its statements grouped by
                                            virtual transaction, with the xid logged on each line.
It also prints the xids on ROLLBACK lines inside reset transactions, for a pg_xact_status() check.
It refuses to write anything if an extracted line mentions a password.
"""
import collections, os, re, sys

PREFIX = re.compile(r"^(\S+ \S+) UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) (\w+):  (.*)$")
APP = re.compile(r"application_name=(\S+)")
RUN = re.compile(r"^chk3-(?:witness-)?(psycopg2?)-(?:.*-)?r(\d+)$")

log_path, out_dir = sys.argv[1], sys.argv[2]
entries, pid_app = [], {}  # entries: [pid, first line, continuation lines...]
for raw in open(log_path, encoding="utf-8"):
    line = raw.rstrip("\n")
    m = PREFIX.match(line)
    if m:
        pid, msg = m.group(2), m.group(7)
        if msg.startswith("connection authorized:") and (a := APP.search(msg)):
            pid_app[pid] = a.group(1)
        entries.append([pid, line])
    elif entries:
        entries[-1].append(line)

runs = collections.defaultdict(list)  # (driver, rep) -> entries
for e in entries:
    app = pid_app.get(e[0], "")
    if (m := RUN.match(app)):
        runs[(m.group(1), m.group(2))].append(e)

for e in (e for es in runs.values() for e in es):
    if any(re.search(r"password", l, re.I) for l in e[1:]):
        sys.exit("refusing to write: an extracted line mentions a password")

os.makedirs(out_dir, exist_ok=True)
rollback_xids = []
for (driver, rep), es in sorted(runs.items()):
    with open(os.path.join(out_dir, f"server-log.{driver}.rep{rep}.txt"), "w", encoding="utf-8") as f:
        for e in es:
            f.write("\n".join(e[1:]) + "\n")
    sessions = collections.OrderedDict()
    for e in es:
        m = PREFIX.match(e[1])
        ts, pid, app, vxid, xid, level, msg = m.groups()
        if pid_app[pid].startswith("chk3-witness-") or msg.startswith(("connection received", "connection authenticated")):
            continue
        s = sessions.setdefault(pid, {"app": pid_app[pid], "tx": [], "end": "still connected at the end of the log"})
        if msg.startswith("connection authorized"):
            continue
        if msg.startswith("disconnection:"):
            s["end"] = "disconnected (" + msg.split(": ", 1)[1].split(" user=")[0] + ")"
            continue
        text = re.sub(r"^(statement|execute <unnamed>|execute \S+): ", "", msg) if level == "LOG" else f"{level}: {msg}"
        text = text if len(text) <= 60 else text[:57] + "..."
        if level == "LOG" and msg.startswith("execute ") and not msg.startswith("execute <unnamed>"):
            text = "[" + msg.split(":", 1)[0] + "] " + text
        if not s["tx"] or s["tx"][-1][0] != vxid:
            s["tx"].append((vxid, []))
        s["tx"][-1][1].append(text + (f" [xid {xid}]" if xid != "0" else ""))
    with open(os.path.join(out_dir, f"server-log-summary.{driver}.rep{rep}.txt"), "w", encoding="utf-8") as f:
        for pid, s in sessions.items():
            arm = s["app"][len(f"chk3-{driver}-"):-len(f"-r{rep}")]
            f.write(f"{arm} (backend {pid}):\n")
            for vxid, stmts in s["tx"]:
                f.write(f"  vxid {vxid}: " + " | ".join(stmts) + "\n")
                if stmts and stmts[-1].startswith("ROLLBACK [xid") and any(
                        x.startswith(("CLOSE ALL", "RESET ALL", "DISCARD")) for x in stmts):
                    rollback_xids.append(stmts[-1].split("[xid ")[1].rstrip("]"))
            f.write(f"  {s['end']}\n")
print("xids on ROLLBACK lines of reset transactions:", " ".join(rollback_xids))
