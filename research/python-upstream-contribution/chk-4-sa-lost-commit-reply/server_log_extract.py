"""Check CHK-4's runs against the server's statement log, independently of SQLAlchemy and the drivers.

Usage: server_log_extract.py <full server log> <output dir>
For every run's raw JSON (output/sa-*/raw/*.json) it keeps the log lines of that run's sessions (unit 1's
backend, unit 2's if different, and the observer's), within the run's start and end times plus one second,
in output/sa-<version>/server-log/<run>.txt. It then checks, from the log alone:
  every arm   unit 1's backend logged COMMIT with unit 1's xid, and unit 2's backend logged COMMIT with unit 2's
  lost-reply  after that COMMIT, unit 1's backend logged no statement and no error, only its disconnection
  rejected    that COMMIT was followed by an ERROR with SQLSTATE 23503 (the deferred foreign key)
  no-fault    that COMMIT was followed by no ERROR
It also lists what unit 1's backend logged after its COMMIT, in output/server-log-checks.txt.
The program refuses to write any line that contains a password from the instance file.
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) UTC \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) "
                  r"sqlstate=(\w+) (\w+):\s+(.*)$")
COMMIT = re.compile(r"^(statement|execute [^:]+): COMMIT;?$", re.I)
STATEMENT = re.compile(r"^(statement|execute [^:]+): (.*)$", re.I)


def parse(path):
    entries = []
    for raw in open(path, encoding="utf-8", errors="replace"):
        m = LINE.match(raw.rstrip("\n"))
        if m:
            when = datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            entries.append({"when": when, "pid": int(m[2]), "app": m[3], "vxid": m[4], "xid": m[5],
                            "sqlstate": m[6], "level": m[7], "msg": m[8], "raw": raw.rstrip("\n")})
    return entries


def short(entry):
    return f"{entry['level']} vxid={entry['vxid']} xid={entry['xid']} sqlstate={entry['sqlstate']}: {entry['msg'][:90]}"


def check_run(raw, entries):
    lo = datetime.fromisoformat(raw["started"]) - timedelta(seconds=1)
    hi = datetime.fromisoformat(raw["ended"]) + timedelta(seconds=1)
    u1, u2 = raw["unit1"], raw["unit2"]
    pids = {u1["pid"], u2["pid"], raw["observer_pid"]}
    mine = [e for e in entries if e["pid"] in pids and lo <= e["when"] <= hi]
    b1 = [e for e in mine if e["pid"] == u1["pid"]]
    problems, notes = [], []
    commits = [i for i, e in enumerate(b1) if COMMIT.match(e["msg"]) and e["xid"] == u1["xid"]]
    if len(commits) != 1:
        problems.append(f"unit 1's backend logged {len(commits)} COMMIT lines with unit 1's xid")
    else:
        after = b1[commits[0] + 1:]
        notes = [short(e) for e in after]
        statements = [e for e in after if STATEMENT.match(e["msg"])]
        errors = [e for e in after if e["level"] in ("ERROR", "FATAL")]
        if raw["arm"] == "lost-reply":
            if statements or errors:
                problems.append("unit 1's backend logged a statement or an error after COMMIT")
            if not any(e["msg"].startswith("disconnection:") for e in after):
                problems.append("unit 1's backend logged no disconnection after COMMIT")
        elif raw["arm"] == "rejected":
            if not after or after[0]["level"] != "ERROR" or after[0]["sqlstate"] != "23503":
                problems.append("COMMIT was not followed by ERROR 23503")
        elif errors:
            problems.append("the control's COMMIT was followed by an error")
    b2 = [e for e in mine if e["pid"] == u2["pid"]]
    if not any(COMMIT.match(e["msg"]) and e["xid"] == u2["xid"] for e in b2):
        problems.append("unit 2's backend logged no COMMIT with unit 2's xid")
    return mine, problems, notes


def main(log_path, out_dir):
    instance = json.load(open(os.environ["CHK4_INSTANCE"]))
    secrets = [instance["app_password"], instance["superuser_password"]]
    entries = parse(log_path)
    report = []
    failures = 0
    for raw_path in sorted(glob.glob(os.path.join(out_dir, "sa-*", "raw", "*.json"))):
        raw = json.load(open(raw_path))
        name = os.path.basename(raw_path)[:-5]
        mine, problems, notes = check_run(raw, entries)
        text = "\n".join(e["raw"] for e in mine) + "\n"
        if any(s in text for s in secrets):
            raise SystemExit(f"refusing to write {name}: a password is in the extract")
        log_dir = os.path.join(os.path.dirname(os.path.dirname(raw_path)), "server-log")
        os.makedirs(log_dir, exist_ok=True)
        open(os.path.join(log_dir, f"{name}.txt"), "w").write(text)
        failures += bool(problems)
        report.append(f"sa-{raw['sqlalchemy']} {name}: {'OK' if not problems else 'FAIL: ' + '; '.join(problems)}")
        report.append("  unit 1's backend after its COMMIT: " + (" | ".join(notes) if notes else "(nothing)"))
    report.append(f"{len(report) // 2} runs checked against the server log; runs with a problem: {failures}")
    open(os.path.join(out_dir, "server-log-checks.txt"), "w").write("\n".join(report) + "\n")
    print("\n".join(report[-1:]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
