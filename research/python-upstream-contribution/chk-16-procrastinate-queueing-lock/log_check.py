"""Cross-check the server log, the program outputs and the psql fates.

    python -I log_check.py output

For every subject session in output/server.log (application_name chk16-<arm>), prints the
transaction-control statements it sent, the SQLSTATEs of the errors the server raised
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
# arm: (code outcome, on_commit ran, fate, order visible, queued jobs for the customer,
#       error SQLSTATEs, final statement), written before the runs
HYPOTHESIS = {
    "django.first": ("returned", "True", "committed", True, 1, "-", "COMMIT"),
    "django.repeat": ("returned", "True", "aborted", False, 1, "23505", "COMMIT"),
    "django.repeat_savepoint": ("returned", "True", "committed", True, 1, "23505", "COMMIT"),
    "psycopg.first": ("returned", "-", "committed", True, 1, "-", "COMMIT"),
    "psycopg.repeat": ("returned", "-", "aborted", False, 1, "23505", "COMMIT"),
    "psycopg.repeat_savepoint": ("returned", "-", "committed", True, 1, "23505", "COMMIT"),
}
LINE = re.compile(r"^\S+ \S+ UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) sqlstate=(\w+) (\w+):\s+(.*)$")
CONTROL = re.compile(r"^(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)
END = re.compile(r"^(COMMIT|ROLLBACK);?$", re.IGNORECASE)

sessions = {}
for raw in (OUT / "server.log").read_text().splitlines():
    m = LINE.match(raw)
    if not m or m.group(2)[len("chk16-"):] not in HYPOTHESIS:
        continue
    pid, app, vxid, xid, sqlstate, kind, text = m.groups()
    s = sessions.setdefault(pid, {"arm": app[len("chk16-"):], "control": [], "errors": [], "xids": set(),
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
    arm = code = ran = None
    for line in path.read_text().splitlines():
        if line.strip() in HYPOTHESIS:
            arm = line.strip()
        if m := re.match(r"\s+code: (returned|raised)\b.*; on_commit ran (\S+)$", line):
            code, ran = m.group(1), m.group(2)
        if m := re.search(r"pg_xact_status\((\d+)\) (\w+), order visible (\w+), queued jobs for the customer (\d+)", line):
            printed[m.group(1)] = (path.stem, arm, code, ran, m.group(2), m.group(3) == "True", int(m.group(4)))

fates = {}
for line in (OUT / "psql-xact-status.txt").read_text().splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 2 and cells[0].isdigit():
        fates[cells[0]] = cells[1]

problems = 0
results = collections.defaultdict(list)
print(f"{'run':<6} {'arm':<25} {'pid':>4} {'xid':>4}  {'sent (transaction control)':<56} {'errors':<7} "
      f"{'end vxid':>8} script    psql      log")
for pid, s in sorted(sessions.items(), key=lambda kv: int(kv[0])):
    xid = next(iter(s["xids"])) if len(s["xids"]) == 1 else "?"
    run, arm, code, ran, script_fate, visible, jobs = printed.get(xid, ("?", "?", None, None, "?", None, None))
    psql_fate = fates.get(xid, "?")
    log_fate = ("aborted" if s["end_vxid"].endswith("/0") or s["end"] == "ROLLBACK"
                else "committed" if s["end"] == "COMMIT" else "?")
    errors = " ".join(sorted(s["errors"])) or "-"
    ok = arm == s["arm"] and script_fate == psql_fate == log_fate != "?" and len(s["backends"]) == 1
    problems += not ok
    print(f"{run:<6} {s['arm']:<25} {pid:>4} {xid:>4}  {' | '.join(s['control']):<56} {errors:<7} "
          f"{s['end_vxid']:>8} {script_fate:<9} {psql_fate:<9} {log_fate}{'' if ok else '   <-- DISAGREES'}")
    if ok:
        results[s["arm"]].append((code, ran, psql_fate, visible, jobs, errors, s["end"]))

missing = set(printed) - {next(iter(s["xids"])) for s in sessions.values() if len(s["xids"]) == 1}
if missing:
    problems += len(missing)
    print(f"printed transaction IDs with no session in the log: {sorted(missing, key=int)}")
print(f"\n{len(sessions)} sessions, {len(printed)} printed transaction IDs, {len(fates)} psql fates; "
      f"{'all sources agree' if not problems else f'{problems} problem(s)'}")

print("\nhypothesis (code, on_commit ran, fate, order visible, queued jobs, errors, final statement), per arm:")
failed = 0
for arm, expected in HYPOTHESIS.items():
    seen = results.get(arm, [])
    held = len(seen) == 3 and all(r == expected for r in seen)
    failed += not held
    print(f"  {arm:<25} expected {expected}; {len(seen)} agreeing runs; "
          f"{'held' if held else f'NOT held: {sorted(set(seen), key=str)}'}")
sys.exit(1 if problems or failed else 0)
