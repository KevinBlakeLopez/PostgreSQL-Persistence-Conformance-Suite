"""Cross-check CHK-2's server log, program outputs, and psql fates. Not part of the upstream script.

    python -I server_log_sessions.py output

For every subject session in output/server.log (application_name repro-managed,
repro-explicit, repro-raw or repro-control), prints the transaction-control statements
it sent, the errors the server raised, and the transaction ID on its last line. Matches
each session to the run and arm whose output printed the same transaction ID, and to
that ID's fate in output/psql-xact-status.txt. Exits 1 if anything disagrees.
"""

import pathlib
import re
import sys

OUT = pathlib.Path(sys.argv[1])
SUBJECTS = {"repro-managed": "managed", "repro-explicit": "explicit", "repro-raw": "raw", "repro-control": "control"}
LINE = re.compile(r"^\S+ \S+ UTC \[(\d+)\] app=(\S*) xid=(\d+) (LOG|ERROR|DETAIL|STATEMENT):\s+(.*)$")
CONTROL = re.compile(r"^(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)

sessions = {}
for raw in (OUT / "server.log").read_text().splitlines():
    m = LINE.match(raw)
    if not m or m.group(2) not in SUBJECTS:
        continue
    pid, app, xid, kind, text = m.groups()
    s = sessions.setdefault(pid, {"app": app, "control": [], "errors": [], "xid": "0"})
    s["xid"] = xid
    if kind == "LOG":
        stmt = re.sub(r"^(statement|execute [^:]+):\s*", "", text)
        if CONTROL.match(stmt):
            s["control"].append(stmt)
    elif kind == "ERROR":
        s["errors"].append(text)

printed = {}
for path in sorted(OUT.glob("*.rep*.out")):
    arm = None
    for line in path.read_text().splitlines():
        head = line.split(":", 1)[0]
        if head in SUBJECTS.values():
            arm = head
        m = re.search(r"pg_xact_status\((\d+)\) (\w+)", line)
        if m:
            printed[m.group(1)] = (path.stem, arm, m.group(2))

fates = {}
for line in (OUT / "psql-xact-status.txt").read_text().splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 4 and cells[2].isdigit():
        fates[cells[2]] = cells[3]

problems = 0
print(f"{'run':<13} {'arm':<9} {'pid':>4} {'xid':>4}  {'sent (transaction control)':<46} {'server error':<14} script   psql")
for pid, s in sessions.items():
    run, arm, script_fate = printed.get(s["xid"], ("?", "?", "?"))
    psql_fate = fates.get(s["xid"], "?")
    errors = ",".join("23505" if "duplicate key" in e else e for e in s["errors"]) or "-"
    ok = (arm == SUBJECTS[s["app"]] and script_fate == psql_fate and s["control"][-1:] == ["COMMIT;" if arm != "raw" else "COMMIT"]
          and errors == "23505")
    problems += not ok
    print(f"{run:<13} {arm:<9} {pid:>4} {s['xid']:>4}  {' '.join(s['control']):<46} {errors:<14} {script_fate:<8} {psql_fate}{'' if ok else '  <-- MISMATCH'}")

print(f"\n{len(sessions)} subject sessions; {len(printed)} transaction IDs printed by the program; {len(fates)} fates read by psql; mismatches: {problems}")
sys.exit(1 if problems or len(sessions) != len(printed) else 0)
