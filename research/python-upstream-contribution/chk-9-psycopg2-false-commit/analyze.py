"""Summarize the false-commit runs: one block per arm, comparable across the three runs.

Usage: python3 -I analyze.py [output/psql-xact-status.txt]

Each block holds what the API reported, what the witness saw, and the arm's statements as the server
logged them (application_name fc-<arm>-r<rep>), with no ids, pids or timestamps. Without the psql file
it prints the transaction ids to look up.
"""
import hashlib, json, pathlib, re, sys

OUT = pathlib.Path(__file__).resolve().parent / "output"
LINE = re.compile(r"^\S+ \S+ \S+ \[\d+\] app=(\S*) vxid=\S* xid=\d+ sqlstate=(\w+) ([A-Z]+):  (.*)$")


def server_sequence(lines, app):
    seq = []
    for ln in lines:
        m = LINE.match(ln)
        if not m or m.group(1) != app:
            continue
        sqlstate, level, msg = m.group(2), m.group(3), m.group(4)
        if level == "LOG" and (msg.startswith("statement: ") or msg.startswith("execute ")):
            sql = msg.split(": ", 1)[1]
            if "fc_item" in sql:
                seq.append("insert fc_item" if sql.lower().startswith("insert") else "fc_item query")
            elif "pg_current_xact_id" in sql:
                seq.append("select xid")
            elif sql.strip().upper() in ("BEGIN", "COMMIT", "ROLLBACK") or sql.upper().startswith("BEGIN"):
                seq.append(sql.strip().upper())
        elif level == "ERROR":
            seq.append(f"ERROR {sqlstate}")
    return seq


def block(a, lines, fates):
    keys = ["failing_statement", "driver_status_before_commit", "sa_in_transaction_before_commit", "api",
            "commit_command_status", "driver_status_after_commit", "sa_in_transaction_after_commit"]
    out = [f"{k}: {a[k]}" for k in keys if k in a]
    if "events" in a:
        out.append("events: " + (", ".join(a["events"]) or "none"))
    w = a["witness"]
    out.append(f"witness: row X exists={w['row_x_exists']}; pg_xact_status={w['xact_status']}")
    if fates is not None:
        out.append(f"psql pg_xact_status: {fates.get(a['xid'])}")
    out.append("server log: " + " | ".join(server_sequence(lines, a["application_name"])))
    return "\n".join("  " + s for s in out) + "\n"


def main():
    fates = None
    if len(sys.argv) > 1:
        fates = dict(ln.split("|", 1) for ln in pathlib.Path(sys.argv[1]).read_text().splitlines() if "|" in ln)
    lines = (OUT / "server-log-extract.txt").read_text().splitlines()
    reps = [json.loads((OUT / f"rep{n}.json").read_text()) for n in (1, 2, 3)]
    v = reps[0]["versions"]
    print(f"versions: SQLAlchemy {v['sqlalchemy']}; psycopg2 {v['psycopg2']} (libpq {v['psycopg2_libpq']}); "
          f"psycopg {v['psycopg']} ({v['psycopg_impl']}, libpq {v['psycopg_libpq']}); Python {v['python']}; "
          f"PostgreSQL {v['server']}")
    xids = []
    for i, arm in enumerate(reps[0]["arms"]):
        blocks = [block(r["arms"][i], lines, fates) for r in reps]
        xids += [r["arms"][i]["xid"] for r in reps if r["arms"][i]["xid"]]
        same = len({hashlib.sha256(b.encode()).hexdigest() for b in blocks}) == 1
        print(f"\n## {arm['arm']}: 3 runs, {'identical' if same else 'DIFFERENT'}")
        for b in (blocks[:1] if same else blocks):
            print(b, end="")
    if fates is None:
        print("\nxids: " + ",".join(sorted(set(xids), key=int)))


if __name__ == "__main__":
    main()
