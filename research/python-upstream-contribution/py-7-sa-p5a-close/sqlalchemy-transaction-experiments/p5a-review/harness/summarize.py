import json, pathlib, re, sys
src = pathlib.Path("p5a_review.py").read_text()
names = re.findall(r'^\s+"([a-z_\-]+)":', src.split("CASES = {", 1)[1].split("\n}\n", 1)[0], re.M)
def short(e):
    if e == "returned" or e is None: return str(e)
    s = e["type"].replace("builtins.", "").replace("sqlalchemy.exc.", "sa.").replace("psycopg.errors.", "pg.").replace("psycopg.", "pg.")
    if "orig" in e: s += f"(orig={e['orig'].replace('psycopg.errors.', 'pg.').replace('psycopg.', 'pg.')},{e.get('sqlstate')})"
    if "connection_invalidated" in e: s += f" inv={e['connection_invalidated']}"
    return s
def ev(events):
    out = []
    for e in events or []:
        k = e["kind"]
        if k == "sa.PoolEvents.reset": out.append(f"reset(was_reset={e['transaction_was_reset']},pg={e['psycopg']})")
        elif k == "dbapi.rollback.call": out.append(f"rollback()[{e['status_before']}<-{e['caller'].split('>')[-2] if '>' in e['caller'] else e['caller']}]")
        elif k == "psycopg.send": out.append(f"send:{e['cmd']}")
        elif k == "sa.PoolEvents.invalidate": out.append("invalidate")
        elif k == "dbapi.rollback.raised": out.append("rollback-raised")
    return " ".join(out) or "-"
for n in names:
    p = pathlib.Path(f"results/{n}.json")
    try: d = json.loads(p.read_text())
    except Exception as x: print(f"{n}: unreadable {x}"); continue
    f, s = d["first"], d["second_checkout"]
    ac = f.get("after_commit") or {}
    act = (ac.get("activity") or {}).get("state")
    close_ev = f.get("events_during_close") or f.get("events_during_commit_and_exit") or f.get("events_during_rollback_and_close")
    after = f.get("after_close") or f.get("after_with_exit") or {}
    print(f"\n## {n}")
    print(f"  commit -> {short(f.get('commit'))}  [{f.get('commit_seconds','')}s]")
    if ac: print(f"  after commit: marker={ac.get('marker_present')}/{ac.get('marker_active')} conn.invalidated={ac.get('connection_invalidated')} psycopg={ac.get('psycopg')} server={act}")
    if "rollback" in f: print(f"  rollback() -> {short(f['rollback'])}; during: {ev(f.get('events_during_rollback'))}; after: psycopg={(f.get('after_rollback') or {}).get('psycopg')} server={((f.get('after_rollback') or {}).get('activity') or {}).get('state')}")
    if "reuse_commit" in f: print(f"  reuse same Connection: xid_before_insert={f.get('reuse_xid_before_insert')} (first xid={f.get('xid')}) commit -> {short(f['reuse_commit'])} visible={f.get('visible_after_reuse')}")
    print(f"  close/exit events: {ev(close_ev)}")
    print(f"  after close: psycopg={after.get('psycopg')} server={(after.get('activity') or {}).get('state')} checkedout={after.get('pool_checkedout')}")
    print(f"  visible after first unit: {d['visible_after_first_unit']}")
    print(f"  2nd checkout: same_pid={s.get('same_pid')} in_tx={s.get('in_transaction')} psycopg={s.get('psycopg')} server={(s.get('activity') or {}).get('state')} xid_seen={s.get('xid_seen_before_insert')} same_xid={s.get('same_xid_as_first')} next_commit={short(s.get('next_commit'))}")
    print(f"  visible after next: {s.get('visible_after_next')} | final: {d['visible_final']}")
