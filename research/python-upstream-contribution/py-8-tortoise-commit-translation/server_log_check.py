"""CHK-only. Server-log extraction and cross-checks for the PY-8 runs.

    python server_log_check.py extract <full server log> <extract file>
    python server_log_check.py query <evidence dir>
    python server_log_check.py transcripts <extract file>
    python server_log_check.py check <evidence dir> <psql output> <extract file>

The server ran with log_statement=all and
log_line_prefix='%m [%p] app=%a vxid=%v xid=%x sqlstate=%e '.

- extract: keeps every entry, with its continuation lines, of the subject sessions. These
  are the sessions whose application_name starts with py8-repro-, py8-nested-,
  py8-after-, py8-uoc- or py8-reuse-, plus py8-competitor. Sessions are attributed by PID
  from their "connection authorized" line, until their "disconnection" line.
- query: prints a psql query for pg_xact_status() of every transaction ID that the
  outputs print as "pg_xact_status(<xid>): <fate>".
- transcripts: prints, per run, each session's statements grouped by virtual transaction
  ID, with the SQLSTATE of any error. asyncpg statement names are masked, and the
  repetitions of a run are compared.
- check: compares the printed fates with psql's, and with how each transaction ended in
  the log.
"""

import collections
import glob
import os
import re
import sys

ENTRY = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} UTC) \[(?P<pid>\d+)\] app=(?P<app>\S*) "
    r"vxid=(?P<vxid>\S*) xid=(?P<xid>\d+) sqlstate=(?P<sqlstate>\w{5}) (?P<level>[A-Z]+):  (?P<msg>.*)$"
)
SUBJECT = re.compile(r"^py8-(repro|nested|after|uoc|reuse)-|^py8-competitor$")
FATE = re.compile(r"pg_xact_status\((\d+)\): (\w+)")


def entries(path):
    """Log entries, each a dict with its continuation lines folded into 'text'."""
    current = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = ENTRY.match(line)
            if m:
                if current:
                    yield current
                current = dict(m.groupdict(), raw=[line], text=m.group("msg"))
            elif current is not None:
                current["raw"].append(line)
                current["text"] += "\n" + line
    if current:
        yield current


def extract(full, out):
    live = {}  # pid -> application_name of the session that holds it
    kept = 0
    with open(out, "w", encoding="utf-8") as fh:
        for e in entries(full):
            pid = e["pid"]
            m = re.search(r"connection authorized: .*application_name=(\S+)", e["msg"])
            if m:
                live[pid] = m.group(1)
            app = live.get(pid)
            if app and SUBJECT.search(app):
                fh.write("\n".join(e["raw"]) + "\n")
                kept += 1
            if e["msg"].startswith("disconnection:"):
                live.pop(pid, None)
    print(f"kept {kept} entries")


def printed_fates(root):
    fates = {}
    for f in sorted(glob.glob(f"{root}/output/**/*.out", recursive=True)):
        for xid, fate in FATE.findall(open(f, encoding="utf-8").read()):
            fates.setdefault(xid, set()).add((fate, os.path.relpath(f, root)))
    return fates


def query(root):
    xids = sorted(printed_fates(root), key=int)
    values = ",".join(f"({x})" for x in xids)
    print(f"SELECT x AS xid, pg_xact_status(x::text::xid8) AS fate FROM (VALUES {values}) AS t(x) ORDER BY x;")


def normalize(sql):
    """Collapse whitespace, mask asyncpg statement names, and sort a SELECT's column list.

    Tortoise builds the column list of a model SELECT in an order that varies between
    processes, so the list is sorted before runs are compared.
    """
    sql = " ".join(sql.split())
    sql = re.sub(r"__asyncpg_stmt_[0-9a-f]+__", "__asyncpg_stmt__", sql)
    sql = re.sub(
        r'^SELECT ((?:"\w+",)*"\w+") FROM',
        lambda m: "SELECT " + ",".join(sorted(m.group(1).split(","))) + " FROM",
        sql,
    )
    return sql


def sessions(extract_path):
    """Sessions in order of their first entry: app, pid, and (vxid, item, sqlstate, xid) items.

    After an error aborts a top-level transaction, PostgreSQL 18 logs the statements that
    follow it, up to the ROLLBACK, with a vxid of <backend>/0. Those entries are kept with
    the session's current transaction.
    """
    out, open_by_pid = [], {}
    for e in entries(extract_path):
        pid, msg = e["pid"], e["msg"]
        m = re.search(r"connection authorized: .*application_name=(\S+)", msg)
        if m:
            s = {"app": m.group(1), "pid": pid, "items": [], "vxid": ""}
            out.append(s)
            open_by_pid[pid] = s
            continue
        s = open_by_pid.get(pid)
        if s is None:
            continue
        if msg.startswith("disconnection:"):
            s["items"].append(("", "disconnection", "00000", e["xid"]))
            open_by_pid.pop(pid)
            continue
        vxid = e["vxid"]
        if vxid.endswith("/0"):
            vxid = s["vxid"]
        else:
            s["vxid"] = vxid
        m = re.match(r"(?:statement|execute [^:]+): (.*)", e["text"], re.S)
        if e["level"] == "LOG" and m:
            s["items"].append((vxid, normalize(m.group(1)), "00000", e["xid"]))
        elif e["level"] in ("ERROR", "FATAL"):
            s["items"].append((vxid, f"{e['level']} {e['sqlstate']}", e["sqlstate"], e["xid"]))
    return out


def run_key(app):
    """The run a session belongs to, and the name its repetitions share."""
    m = re.match(r"^(py8-.*)-r(?:dev|rel)?([123])$", app)
    return (app, re.sub(r"-r(dev|rel)?[123]$", "", app)) if m else (app, app)


def transcript(session_list):
    lines = []
    for n, s in enumerate(session_list, 1):
        lines.append(f"  session {n}")
        groups = collections.OrderedDict()
        for vxid, item, _, _ in s["items"]:
            groups.setdefault(vxid or "-", []).append(item)
        for t, (vxid, items) in enumerate(groups.items(), 1):
            label = "end" if vxid == "-" else f"tx {t}"
            lines.append(f"    {label}: " + " | ".join(items))
    return lines


def transcripts(extract_path):
    by_run = collections.OrderedDict()
    for s in sessions(extract_path):
        if s["app"] == "py8-competitor":
            continue
        app, _ = run_key(s["app"])
        by_run.setdefault(app, []).append(s)
    by_shared = collections.OrderedDict()
    for app, sess in by_run.items():
        by_shared.setdefault(run_key(app)[1], []).append((app, transcript(sess)))
    for shared, reps in by_shared.items():
        first = reps[0][1]
        same = all(t == first for _, t in reps[1:])
        print(f"{shared}: {len(reps)} runs; " + ("identical transcripts" if same else "TRANSCRIPTS DIFFER"))
        for line in first:
            print(line)
        if not same:
            for app, t in reps[1:]:
                if t != first:
                    print(f"  differs: {app}")
                    for line in t:
                        print(line)


def tx_ending(session_list, xid):
    """How the transaction that carried xid ended in the log."""
    for s in session_list:
        items = s["items"]
        idx = [i for i, it in enumerate(items) if it[3] == xid]
        if not idx:
            continue
        vxid = items[idx[0]][0]
        tx = [it for it in items if it[0] == vxid]
        rest = items[items.index(tx[-1]) + 1:]
        last_stmt = [it for it in tx if not it[1].startswith(("ERROR", "FATAL"))][-1][1]
        errors = [it[2] for it in tx if it[1].startswith("ERROR")]
        last = tx[-1][1]
        if last.startswith("COMMIT") and not errors:
            return "committed", f"{last}", s["app"]
        if last.startswith("ERROR") and last_stmt.startswith("COMMIT"):
            return "aborted", f"{last_stmt} -> {last}", s["app"]
        if last.startswith("ROLLBACK"):
            return "aborted", f"{last}" + (f" (after errors {','.join(errors)})" if errors else ""), s["app"]
        if rest and rest[0][1] == "disconnection":
            return "aborted", "session ended without COMMIT or ROLLBACK", s["app"]
        return "unknown", f"last item {last}", s["app"]
    return None, "not found in the extract", None


def check(root, psql_path, extract_path):
    printed = printed_fates(root)
    psql = dict(re.findall(r"^\s*(\d+)\s*\|\s*(\w+)", open(psql_path).read(), re.M))
    sess = sessions(extract_path)
    problems = 0
    counts = collections.Counter()
    for xid in sorted(printed, key=int):
        fates = {f for f, _ in printed[xid]}
        files = sorted({p for _, p in printed[xid]})
        log_fate, how, app = tx_ending(sess, xid)
        ok = len(fates) == 1 and psql.get(xid) in fates and log_fate in fates
        problems += not ok
        counts[(next(iter(fates)) if len(fates) == 1 else "?", how)] += 1
        if not ok:
            print(f"PROBLEM xid {xid}: printed {fates} in {files}; psql {psql.get(xid)}; log {log_fate} ({how}, {app})")
    print(f"{len(printed)} printed transaction IDs; {len(psql)} psql rows; problems: {problems}")
    print("printed fate, and how the transaction ended in the log:")
    for (fate, how), n in sorted(counts.items()):
        print(f"  {n:4}  {fate:10} {how}")
    return problems


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "extract" and len(sys.argv) == 4:
        extract(sys.argv[2], sys.argv[3])
    elif cmd == "query" and len(sys.argv) == 3:
        query(sys.argv[2])
    elif cmd == "transcripts" and len(sys.argv) == 3:
        transcripts(sys.argv[2])
    elif cmd == "check" and len(sys.argv) == 5:
        sys.exit(1 if check(sys.argv[2], sys.argv[3], sys.argv[4]) else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
