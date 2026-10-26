from sqlalchemy import create_engine, text

url = "postgresql+psycopg://postgres@127.0.0.1:5432/scratch"
engine = create_engine(url, pool_size=1, max_overflow=0, pool_pre_ping=False)
witness = create_engine(url)

def visible():
    with witness.connect() as conn:
        return list(conn.execute(text("select code from p5a order by code")).scalars())

def activity(pid):
    with witness.connect() as conn:
        return conn.execute(
            text("select state from pg_stat_activity where pid = :pid"),
            {"pid": pid},
        ).scalar()

def fail_commit_once(raw):
    original = raw.commit
    def commit():
        raw.commit = original
        raise RuntimeError("COMMIT was not sent")
    raw.commit = commit

def fail_rollbacks(raw, limit):
    original = raw.rollback
    calls = []
    def rollback():
        calls.append(raw.info.backend_pid)
        if len(calls) <= limit:
            raise RuntimeError("ROLLBACK was not sent")
        return original()
    raw.rollback = rollback
    return calls

with witness.begin() as conn:
    conn.execute(text("drop table if exists p5a"))
    conn.execute(text("create table p5a (code text primary key)"))

# 1. commit() raises before send.
# close() returns the connection to the default pool.
conn = engine.connect()
trans = conn.begin()
conn.execute(text("insert into p5a (code) values ('doomed')"))
raw = conn.connection.driver_connection
pid = raw.info.backend_pid
fail_commit_once(raw)
try:
    trans.commit()
except RuntimeError as exc:
    print("1. commit raised:", exc)
marker = conn.get_transaction()
print(
    "1. in_transaction:", conn.in_transaction(),
    "| marker:", marker is not None,
    "| marker active:", None if marker is None else marker.is_active,
    "| psycopg:", raw.info.transaction_status.name,
    "| pg:", activity(pid),
)
conn.close()
print("1. close returned | pg:", activity(pid))
conn2 = engine.connect()
raw2 = conn2.connection.driver_connection
print(
    "1. same dbapi:", raw2 is raw,
    "| same pid:", raw2.info.backend_pid == pid,
    "| in_transaction:", conn2.in_transaction(),
    "| psycopg:", raw2.info.transaction_status.name,
)
trans2 = conn2.begin()
conn2.execute(text("insert into p5a (code) values ('next')"))
trans2.commit()
print("1. visible:", visible())
conn2.close()

# 2. Control.
# rollback() is armed to raise, including during close().
with witness.begin() as conn:
    conn.execute(text("delete from p5a"))
conn = engine.connect()
trans = conn.begin()
conn.execute(text("insert into p5a (code) values ('doomed')"))
raw = conn.connection.driver_connection
pid = raw.info.backend_pid
fail_commit_once(raw)
calls = fail_rollbacks(raw, limit=99)
try:
    trans.commit()
except RuntimeError as exc:
    print("2. commit raised:", exc)
print("2. rollback calls before close:", len(calls))
conn.close()
print("2. close returned | rollback calls after close:", len(calls), "| pg:", activity(pid))
conn2 = engine.connect()
same = conn2.connection.driver_connection is raw
trans2 = conn2.begin()
conn2.execute(text("insert into p5a (code) values ('next')"))
trans2.commit()
print("2. same dbapi:", same, "| visible:", visible())
try:
    conn2.close()
except RuntimeError as exc:
    print("2. later close raised:", exc)
print("2. rollback calls after later close:", len(calls))

# 3. Control.
# A failed rollback that does reach pool reset.
with witness.begin() as conn:
    conn.execute(text("delete from p5a"))
conn = engine.connect()
trans = conn.begin()
conn.execute(text("insert into p5a (code) values ('doomed')"))
raw = conn.connection.driver_connection
pid = raw.info.backend_pid
fail_rollbacks(raw, limit=2)
try:
    trans.rollback()
except RuntimeError as exc:
    print("3. rollback raised:", exc)
conn.close()
print("3. close returned | pg:", activity(pid))
conn2 = engine.connect()
raw2 = conn2.connection.driver_connection
trans2 = conn2.begin()
conn2.execute(text("insert into p5a (code) values ('next')"))
trans2.commit()
print(
    "3. same dbapi:", raw2 is raw,
    "| same pid:", raw2.info.backend_pid == pid,
    "| visible:", visible(),
)
conn2.close()

engine.dispose()
witness.dispose()
