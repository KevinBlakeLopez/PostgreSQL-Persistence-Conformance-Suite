"""CHK-3 setup: roles, database, schemas and tables, on the throwaway server only.

Usage: CHK3_APP_PASSWORD=<password> python -I chk3_setup.py

Connects as the superuser `postgres` to 127.0.0.1:55492; libpq reads the password from
PGPASSFILE. Creates the login role `app_login` (not a superuser), the NOLOGIN role
`tenant_a` granted to it, and database `chk3` with an `item` table in schemas `public` and
`tenant_s`. `item.inserted_by` defaults to current_user, so a witness can read which role
inserted a row, and the schema a row lands in shows the inserting session's search_path.
app_login's password comes from the environment, and is set with log_statement off so that
the server log never records it.
"""
import os

import psycopg
from psycopg import sql

HOST, PORT = "127.0.0.1", 55492
ADMIN = f"host={HOST} port={PORT} user=postgres application_name=chk3-setup"

with psycopg.connect(ADMIN + " dbname=postgres", autocommit=True) as c:
    c.execute("drop database if exists chk3")
    c.execute("drop role if exists app_login")
    c.execute("drop role if exists tenant_a")
    c.execute("create role app_login login nosuperuser")
    c.execute("create role tenant_a nologin")
    c.execute("grant tenant_a to app_login")
    c.execute("create database chk3 owner postgres")

with psycopg.connect(ADMIN + " dbname=chk3", autocommit=True) as c:
    c.execute("create schema tenant_s")
    for s in ("public", "tenant_s"):
        c.execute(f"create table {s}.item (name text not null, inserted_by name not null default current_user)")
    c.execute("grant usage, create on schema public, tenant_s to app_login, tenant_a")
    c.execute("grant select, insert on all tables in schema public, tenant_s to app_login, tenant_a")

with psycopg.connect(ADMIN + " dbname=postgres", autocommit=True) as c:
    c.execute("set log_statement = 'none'")
    c.execute(sql.SQL("alter role app_login password {}").format(sql.Literal(os.environ["CHK3_APP_PASSWORD"])))
    print("setup done:", c.execute("select rolname, rolsuper, rolcanlogin from pg_roles where rolname in "
                                   "('app_login', 'tenant_a') order by 1").fetchall())
