"""Summarize the CHK-7 supplement's runs: the harness JSON, the server log, and psql.

Usage: python3 -I analyze_triggers.py [output/psql-xact-status.txt]

Prints one block per run with no pid, xid or timestamp in it, so that the three runs of a
case can be compared byte for byte. The JSON's witness is the harness's own autocommit
connection; the server-log lines are output/server-log-extract.txt. With the psql output
(pg_xact_status, read in a psql session inside the container), each block also gives the
outcome of the transactions involved. Without it, it prints the xids to look up.
"""
import hashlib, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
LINE = re.compile(r"^(\S+ \S+ \S+) \[(\d+)\] app=(\S*) vxid=(\S*) xid=(\d+) ([A-Z]+):  (.*)$")
DOOMED = "insert into p5a_review (code) values ('doomed')"
NEXT = "insert into p5a_review (code) values ('next')"
TRIGGER_NOTES = {"inject.commit_listener_raises": "the commit listener raised",
                 "psycopg.transaction_block_entered": "psycopg's transaction() block was entered"}


def exc(e):
    if e in ("returned", None):
        return str(e)
    s = f"{e['type']}: {e['msg']}"
    if "orig" in e:
        s += f" [orig {e['orig']}]"
    if "connection_invalidated" in e:
        s += f" [connection_invalidated={e['connection_invalidated']}]"
    return s


def statements(parsed, pid):
    return [(v, x, m[len("statement: "):]) for p, v, x, lvl, m in parsed
            if p == pid and lvl == "LOG" and m.startswith("statement: ")]


def block(d, parsed, status):
    f, s2 = d["first"], d["second_checkout"]
    out = [f"commit(): {exc(f.get('commit'))}"]
    if "after_commit" in f:
        a = f["after_commit"]
        out.append(f"after commit(): marker present={a['marker_present']} active={a['marker_active']}; "
                   f"in_transaction()={a['in_transaction']}; psycopg {a['psycopg']}; "
                   f"server {(a['activity'] or {}).get('state')}")
    window = (f.get("events_during_commit") or []) + (f.get("events_during_close") or []) \
        if "events_during_close" in f else (f.get("events_during_commit_and_exit") or [])
    kinds = [e["kind"] for e in d["timeline"]]
    out.append("trigger: " + "; ".join(v for k, v in TRIGGER_NOTES.items() if k in kinds) if
               any(k in kinds for k in TRIGGER_NOTES) else "trigger: none (control)")
    out.append("from commit() to the return to the pool:")
    out.append(f"  DBAPI commit() calls: {sum(e['kind'] == 'dbapi.commit.call' for e in window)}, raised: "
               + (", ".join(e["exc"]["type"] for e in window if e["kind"] == "dbapi.commit.raised") or "none"))
    out.append(f"  DBAPI rollback() calls: {sum(e['kind'] == 'dbapi.rollback.call' for e in window)}")
    out.append("  psycopg commands sent: " + (", ".join(e["cmd"] for e in window if e["kind"] == "psycopg.send") or "none"))
    out.append("  PoolEvents.reset: " + (", ".join(f"transaction_was_reset={e['transaction_was_reset']} with psycopg "
                                                   f"{e['psycopg']}" for e in window if e["kind"] == "sa.PoolEvents.reset")
                                         or "none"))
    out.append(f"  invalidations: {sum(e['kind'] == 'sa.PoolEvents.invalidate' for e in window)}")
    after = f.get("after_close") or f.get("after_with_exit") or {}
    out.append(f"after the return: psycopg {after.get('psycopg')}; server {(after.get('activity') or {}).get('state')}; "
               f"checked out {after.get('pool_checkedout')}")
    out.append(f"witness after the first unit: {d['visible_after_first_unit']}")
    out.append(f"second checkout: same DBAPI connection={s2.get('same_dbapi_object')}; same backend={s2.get('same_pid')}; "
               f"in_transaction()={s2.get('in_transaction')}; psycopg {s2.get('psycopg')}; "
               f"server {(s2.get('activity') or {}).get('state')}")
    out.append(f"  before its own insert, the transaction already has the first unit's xid: {s2.get('same_xid_as_first')}")
    out.append(f"  its commit(): {exc(s2.get('next_commit'))}; witness after it: {s2.get('visible_after_next')}")
    out.append(f"witness at the end: {d['visible_final']}")

    xids = []
    pid1, pid2 = f.get("pid"), s2.get("pid")
    seq = statements(parsed, pid1)
    texts = [t for _, _, t in seq]
    if pid1 != pid2 or DOOMED not in texts or NEXT not in texts:
        out.append("server log: the doomed and next inserts are not both on the first backend")
        return out, xids
    i_d = texts.index(DOOMED)
    i_n = texts.index(NEXT, i_d)
    i_c = texts.index("COMMIT", i_n)
    between = texts[i_d + 1:i_n]
    ends = [t for t in between if t in ("COMMIT", "ROLLBACK") or t.startswith("BEGIN")]
    one_vxid = seq[i_d][0] == seq[i_n][0] == seq[i_c][0]
    out.append("server log, first backend:")
    out.append("  statements between the doomed insert and the next insert: " + " ; ".join(between))
    out.append("  COMMIT, ROLLBACK or BEGIN among them: " + (", ".join(ends) or "none"))
    out.append(f"  the doomed insert, the next insert and the COMMIT after it share one vxid: {one_vxid}")
    first_xid = f.get("xid")
    out.append(f"  xid logged on the doomed insert: {'0' if seq[i_d][1] == '0' else 'non-zero'}; on the next insert "
               f"and its COMMIT: {'the first unit' + chr(39) + 's xid' if seq[i_n][1] == seq[i_c][1] == first_xid else 'another xid'}")
    xids = [first_xid, seq[i_c][1]]
    if status is not None:
        out.append(f"pg_xact_status (psql): first unit's transaction {status.get(first_xid)}; "
                   f"the transaction its next COMMIT ended {'(the same) ' if seq[i_c][1] == first_xid else ''}"
                   f"{status.get(seq[i_c][1])}")
    return out, xids


def main():
    status = None
    if len(sys.argv) > 1:
        status = dict(ln.split("|", 1) for ln in pathlib.Path(sys.argv[1]).read_text().splitlines() if "|" in ln)
    parsed = []
    for ln in (OUT / "server-log-extract.txt").read_text().splitlines():
        m = LINE.match(ln)
        if m:
            parsed.append((int(m.group(2)), m.group(4), m.group(5), m.group(6), m.group(7)))
    runs = json.loads((OUT / "runs.json").read_text())
    by_case, all_xids = {}, []
    for r in runs:
        d = json.loads((OUT / f"{r['run']}.json").read_text())
        lines, xids = block(d, parsed, status)
        all_xids += xids
        case = r["run"].rsplit(".rep", 1)[0]
        text = "\n".join(lines) + "\n"
        by_case.setdefault(case, []).append((r["run"], r["exit"], text))
    v = json.loads((OUT / f"{runs[0]['run']}.json").read_text())["versions"]
    print(f"versions: SQLAlchemy {v['sqlalchemy']}, psycopg {v['psycopg']} ({v['psycopg_impl']}, libpq {v['libpq']}), "
          f"Python {v['python']}, PostgreSQL {v['server']}")
    for case, reps in by_case.items():
        digests = {hashlib.sha256(t.encode()).hexdigest()[:12] for _, _, t in reps}
        print(f"\n## {case}: {len(reps)} runs, exits {[e for _, e, _ in reps]}, "
              f"{'blocks identical' if len(digests) == 1 else 'blocks DIFFER'} ({', '.join(sorted(digests))})")
        seen = set()
        for run, _, text in reps:
            if text in seen:
                continue
            seen.add(text)
            print(text, end="")
    if status is None:
        print("\nxids to look up: " + ",".join(sorted({x for x in all_xids if x}, key=int)))


if __name__ == "__main__":
    main()
