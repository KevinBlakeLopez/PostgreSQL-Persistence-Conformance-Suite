"""CHK-5 controls, not for the upstream issue: Django and SQLAlchemy on the same retries.

    DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55495/postgres \
      python -I controls_django_sqlalchemy.py

The arms are those of tortoise_save_after_rollback.py: retry, retry-changed, savepoint and
savepoint-changed. Django uses atomic(), with a nested atomic() (a savepoint) for the
savepoint arms. SQLAlchemy ORM uses a new Session per attempt, with the object added again,
as in the gap analysis's P4, and begin_nested() for the savepoint arms. A separate psycopg
connection, in autocommit, reads pg_xact_status() of the transaction IDs captured inside the
transactions, and counts the arm's rows. The program creates database chk5_controls, and
drops it at the end.
"""

import os
import platform
from urllib.parse import urlsplit

import psycopg

URL = os.environ["DATABASE_URL"]
NAME = "chk5_controls"


class AppError(Exception):
    pass


def conninfo(**extra):
    return psycopg.conninfo.make_conninfo(URL, dbname=NAME, **extra)


def report(witness, label, xid):
    fate = witness.execute("select pg_xact_status(%s::text::xid8)", (xid,)).fetchone()[0]
    print(f"  {label}transaction: pg_xact_status({xid}) {fate}")


def count(witness, table, arm):
    n = witness.execute(f"select count(*) from {table} where arm = %s", (arm,)).fetchone()[0]
    return f"rows with arm={arm!r}: {n}"


# ---------------------------------------------------------------- Django
def django_part(witness):
    import django
    from django.conf import settings

    url = urlsplit(URL)
    settings.configure(
        DATABASES={"default": {
            "ENGINE": "django.db.backends.postgresql", "NAME": NAME, "USER": url.username,
            "PASSWORD": url.password, "HOST": url.hostname, "PORT": str(url.port),
            "OPTIONS": {"application_name": "repro-django"},
        }},
        INSTALLED_APPS=[], USE_TZ=True,
    )
    django.setup()
    from django.db import connection, models, transaction

    class DItem(models.Model):
        arm = models.TextField()
        value = models.IntegerField()

        class Meta:
            app_label = "controls"
            db_table = "dj_item"

    with connection.schema_editor() as editor:
        editor.create_model(DItem)

    def xid():
        with connection.cursor() as cursor:
            cursor.execute("select pg_current_xact_id()::text")
            return cursor.fetchone()[0]

    for change in (False, True):
        arm = "retry-changed" if change else "retry"
        print(f"django-{arm}: save() in atomic(), the block raises; then"
              + (" value = 2 and" if change else "") + " save() again in a new atomic()")
        obj = DItem(arm=arm, value=1)
        try:
            with transaction.atomic():
                obj.save()
                first = xid()
                raise AppError("the application fails after save()")
        except AppError:
            pass
        report(witness, "first ", first)
        print(f"  after the rollback: pk={obj.pk}, _state.adding={obj._state.adding}")
        if change:
            obj.value = 2
        with transaction.atomic():
            obj.save()
            second = xid()
        print(f"  second save() returned normally, pk={obj.pk}")
        report(witness, "second ", second)
        print(f"  {count(witness, 'dj_item', arm)}")

    for change in (False, True):
        arm = "savepoint-changed" if change else "savepoint"
        print(f"django-{arm}: in an outer atomic(), save() in a nested atomic() that raises;"
              " the error is caught; then" + (" value = 2 and" if change else "") + " save() again in the outer block")
        obj = DItem(arm=arm, value=1)
        with transaction.atomic():
            try:
                with transaction.atomic():
                    obj.save()
                    raise AppError("the application fails after save()")
            except AppError:
                pass
            print(f"  after the savepoint rollback: pk={obj.pk}, _state.adding={obj._state.adding}")
            if change:
                obj.value = 2
            obj.save()
            outer = xid()
            print(f"  second save() returned normally, pk={obj.pk}")
        report(witness, "outer ", outer)
        print(f"  {count(witness, 'dj_item', arm)}")
    connection.close()
    return django.get_version()


# ---------------------------------------------------------------- SQLAlchemy
def sqlalchemy_part(witness):
    import sqlalchemy as sa
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

    class Base(DeclarativeBase):
        pass

    class SItem(Base):
        __tablename__ = "sa_item"
        id: Mapped[int] = mapped_column(primary_key=True)
        arm: Mapped[str]
        value: Mapped[int]

    url = sa.make_url(URL).set(drivername="postgresql+psycopg", database=NAME)
    engine = sa.create_engine(url, connect_args={"application_name": "repro-sqlalchemy"})
    Base.metadata.create_all(engine)
    xid_sql = sa.text("select pg_current_xact_id()::text")

    def state(obj):
        st = sa.inspect(obj)
        return f"pk={obj.id}, transient={st.transient}, pending={st.pending}, persistent={st.persistent}"

    for change in (False, True):
        arm = "retry-changed" if change else "retry"
        print(f"sqlalchemy-{arm}: add() and flush() in a Session, the block raises; then"
              + (" value = 2 and" if change else "") + " add() and flush() again in a new Session")
        obj = SItem(arm=arm, value=1)
        try:
            with Session(engine) as s, s.begin():
                s.add(obj)
                s.flush()
                first = s.execute(xid_sql).scalar_one()
                raise AppError("the application fails after flush()")
        except AppError:
            pass
        report(witness, "first ", first)
        print(f"  after the rollback: {state(obj)}")
        if change:
            obj.value = 2
        with Session(engine) as s, s.begin():
            s.add(obj)
            s.flush()
            second = s.execute(xid_sql).scalar_one()
            pk = obj.id
        print(f"  the second Session committed normally, pk={pk}")
        report(witness, "second ", second)
        print(f"  {count(witness, 'sa_item', arm)}")

    for change in (False, True):
        arm = "savepoint-changed" if change else "savepoint"
        print(f"sqlalchemy-{arm}: in a Session's transaction, add() and flush() in begin_nested() that raises;"
              " the error is caught; then" + (" value = 2 and" if change else "") + " add() and flush() again")
        obj = SItem(arm=arm, value=1)
        with Session(engine) as s, s.begin():
            try:
                with s.begin_nested():
                    s.add(obj)
                    s.flush()
                    raise AppError("the application fails after flush()")
            except AppError:
                pass
            print(f"  after the savepoint rollback: {state(obj)}")
            if change:
                obj.value = 2
            s.add(obj)
            s.flush()
            outer = s.execute(xid_sql).scalar_one()
            print(f"  the second flush() returned normally, pk={obj.id}")
        report(witness, "outer ", outer)
        print(f"  {count(witness, 'sa_item', arm)}")
    engine.dispose()
    return sa.__version__


def main():
    print(f"python {platform.python_version()}, psycopg {psycopg.__version__}, {platform.system()} {platform.machine()}")
    with psycopg.connect(URL, autocommit=True, application_name="repro-admin") as admin:
        print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
        admin.execute(f"drop database if exists {NAME} with (force)")
        admin.execute(f"create database {NAME}")
    with psycopg.connect(conninfo(application_name="repro-witness"), autocommit=True) as witness:
        sqlalchemy_version = sqlalchemy_part(witness)
        django_version = django_part(witness)
    print(f"versions: Django {django_version}, SQLAlchemy {sqlalchemy_version}")
    with psycopg.connect(URL, autocommit=True, application_name="repro-admin") as admin:
        admin.execute(f"drop database {NAME} with (force)")


if __name__ == "__main__":
    main()
