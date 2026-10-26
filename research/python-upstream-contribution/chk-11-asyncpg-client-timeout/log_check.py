"""Cross-check the server log, the program outputs and the psql fates.

    python -I log_check.py output

For every subject session in output/server.log (application_name repro-<arm>), prints
the transaction-control statements it sent, the errors the server raised, and its
transaction ID. Matches each session to the run and arm whose output printed that ID,
and to the ID's fate in output/psql-xact-status.txt. Exits 1 if the sources disagree.
Then compares the agreed results with the hypothesis written before the runs.
"""

import collections
import pathlib
import re
import sys

OUT = pathlib.Path(sys.argv[1])
CANCEL = "canceling statement due to user request"
# arm: (fate, cancel errors, last transaction-control statement), written before the runs
HYPOTHESIS = {
    "managed": ("aborted", 1, "COMMIT;"),
    "explicit": ("aborted", 1, "COMMIT;"),
    "raw": ("aborted", 1, "COMMIT"),
    "command_timeout": ("aborted", 1, "COMMIT;"),
    "wait_for": ("aborted", 1, "COMMIT;"),
    "control_savepoint": ("committed", 1, "COMMIT;"),
    "control_fast": ("committed", 0, "COMMIT;"),
    "control_uncaught": ("aborted", 1, "ROLLBACK;"),
}
LINE = re.compile(r"^\S+ \S+ UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) (\w+):\s+(.*)$")
CONTROL = re.compile(r"^(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.IGNORECASE)

sessions = {}
for raw in (OUT / "server.log").read_text().splitlines():
    m = LINE.match(raw)
    if not m or m.group(2)[len("repro-"):] not in HYPOTHESIS:
        continue
    pid, app, vxid, xid, kind, text = m.groups()
    s = sessions.setdefault(pid, {"arm": app[len("repro-"):], "control": [], "errors": [], "xids": set(),
                                  "backends": set(), "final_vxid": "?"})
    if xid != "0":
        s["xids"].add(xid)
    # The backend part of the virtual transaction ID stays fixed. PostgreSQL resets the local
    # part to 0 when it aborts the transaction, while %x keeps the xid until the block ends.
    s["backends"].add(vxid.split("/")[0])
    if kind == "LOG":
        stmt = re.sub(r"^(statement|execute [^:]+):\s*", "", text)
        if CONTROL.match(stmt):
            s["control"].append(stmt)
            s["final_vxid"] = vxid
    elif kind == "ERROR":
        s["errors"].append(text)

printed = {}
for path in sorted(OUT.glob("*.rep*.out")):
    arm = None
    for line in path.read_text().splitlines():
        head = line.split(":", 1)[0]
        if head in HYPOTHESIS:
            arm = head
        m = re.search(r"pg_xact_status\((\d+)\) (\w+), marker visible (\w+)", line)
        if m:
            printed[m.group(1)] = (path.stem, arm, m.group(2), m.group(3))

fates = {}
for line in (OUT / "psql-xact-status.txt").read_text().splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 2 and cells[0].isdigit():
        fates[cells[0]] = cells[1]

problems = 0
agreed = collections.defaultdict(list)
print(f"{'run':<13} {'arm':<18} {'pid':>5} {'xid':>5}  {'sent (transaction control)':<58} {'errors':<10} {'end vxid':>8} script   psql     marker")
for pid, s in sorted(sessions.items(), key=lambda kv: int(kv[0])):
    xid = next(iter(s["xids"])) if len(s["xids"]) == 1 else "?"
    run, arm, script_fate, visible = printed.get(xid, ("?", "?", "?", "?"))
    psql_fate = fates.get(xid, "?")
    cancels = sum(CANCEL in e for e in s["errors"])
    others = [e for e in s["errors"] if CANCEL not in e]
    errors = (f"57014x{cancels}" if cancels else "-") + (" +other" if others else "")
    released = s["final_vxid"].endswith("/0")
    ok = (arm == s["arm"] and script_fate == psql_fate != "?" and not others and len(s["backends"]) == 1
          and visible == ("True" if psql_fate == "committed" else "False")
          and released == (psql_fate == "aborted"))
    problems += not ok
    print(f"{run:<13} {s['arm']:<18} {pid:>5} {xid:>5}  {' | '.join(s['control']):<58} {errors:<10} {s['final_vxid']:>8} "
          f"{script_fate:<8} {psql_fate:<8} {visible}{'' if ok else '   <-- DISAGREES'}")
    if ok:
        agreed[s["arm"]].append((psql_fate, cancels, s["control"][-1] if s["control"] else "-"))

missing = set(printed) - {next(iter(s["xids"])) for s in sessions.values() if len(s["xids"]) == 1}
if missing:
    problems += len(missing)
    print(f"printed transaction IDs with no session in the log: {sorted(missing, key=int)}")
print(f"\n{len(sessions)} sessions, {len(printed)} printed transaction IDs, {len(fates)} psql fates; "
      f"{'all sources agree' if not problems else f'{problems} problem(s)'}")

print("\nhypothesis (fate, 57014 count, last control statement), per arm:")
for arm, expected in HYPOTHESIS.items():
    seen = agreed.get(arm, [])
    held = len(seen) == 6 and all(r == expected for r in seen)
    print(f"  {arm:<18} expected {expected}; {len(seen)} agreeing runs; {'held' if held else f'NOT held: {sorted(set(seen))}'}")
sys.exit(1 if problems else 0)
