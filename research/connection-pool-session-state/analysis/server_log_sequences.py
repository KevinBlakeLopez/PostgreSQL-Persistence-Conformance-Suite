"""Reads this investigation's PostgreSQL statement log and prints, for each backend of the selected applications,
its statements grouped into transactions by virtual transaction ID (log_line_prefix %v).

The output masks PIDs, timestamps, virtual transaction IDs and transaction IDs: transactions are numbered T1, T2, ...
in order of first appearance per backend, and a statement that already carries a transaction ID is marked [xid].
Repetitions of one scenario should therefore print identical blocks, which the summary checks.

PostgreSQL 18 logs the statements after an error in an aborted top-level transaction with vxid <backend>/0; those
lines are attached to the backend's current transaction.

The probes' own observation connections (application names ending in -observer or -competitor) are skipped: they
are evidence channels, not borrowers.

Usage: python -I server_log_sequences.py <server-log> <application_name-prefix> [...]
"""

import re
import sys
from collections import OrderedDict, defaultdict

LINE = re.compile(
    r"^\S+ \S+ \S+ \[(?P<pid>\d+)\] app=(?P<app>\S*) vxid=(?P<vxid>\S+) xid=(?P<xid>\d+) sqlstate=(?P<state>\w+) "
    r"(?P<level>[A-Z]+):\s+(?P<msg>.*)$"
)
STATEMENT = re.compile(r"^(?:statement|execute [^:]+|parse [^:]+|bind [^:]+): ?(?P<sql>.*)$")


def main():
    log_path, prefixes = sys.argv[1], sys.argv[2:]
    backends = OrderedDict()   # (app, pid) -> list of (txn, text)
    current = {}
    for raw in open(log_path, encoding="utf-8", errors="replace"):
        m = LINE.match(raw.rstrip("\n"))
        if not m or not any(m["app"].startswith(p) for p in prefixes):
            continue
        if m["app"].endswith(("-observer", "-competitor")):
            continue
        key = (m["app"], m["pid"])
        msg = m["msg"]
        if m["level"] == "LOG":
            s = STATEMENT.match(msg)
            if not s:
                continue
            text = s["sql"].strip() or "<empty query>"
        elif m["level"] in ("ERROR", "WARNING", "FATAL"):
            text = f"{m['level']} {m['state']}"
        else:
            continue
        vxid = m["vxid"]
        if vxid.endswith("/0") and key in current:
            vxid = current[key]
        current[key] = vxid
        if m["xid"] != "0" and m["level"] == "LOG":
            text = "[xid] " + text
        backends.setdefault(key, []).append((vxid, text))

    by_app = defaultdict(list)
    for (app, pid), entries in backends.items():
        numbering = OrderedDict()
        for vxid, _ in entries:
            numbering.setdefault(vxid, f"T{len(numbering) + 1}")
        lines = []
        for txn in numbering.values():
            stmts = [text for vxid, text in entries if numbering[vxid] == txn]
            lines.append(f"  {txn}: " + " | ".join(stmts))
        by_app[app].append("\n".join(lines))

    for app, blocks in by_app.items():
        distinct = list(OrderedDict.fromkeys(blocks))
        print(f"== {app}: {len(blocks)} backend(s), {len(distinct)} distinct sequence(s)")
        for i, block in enumerate(distinct, 1):
            count = blocks.count(block)
            print(f" sequence {i} (seen on {count} backend(s)):")
            print(block)


if __name__ == "__main__":
    main()
