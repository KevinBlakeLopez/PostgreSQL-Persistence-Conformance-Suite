"""Cross-check the server log, the program outputs and the psql fates.

    python -I log_check.py output

For every subject session in output/server.log (application_name chk12-<arm>), prints
the transaction-control statements it sent, the SQLSTATEs of the errors the server raised
(logged by %e), and its transaction ID. Matches each session to the run and arm whose
output printed that ID, and to the ID's fate in output/psql-xact-status.txt.

The server log gives a third fate. A final COMMIT or ROLLBACK whose virtual transaction ID
has local part 0 arrived after PostgreSQL had aborted the transaction, so the transaction
is aborted. Otherwise a final COMMIT means committed and a final ROLLBACK means aborted.
Exits 1 if the three fates or the arms disagree. Then compares the results with the
hypothesis written before the runs.
"""

import collections
import pathlib
import re
import sys

OUT = pathlib.Path(sys.argv[1])
# arm: (HTTP status, on_commit ran, fate, marker visible, error SQLSTATEs, final statement),
# written before the runs
HYPOTHESIS = {
    "atomic.orm.ok": (200, True, "committed", True, "-", "COMMIT"),
    "atomic.orm.long": (200, False, "aborted", False, "22001", "ROLLBACK"),
    "atomic.sql.ok": (200, True, "committed", True, "-", "COMMIT"),
    "atomic.sql.long": (200, True, "aborted", False, "22001", "COMMIT"),
    "nested.orm.ok": (200, True, "committed", True, "-", "COMMIT"),
    "nested.orm.long": (200, False, "committed", False, "22001", "COMMIT"),
    "nested.sql.ok": (200, True, "committed", True, "-", "COMMIT"),
    "nested.sql.long": (500, False, "aborted", False, "22001 25P02", "ROLLBACK"),
    "request.orm.ok": (200, True, "committed", True, "-", "COMMIT"),
    "request.orm.long": (200, False, "aborted", False, "22001", "ROLLBACK"),
    "request.sql.ok": (200, True, "committed", True, "-", "COMMIT"),
    "request.sql.long": (200, True, "aborted", False, "22001", "COMMIT"),
}
LINE = re.compile(r"^\S+ \S+ UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) sqlstate=(\w+) (\w+):\s+(.*)$")
CONTROL = re.compile(r"^(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)
END = re.compile(r"^(COMMIT|ROLLBACK);?$", re.IGNORECASE)

sessions = {}
for raw in (OUT / "server.log").read_text().splitlines():
    m = LINE.match(raw)
    if not m or m.group(2)[len("chk12-"):] not in HYPOTHESIS:
        continue
    pid, app, vxid, xid, sqlstate, kind, text = m.groups()
    s = sessions.setdefault(pid, {"arm": app[len("chk12-"):], "control": [], "errors": [], "xids": set(),
                                  "backends": set(), "end": "-", "end_vxid": "?"})
    if xid != "0":
        s["xids"].add(xid)
    if vxid:
        s["backends"].add(vxid.split("/")[0])
    if kind == "LOG":
        stmt = re.sub(r"^(statement|execute [^:]+):\s*", "", text).strip()
        if CONTROL.match(stmt):
            s["control"].append(re.sub(r'"[^"]*"', "sp", stmt))  # savepoint names differ per run
            if END.match(stmt):
                s["end"], s["end_vxid"] = stmt.rstrip(";").upper(), vxid
    elif kind == "ERROR":
        s["errors"].append(sqlstate)

printed = {}
for path in sorted(OUT.glob("*.rep*.out")):
    arm = http = ran = None
    for line in path.read_text().splitlines():
        if line.split(":", 1)[0] in HYPOTHESIS:
            arm = line.split(":", 1)[0]
        if m := re.match(r"\s+Django: HTTP (\d+)", line):
            http = int(m.group(1))
        if m := re.match(r"\s+on_commit callback ran: (\w+)", line):
            ran = m.group(1) == "True"
        if m := re.search(r"pg_xact_status\((\d+)\) (\w+), marker visible (\w+)", line):
            printed[m.group(1)] = (path.stem, arm, http, ran, m.group(2), m.group(3) == "True")

fates = {}
for line in (OUT / "psql-xact-status.txt").read_text().splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 2 and cells[0].isdigit():
        fates[cells[0]] = cells[1]

problems = 0
results = collections.defaultdict(list)
print(f"{'run':<9} {'arm':<17} {'pid':>4} {'xid':>4}  {'sent (transaction control)':<62} {'errors':<12} "
      f"{'end vxid':>8} script   psql     log      marker")
for pid, s in sorted(sessions.items(), key=lambda kv: int(kv[0])):
    xid = next(iter(s["xids"])) if len(s["xids"]) == 1 else "?"
    run, arm, http, ran, script_fate, visible = printed.get(xid, ("?", "?", None, None, "?", None))
    psql_fate = fates.get(xid, "?")
    aborted_before_end = s["end_vxid"].endswith("/0")
    log_fate = ("aborted" if aborted_before_end or s["end"] == "ROLLBACK"
                else "committed" if s["end"] == "COMMIT" else "?")
    errors = " ".join(sorted(s["errors"])) or "-"
    ok = arm == s["arm"] and script_fate == psql_fate == log_fate != "?" and len(s["backends"]) == 1
    problems += not ok
    print(f"{run:<9} {s['arm']:<17} {pid:>4} {xid:>4}  {' | '.join(s['control']):<62} {errors:<12} "
          f"{s['end_vxid']:>8} {script_fate:<8} {psql_fate:<8} {log_fate:<8} {visible}"
          f"{'' if ok else '   <-- DISAGREES'}")
    if ok:
        results[s["arm"]].append((http, ran, psql_fate, visible, errors, s["end"]))

missing = set(printed) - {next(iter(s["xids"])) for s in sessions.values() if len(s["xids"]) == 1}
if missing:
    problems += len(missing)
    print(f"printed transaction IDs with no session in the log: {sorted(missing, key=int)}")
print(f"\n{len(sessions)} sessions, {len(printed)} printed transaction IDs, {len(fates)} psql fates; "
      f"{'all sources agree' if not problems else f'{problems} problem(s)'}")

print("\nhypothesis (HTTP, on_commit ran, fate, marker visible, errors, final statement), per arm:")
for arm, expected in HYPOTHESIS.items():
    seen = results.get(arm, [])
    held = len(seen) == 3 and all(r == expected for r in seen)
    print(f"  {arm:<17} expected {expected}; {len(seen)} agreeing runs; "
          f"{'held' if held else f'NOT held: {sorted(set(seen), key=str)}'}")
sys.exit(1 if problems else 0)
