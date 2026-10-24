"""P4/P5: a COMMIT that PostgreSQL rejects, and reuse of an instance after rollback.

Premise probe for the gap analysis, not a PPCS case.
P5 (commit rejected): Django atomic() with a deferred FK violation (Django's own DDL, which
   PostgreSQL creates DEFERRABLE INITIALLY DEFERRED) and an on_commit callback; Tortoise
   in_transaction() with a deferred FK violation: which exception reaches the application.
P4 (retry with the same instance): the instance's INSERT ran inside a transaction that rolled
   back; the application retries save() with the same object in a new transaction.
   Tortoise, Django, and SQLAlchemy ORM (new Session per attempt, the object re-added).
A separate psycopg autocommit witness reads what PostgreSQL holds.
"""
import asyncio, json, os, sys

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
PW = open(os.path.join(HERE, ".pgpass_token")).read().strip()
PORT = 55483
DB = "probe45"
ADMIN = f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/{DB}"


def setup():
    with psycopg.connect(f"postgresql://postgres:{PW}@127.0.0.1:{PORT}/postgres", autocommit=True) as c:
        c.execute(f"drop database if exists {DB}")
        c.execute(f"create database {DB}")


def q(sql, args=()):
    with psycopg.connect(ADMIN, autocommit=True) as c:
        cur = c.execute(sql, args)
        return cur.fetchall() if cur.description else []


class AppError(Exception):
    pass


# ---------------------------------------------------------------- Django
def django_part():
    import django
    from django.conf import settings
    settings.configure(DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": DB,
                                              "USER": "postgres", "PASSWORD": PW, "HOST": "127.0.0.1",
                                              "PORT": str(PORT), "CONN_MAX_AGE": None}},
                       INSTALLED_APPS=[], USE_TZ=True)
    django.setup()
    from django.db import IntegrityError, connection, models, transaction

    class Parent(models.Model):
        class Meta:
            app_label = "probe"
            db_table = "dj_parent"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
        name = models.TextField()

        class Meta:
            app_label = "probe"
            db_table = "dj_child"

    class Thing(models.Model):
        name = models.TextField()

        class Meta:
            app_label = "probe"
            db_table = "dj_thing"

    with connection.schema_editor() as se:
        for m in (Parent, Child, Thing):
            se.create_model(m)
    ddl = q("select pg_get_constraintdef(oid) from pg_constraint where conrelid='dj_child'::regclass and contype='f'")
    out = {"fk_ddl": ddl[0][0] if ddl else None}

    # P5: deferred FK violation surfaces at COMMIT
    hooks = []
    raised_at = None
    try:
        with transaction.atomic():
            c = Child(parent_id=999, name="orphan")
            c.save()
            raised_at = "not at save()"
            transaction.on_commit(lambda: hooks.append("on_commit ran"))
    except IntegrityError as e:
        out["p5_django"] = {"save_raised": raised_at is None, "atomic_exit_raised": type(e).__name__,
                            "sqlstate": getattr(e.__cause__, "sqlstate", None), "on_commit": hooks,
                            "instance_pk_after": c.pk, "instance_adding_after": c._state.adding,
                            "row_present": bool(q("select 1 from dj_child where name='orphan'"))}
    # the persistent connection after the failed COMMIT
    with transaction.atomic():
        Thing.objects.create(name="after-commit-failure")
    out["p5_django"]["next_atomic_ok"] = bool(q("select 1 from dj_thing where name='after-commit-failure'"))

    # P4: retry with the same instance after a rollback
    t = Thing(name="dj-retry")
    try:
        with transaction.atomic():
            t.save()
            raise AppError("first attempt fails after the INSERT")
    except AppError:
        pass
    state = {"pk": t.pk, "adding": t._state.adding}
    with transaction.atomic():
        t.save()
    out["p4_django"] = {"after_rollback": state, "retry_returned": "normally",
                        "rows_with_name": q("select count(*) from dj_thing where name='dj-retry'")[0][0]}
    connection.close()
    return out


# ---------------------------------------------------------------- Tortoise
async def tortoise_part():
    from tortoise import Tortoise, fields
    from tortoise.exceptions import IntegrityError as TIntegrityError
    from tortoise.models import Model
    from tortoise.transactions import in_transaction
    import asyncpg

    class TItem(Model):
        id = fields.IntField(primary_key=True)
        name = fields.TextField()

        class Meta:
            table = "t_item"

    globals()["TItem"] = TItem
    await Tortoise.init(db_url=ADMIN.replace("postgresql://", "postgres://") + "?minsize=1&maxsize=1",
                        modules={"models": ["__main__"]})
    await Tortoise.generate_schemas()
    q("create table t_parent (id int primary key)")
    q("create table t_child (id serial primary key, parent_id int references t_parent(id) deferrable initially deferred)")
    out = {}
    # P5: deferred FK violation at COMMIT inside in_transaction()
    try:
        async with in_transaction() as conn:
            await conn.execute_query("insert into t_child(parent_id) values (999)")
        out["p5_tortoise"] = {"raised": None}
    except TIntegrityError as e:
        out["p5_tortoise"] = {"raised": f"tortoise IntegrityError: {e}"[:120]}
    except asyncpg.PostgresError as e:
        out["p5_tortoise"] = {"raised": f"{type(e).__module__}.{type(e).__name__} sqlstate={e.sqlstate}",
                              "is_tortoise_IntegrityError": isinstance(e, TIntegrityError)}
    # P4: retry with the same instance after a rollback
    obj = TItem(name="tt-retry")
    try:
        async with in_transaction():
            await obj.save()
            raise AppError("first attempt fails after the INSERT")
    except AppError:
        pass
    state = {"pk": obj.pk, "_saved_in_db": obj._saved_in_db}
    try:
        async with in_transaction():
            await obj.save()
        retry = "returned normally"
    except Exception as e:  # noqa
        retry = f"raised {type(e).__name__}: {e}"
    out["p4_tortoise"] = {"after_rollback": state, "retry": retry,
                          "rows_with_name": q("select count(*) from t_item where name='tt-retry'")[0][0]}
    await Tortoise.close_connections()
    return out


# ---------------------------------------------------------------- SQLAlchemy
def sqlalchemy_part():
    import sqlalchemy as sa
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, make_transient

    class Base(DeclarativeBase):
        pass

    class SItem(Base):
        __tablename__ = "s_item"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]

    eng = sa.create_engine(ADMIN.replace("postgresql://", "postgresql+psycopg://"))
    Base.metadata.create_all(eng)
    obj = SItem(name="sa-retry")
    try:
        with Session(eng) as s, s.begin():
            s.add(obj)
            s.flush()
            raise AppError("first attempt fails after the INSERT")
    except AppError:
        pass
    st = sa.inspect(obj)
    state = {"pk": obj.id, "transient": st.transient, "detached": st.detached, "has_identity": st.has_identity}
    with Session(eng) as s, s.begin():
        s.add(obj)
    out = {"p4_sqlalchemy": {"after_rollback": state, "retry_returned": "normally",
                             "rows_with_name": q("select count(*) from s_item where name='sa-retry'")[0][0]}}
    eng.dispose()
    return out


async def main():
    setup()
    res = {}
    res.update(await tortoise_part())
    res.update(await asyncio.to_thread(sqlalchemy_part))
    res.update(await asyncio.to_thread(django_part))
    import django, tortoise, sqlalchemy
    res["versions"] = {"django": django.get_version(), "tortoise": tortoise.__version__,
                       "sqlalchemy": sqlalchemy.__version__, "psycopg": psycopg.__version__}
    print(json.dumps(res, indent=1, default=str))


asyncio.run(main())
