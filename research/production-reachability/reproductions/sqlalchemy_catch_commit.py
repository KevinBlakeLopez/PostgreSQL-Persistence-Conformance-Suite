"""Standalone SQLAlchemy reproduction. Uses the adapter virtualenv and the disposable server.

    adapters/sqlalchemy/.venv/bin/python research/production-reachability/reproductions/sqlalchemy_catch_commit.py
"""

import json
from pathlib import Path

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy import Integer, String

ROOT = Path(__file__).resolve().parents[3]
instance = json.loads((ROOT / ".ppcs-instance.json").read_text())
admin = psycopg.connect(
    host=instance.get("host", "127.0.0.1"),
    port=instance.get("port", 55435),
    user=instance.get("user", "postgres"),
    password=instance["password"],
    dbname="postgres",
    autocommit=True,
)
name = "ppcs_repro_sa"
admin.execute(f"drop database if exists {name} with (force)")
admin.execute(f"create database {name}")
url = (
    f"postgresql+psycopg://{instance.get('user', 'postgres')}:{instance['password']}"
    f"@{instance.get('host', '127.0.0.1')}:{instance.get('port', 55435)}/{name}"
)
engine = create_engine(url)
report = []
try:
    with engine.begin() as conn:
        conn.execute(text("create table item (id serial primary key, name text not null)"))
        conn.execute(text("create table uniq (id serial primary key, code text not null unique)"))
        conn.execute(text("insert into uniq (code) values ('taken')"))

    with engine.connect() as conn:
        try:
            with conn.begin():
                conn.execute(text("insert into item (name) values ('kept')"))
                try:
                    conn.execute(text("insert into uniq (code) values ('taken')"))
                except IntegrityError as exc:
                    caught = exc.orig.sqlstate
        except Exception as exc:
            report.append({"api": "Connection.begin()", "exited_with": type(exc).__name__, "sqlstate": caught})
        else:
            report.append({"api": "Connection.begin()", "exited_with": None, "sqlstate": caught})
        visible = conn.execute(text("select name from item")).scalars().all()
        report[-1]["visible"] = visible

    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "item"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String)

    class Uniq(Base):
        __tablename__ = "uniq"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        code: Mapped[str] = mapped_column(String)

    with Session(engine) as session:
        try:
            with session.begin():
                session.add(Item(name="orm"))
                session.flush()
                try:
                    session.add(Uniq(code="taken"))
                    session.flush()
                except IntegrityError as exc:
                    orm_state = exc.orig.sqlstate
        except Exception as exc:
            report.append({"api": "Session.begin() after caught flush", "exited_with": type(exc).__name__, "sqlstate": orm_state})
        else:
            report.append({"api": "Session.begin() after caught flush", "exited_with": None, "sqlstate": orm_state})
        report[-1]["visible"] = session.execute(text("select name from item")).scalars().all()
finally:
    engine.dispose()
    admin.execute(f"drop database if exists {name} with (force)")
    admin.close()

print(json.dumps({"sqlalchemy": __import__("sqlalchemy").__version__, "psycopg": psycopg.__version__, "report": report}, indent=2))
