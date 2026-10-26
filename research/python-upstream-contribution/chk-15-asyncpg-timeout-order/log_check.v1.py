"""Cross-check the server log, the program outputs and the psql fates, per transaction.

    python -I log_check.py output

Groups the subject sessions' log lines (application_name chk13-<arm> or chk13-race-<loop>)
by transaction ID (%x). For every transaction the outputs printed, takes the SQLSTATE and
message of each error the server raised and the statement that ended the transaction, and
compares three fates: the witness's, psql's and the log's. A final COMMIT or ROLLBACK
whose virtual transaction ID has local part 0 arrived after PostgreSQL had aborted the
transaction; otherwise a final COMMIT means committed and a final ROLLBACK means aborted.
Then checks the hypotheses written before the runs. Exits 1 if a source disagrees or a
hypothesis does not hold.
"""

import collections
import pathlib
import re
import sys

OUT = pathlib.Path(sys.argv[1])
DEADLINE = 0.2  # the race's client timeout, in seconds
# Written before the runs. Each tuple: (query, block, fate, order visible, server errors,
# final statement, PostgreSQL had aborted before it).
# Every arm must match in all six arms runs (three per event loop).
ARMS = {
    "control_unlocked": ("returned", "exited normally", "committed", True, "-", "COMMIT", False),
    "client_first": ("caught TimeoutError", "exited normally", "aborted", False, "57014 user request", "COMMIT", True),
    "server_lock_timeout_first": ("-", "raised LockNotAvailableError (55P03)", "aborted", False, "55P03 lock timeout", "ROLLBACK", True),
    "server_statement_timeout_first": ("-", "raised QueryCanceledError (57014)", "aborted", False, "57014 statement timeout", "ROLLBACK", True),
    "server_lock_timeout_later": ("caught TimeoutError", "exited normally", "aborted", False, "57014 user request", "COMMIT", True),
    "server_statement_timeout_later": ("caught TimeoutError", "exited normally", "aborted", False, "57014 user request", "COMMIT", True),
    "asyncio_timeout": ("caught TimeoutError", "exited normally", "aborted", False, "57014 user request", "COMMIT", True),
}
# Every race trial must be one of these classes, with this signature. Also: R only at sleeps
# below the deadline, and TA only above it (a statement can be cancelled only while it runs).
RACE = {
    "R": ("returned", "exited normally", "committed", True, "-", "COMMIT", False),
    "TA": ("caught TimeoutError", "exited normally", "aborted", False, "57014 user request", "COMMIT", True),
    "TC": ("caught TimeoutError", "exited normally", "committed", True, "-", "COMMIT", False),
}
RACE_TRIALS = 2 * 61 * 4

LINE = re.compile(r"^\S+ \S+ UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) sqlstate=(\w+) (\w+):\s+(.*)$")
END = re.compile(r"^(COMMIT|ROLLBACK);?$", re.IGNORECASE)
TRIAL = re.compile(r"^(?:race sleep (\S+) rep\d+: (\w+);|(\w+):) query (.+?); block (exited normally|raised \w+ \(\w+\))"
                   r".*?pg_xact_status\((\d+)\) (\w+), marker visible (\w+)")
NOT_SUBJECT = {"chk13-witness", "chk13-setup", "chk13-migration"}

xacts = collections.defaultdict(lambda: {"errors": [], "end": "-", "end_vxid": "?", "apps": set(), "pids": set()})
for raw in (OUT / "server.log").read_text().splitlines():
    m = LINE.match(raw)
    if not m:
        continue
    pid, app, vxid, xid, sqlstate, kind, text = m.groups()
    if not app.startswith("chk13-") or app in NOT_SUBJECT or xid == "0":
        continue
    x = xacts[xid]
    x["apps"].add(app)
    x["pids"].add(pid)
    if kind == "ERROR":
        x["errors"].append(f"{sqlstate} {re.sub(r'^canceling statement due to ', '', text)}")
    elif kind == "LOG":
        stmt = re.sub(r"^(statement|execute [^:]+):\s*", "", text).strip()
        if END.match(stmt):
            x["end"], x["end_vxid"] = stmt.rstrip(";").upper(), vxid

fates = {}
for line in (OUT / "psql-xact-status.txt").read_text().splitlines():
    cells = [c.strip() for c in line.split("|")]
    if len(cells) == 2 and cells[0].isdigit():
        fates[cells[0]] = cells[1]

problems = 0
arms = collections.defaultdict(list)
race = collections.defaultdict(list)
for path in sorted(OUT.glob("*.out")):
    loop = path.stem.split(".")[0]
    for line in path.read_text().splitlines():
        m = TRIAL.match(line)
        if not m:
            continue
        sleep, cls, arm, query, block, xid, fate, visible = m.groups()
        x = xacts.get(xid)
        app = f"chk13-race-{loop}" if cls else f"chk13-{arm}"
        log_fate = "?"
        if x is not None:
            log_fate = ("aborted" if x["end_vxid"].endswith("/0") or x["end"] == "ROLLBACK"
                        else "committed" if x["end"] == "COMMIT" else "?")
        psql_fate = fates.get(xid, "?")
        if x is None or x["apps"] != {app} or len(x["pids"]) != 1 or not (fate == psql_fate == log_fate != "?"):
            problems += 1
            print(f"DISAGREES ({path.name}): witness {fate}, psql {psql_fate}, log {log_fate}, "
                  f"apps {sorted(x['apps']) if x else '-'}: {line}")
            continue
        result = (query, block, fate, visible == "True", " ".join(x["errors"]) or "-", x["end"],
                  x["end_vxid"].endswith("/0"))
        if cls:
            race[cls].append((loop, float(sleep), result))
        else:
            arms[arm].append((path.stem, xid, result))

checked = sum(len(v) for v in arms.values()) + sum(len(v) for v in race.values())
print(f"{checked} transactions; {len(fates)} psql fates; "
      f"{'witness, psql and the server log agree on every one' if not problems else f'{problems} disagreement(s)'}")

failed = 0
print("\narms, per run (query; block; fate; order visible; server errors; final statement; aborted before it):")
for arm, runs in arms.items():
    for stem, xid, r in runs:
        print(f"  {stem:<20} {arm:<31} xid {xid:>5}  {r}")
print("\narm hypotheses (six runs each):")
for arm, expected in ARMS.items():
    seen = [r for _, _, r in arms.get(arm, [])]
    held = len(seen) == 6 and all(r == expected for r in seen)
    failed += not held
    print(f"  {arm:<31} {len(seen)} runs; {'held' if held else 'NOT held: ' + str(sorted(set(seen), key=str))}")

print(f"\nrace ({RACE_TRIALS} trials expected; client deadline {DEADLINE} s):")
total = 0
for cls in sorted(race):
    trials = race[cls]
    total += len(trials)
    by_loop = collections.Counter(loop for loop, _, _ in trials)
    sleeps = sorted(s for _, s, _ in trials)
    signature = cls in RACE and all(r == RACE[cls] for _, _, r in trials)
    failed += not signature
    print(f"  {cls:<3} asyncio {by_loop['asyncio']:>3}, uvloop {by_loop['uvloop']:>3}; sleeps {sleeps[0]:.4f} to "
          f"{sleeps[-1]:.4f} s; signature {RACE.get(cls, 'not a hypothesised class')}: "
          f"{'held' if signature else 'NOT held'}")
r_ok = all(s < DEADLINE for _, s, _ in race.get("R", []))
ta_ok = all(s > DEADLINE for _, s, _ in race.get("TA", []))
count_ok = total == RACE_TRIALS
failed += (not r_ok) + (not ta_ok) + (not count_ok)
print(f"  every trial classified: {'held' if count_ok else f'NOT held ({total})'}; "
      f"R only below the deadline: {'held' if r_ok else 'NOT held'}; "
      f"TA only above it: {'held' if ta_ok else 'NOT held'}")
print(f"\n{'all hypotheses held' if not failed else f'{failed} hypothesis check(s) failed'}")
sys.exit(1 if problems or failed else 0)
