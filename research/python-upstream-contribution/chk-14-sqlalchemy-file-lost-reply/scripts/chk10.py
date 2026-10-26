"""CHK-10: does sqlalchemy-file delete a committed row's file when the COMMIT reply is lost?

sqlalchemy-file 0.7.0 deletes the files uploaded in a unit of work from a Session
after_soft_rollback listener ("After rollback, new files are automatically deleted").
CHK-4 showed SQLAlchemy firing after_soft_rollback after a root COMMIT that raised, also
when PostgreSQL had committed. This runs sqlalchemy-file's README usage through the
same lost-reply proxy, PPCS's category-E proxy, unchanged.

Forms (unit 1):
  docs             the README's form: with Session(engine) as session: session.add(...); session.commit()
  begin            with Session(engine) as session, session.begin(): session.add(...)
  commit-rollback  session.commit(); on an exception, session.rollback() and re-raise
  admin            starlette-admin's call sequence (sync path), not starlette-admin itself: create()
                   adds and flushes inside session.begin_nested(); DBSessionMiddleware then commits
                   and, if the commit raises, calls session.rollback()
Arms:
  lost-reply  connection 1 goes through the proxy, which drops the reply to COMMIT
  rejected    a deferred foreign key fails at COMMIT (23503), so PostgreSQL rolls back
  no-fault    COMMIT succeeds
Unit 2 then saves another attachment on the same engine.

Ground truth: an independent psycopg connection reads whether the row committed, and
sqlalchemy-file's own StorageManager.get_file() says whether the file it references exists.
Instrumentation records events and sqlalchemy-file's delete_files() calls; it changes nothing.
stdout is stable across repetitions; names, paths and ids go to the raw JSON file.
Usage: chk10.py <form> <arm> <raw.json>  (env: CHK10_APP_PASSWORD, CHK10_CLUSTER_NAME, CHK10_STORAGE)
"""
import importlib.metadata
import itertools
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg
import sqlalchemy
from libcloud.storage.drivers.local import LocalStorageDriver
from libcloud.storage.types import ObjectDoesNotExistError
from sqlalchemy import Column, Integer, String, create_engine, event, text
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy_file import FileField
from sqlalchemy_file.storage import StorageManager
from sqlalchemy_file.types import FileFieldSessionTracker

PG_PORT = 55496  # the CHK-10 container; the observer refuses a server whose cluster_name differs
HERE = Path(__file__).resolve().parent
PROXY = HERE / "chk10_proxy.mjs"
NODE = shutil.which("node")
APP_PASSWORD = os.environ["CHK10_APP_PASSWORD"]
CLUSTER_NAME = os.environ["CHK10_CLUSTER_NAME"]
FORMS = ("docs", "begin", "commit-rollback", "admin")
ARMS = ("lost-reply", "rejected", "no-fault")
EVENTS: list[str] = []
RAW: dict = {}

logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)


def ev(name):
    EVENTS.append(name)


def describe(exc):
    if exc is None:
        return None
    return f"{type(exc).__module__}.{type(exc).__qualname__}: {str(exc).splitlines()[0]}"


Base = declarative_base()


class Attachment(Base):
    __tablename__ = "chk10_attachment"
    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(50), unique=True)
    content = Column(FileField)


def configure_storage():
    # As in sqlalchemy-file's README: a local libcloud container named "attachment".
    STORAGE = Path(os.environ["CHK10_STORAGE"])
    (STORAGE / "attachment").mkdir(parents=True, exist_ok=True)
    StorageManager.add_storage("default", LocalStorageDriver(str(STORAGE)).get_container("attachment"))


def instrument_library():
    original = FileFieldSessionTracker.delete_files.__func__

    def delete_files(cls, paths, ctx):
        ev(f"sqlalchemy_file.delete_files: {len(paths)} file(s), ctx={ctx}")
        return original(cls, paths, ctx)

    FileFieldSessionTracker.delete_files = classmethod(delete_files)
    for name in ("after_commit", "after_rollback", "after_soft_rollback"):
        event.listen(Session, name, (lambda n: lambda *a, **k: ev(f"orm.{n}"))(name))

    @event.listens_for(Attachment, "after_insert")
    def remember_path(mapper, connection, target):
        RAW.setdefault("inserted_paths", []).append(target.content["path"])


def make_engine(proxy_port):
    url = (f"postgresql+psycopg://chk10_app:{APP_PASSWORD}@127.0.0.1:{PG_PORT}/chk10"
           "?sslmode=disable&gssencmode=disable&application_name=chk10-subject")
    engine = create_engine(url, pool_size=1, max_overflow=0)
    for n in ("commit", "rollback"):
        event.listen(engine, n, (lambda n: lambda *a, **k: ev(f"core.{n}"))(n))
    for n in ("checkin", "invalidate", "reset"):
        event.listen(engine.pool, n, (lambda n: lambda *a, **k: ev(f"pool.{n}"))(n))
    count = itertools.count(1)

    @event.listens_for(engine, "do_connect")
    def route(dialect, conn_rec, cargs, cparams):
        i = next(count)
        if proxy_port is not None and i == 1:
            cparams["port"] = proxy_port
            ev(f"connect {i}: through the proxy")
        else:
            ev(f"connect {i}: direct")

    return engine


class Observer:
    def __init__(self):
        self.conn = psycopg.connect(host="127.0.0.1", port=PG_PORT, dbname="chk10", user="chk10_app",
                                    password=APP_PASSWORD, sslmode="disable", gssencmode="disable",
                                    application_name="chk10-observer", autocommit=True)
        cluster = self.conn.execute("show cluster_name").fetchone()[0]
        if cluster != CLUSTER_NAME:
            raise SystemExit(f"refusing: cluster_name is {cluster!r}")

    def committed_content(self, name):
        row = self.conn.execute("select content from chk10_attachment where name = %s", (name,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0]) if isinstance(row[0], str) else row[0]


def file_exists(path):
    try:
        StorageManager.get_file(path)
        return True
    except ObjectDoesNotExistError:
        return False


def stored_objects():
    return sorted(o.name for o in StorageManager.get("default").list_objects())


def unit1(engine, form, arm, name):
    payload = f"payload for {name}".encode()
    if form == "docs":
        with Session(engine) as session:
            session.add(Attachment(name=name, content=payload))
            if arm == "rejected":
                session.execute(text("insert into chk10_child(parent_id) values (-1)"))
            session.commit()
    elif form == "begin":
        with Session(engine) as session, session.begin():
            session.add(Attachment(name=name, content=payload))
            if arm == "rejected":
                session.execute(text("insert into chk10_child(parent_id) values (-1)"))
    elif form == "commit-rollback":
        with Session(engine) as session:
            session.add(Attachment(name=name, content=payload))
            if arm == "rejected":
                session.execute(text("insert into chk10_child(parent_id) values (-1)"))
            try:
                session.commit()
            except Exception:
                session.rollback()
                raise
    else:
        with Session(engine) as session:
            with session.begin_nested():
                session.add(Attachment(name=name, content=payload))
                session.flush()
            if arm == "rejected":
                session.execute(text("insert into chk10_child(parent_id) values (-1)"))
            try:
                session.commit()
            except Exception:
                session.rollback()
                raise


def unit2(engine, name):
    with Session(engine) as session:
        session.add(Attachment(name=name, content=b"unit 2"))
        session.commit()


def verdict(committed, exists):
    if committed and not exists:
        return "DANGLING: the committed row references a file sqlalchemy-file deleted"
    if committed:
        return "consistent: row committed, file kept"
    if exists:
        return "orphan: row absent, file kept"
    return "consistent: row absent, file deleted"


def report(observer, name, path):
    content = observer.committed_content(name)
    committed = content is not None
    referenced = content["path"] if committed else path
    exists = file_exists(referenced) if referenced else None
    return committed, referenced, exists


def main():
    if sys.argv[1] == "--versions":
        print(json.dumps({"sqlalchemy": sqlalchemy.__version__, "psycopg": psycopg.__version__,
                          "sqlalchemy-file": importlib.metadata.version("sqlalchemy-file"),
                          "apache-libcloud": importlib.metadata.version("apache-libcloud"),
                          "python": sys.version.split()[0]}))
        return
    form, arm, raw_path = sys.argv[1:4]
    assert form in FORMS and arm in ARMS
    configure_storage()
    observer = Observer()
    setup_engine = create_engine(f"postgresql+psycopg://chk10_app:{APP_PASSWORD}@127.0.0.1:{PG_PORT}/chk10"
                                 "?sslmode=disable&gssencmode=disable")
    Base.metadata.create_all(setup_engine)
    setup_engine.dispose()
    instrument_library()

    proxy = None
    proxy_port = None
    if arm == "lost-reply":
        proxy = subprocess.Popen([NODE, str(PROXY), str(PG_PORT)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        proxy_port = json.loads(proxy.stdout.readline())["listening"]
    engine = make_engine(proxy_port)
    name1 = f"{form}-{arm}-{secrets.token_hex(4)}"
    name2 = f"unit2-{secrets.token_hex(4)}"
    RAW.update({"form": form, "arm": arm, "name1": name1, "name2": name2})

    print(f"form={form} arm={arm}")
    print("--unit 1--")
    exc1 = None
    try:
        unit1(engine, form, arm, name1)
    except Exception as exc:
        exc1 = exc
    path1 = (RAW.get("inserted_paths") or [None])[0]
    print(" -> ".join(EVENTS))
    print(f"app saw: {describe(exc1) or 'no exception'}")
    committed, referenced, exists = report(observer, name1, path1)
    RAW["unit1"] = {"app_saw": describe(exc1), "committed": committed, "path": referenced, "file_exists": exists,
                    "events": list(EVENTS)}
    print(f"row committed: {'yes' if committed else 'no'}")
    print(f"file referenced by unit 1 exists: {'yes' if exists else 'no'}")
    print(f"verdict: {verdict(committed, exists)}")

    EVENTS.clear()
    print("--unit 2--")
    exc2 = None
    try:
        unit2(engine, name2)
    except Exception as exc:
        exc2 = exc
    committed2, referenced2, exists2 = report(observer, name2, None)
    RAW["unit2"] = {"app_saw": describe(exc2), "committed": committed2, "path": referenced2,
                    "file_exists": exists2, "events": list(EVENTS)}
    print(f"app saw: {describe(exc2) or 'no exception'}; row committed: {'yes' if committed2 else 'no'}; "
          f"file exists: {'yes' if exists2 else 'no'}")
    engine.dispose()
    if proxy is not None:
        proxy.stdin.close()
        dropped = json.loads(proxy.stdout.readline())["dropped"]
        proxy.wait(timeout=10)
        print(f"proxy dropped {dropped} COMMIT repl{'y' if dropped == 1 else 'ies'}")
    RAW["stored_objects"] = stored_objects()
    Path(raw_path).write_text(json.dumps(RAW, indent=1) + "\n")


if __name__ == "__main__":
    main()
