"""Show the session role after asyncpg's default pool reset.

Reads the admin URL from DATABASE_URL and exits if it is unset. Connects to
the database named in that URL only to create, and later drop, database
ppcs_repro_asyncpg_role and roles app_login and tenant_a. app_login can log
in and receives a random password, which is not printed. tenant_a cannot log
in. app_login is granted tenant_a.

Opens an asyncpg pool of one connection as app_login and does not pass
reset=, so release uses the pool's default reset. Checkout 1 sets the role
to tenant_a, reads current_user and session_user, and commits. Releasing
that connection runs the default reset. Checkout 2 reads current_user,
session_user, and the backend pid.

Prints the installed asyncpg version, SELECT version(), both checkouts'
users, and both backend pids.

    DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/postgres python repro.py
"""

import asyncio
import os
import secrets
import sys
import urllib.parse

import asyncpg

REPRO_DB = "ppcs_repro_asyncpg_role"
LOGIN = "app_login"
TENANT = "tenant_a"


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def database_name(url):
    name = urllib.parse.urlsplit(url).path.lstrip("/")
    if not name or "/" in name:
        sys.exit("DATABASE_URL must name one database")
    return name


def require_admin_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is unset")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("postgresql", "postgres"):
        sys.exit("DATABASE_URL must be a postgresql URL")
    if database_name(url) == REPRO_DB:
        sys.exit(f"DATABASE_URL names {REPRO_DB}; refusing")
    if not parts.hostname:
        sys.exit("DATABASE_URL has no host")
    return url


def app_dsn(admin_url, password):
    parts = urllib.parse.urlsplit(admin_url)
    host = parts.hostname
    if ":" in host:
        host = f"[{host}]"
    user = urllib.parse.quote(LOGIN, safe="")
    secret = urllib.parse.quote(password, safe="")
    netloc = f"{user}:{secret}@{host}"
    if parts.port is not None:
        netloc += f":{parts.port}"
    return urllib.parse.urlunsplit((parts.scheme, netloc, f"/{REPRO_DB}", parts.query, ""))


def redact(text, secrets_):
    for secret in secrets_:
        if secret:
            text = text.replace(secret, "***")
            text = text.replace(urllib.parse.quote(secret, safe=""), "***")
    return text


async def setup(admin_url, password, created):
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f"CREATE DATABASE {REPRO_DB}")
        created["db"] = True
        await admin.execute(f"CREATE ROLE {LOGIN} LOGIN PASSWORD {sql_literal(password)}")
        created["login"] = True
        await admin.execute(f"CREATE ROLE {TENANT} NOLOGIN")
        created["tenant"] = True
        await admin.execute(f"GRANT {TENANT} TO {LOGIN}")
        created["grant"] = True
    finally:
        await admin.close()


async def drop_created(admin_url, created):
    if not any(created.values()):
        return
    admin = await asyncpg.connect(admin_url)
    try:
        if created["db"]:
            await admin.execute(f"DROP DATABASE {REPRO_DB} WITH (FORCE)")
        if created["grant"]:
            await admin.execute(f"REVOKE {TENANT} FROM {LOGIN}")
        if created["login"]:
            await admin.execute(f"DROP ROLE {LOGIN}")
        if created["tenant"]:
            await admin.execute(f"DROP ROLE {TENANT}")
    finally:
        await admin.close()


async def demonstrate(pool):
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        # Commit before release. reset() rolls an open transaction back
        # before it runs the default reset query, which would undo SET ROLE.
        async with conn.transaction():
            await conn.execute("SET ROLE tenant_a")
            checkout1 = await conn.fetchrow("SELECT current_user, session_user")
            pid1 = await conn.fetchval("SELECT pg_backend_pid()")
    async with pool.acquire() as conn:
        checkout2 = await conn.fetchrow(
            "SELECT current_user, session_user, pg_backend_pid()"
        )
    print(f"asyncpg {asyncpg.__version__}", flush=True)
    print(f"server {version}", flush=True)
    print(
        f"checkout 1 current_user={checkout1[0]} session_user={checkout1[1]} backend_pid={pid1}",
        flush=True,
    )
    print(
        f"checkout 2 current_user={checkout2[0]} session_user={checkout2[1]} backend_pid={checkout2[2]}",
        flush=True,
    )


async def run(admin_url):
    password = secrets.token_hex(24)
    admin_password = urllib.parse.urlsplit(admin_url).password or ""
    hidden = (password, admin_password, admin_url)
    created = {"db": False, "login": False, "tenant": False, "grant": False}
    pool = None
    failure = None
    try:
        await setup(admin_url, password, created)
        # No reset= argument: release uses asyncpg's default reset.
        pool = await asyncpg.create_pool(
            app_dsn(admin_url, password), min_size=1, max_size=1
        )
        await demonstrate(pool)
    except Exception as exc:
        failure = redact(f"{type(exc).__name__}: {exc}", hidden)
    if pool is not None:
        try:
            await pool.close()
        except Exception as exc:
            closed = redact(f"pool close failed: {type(exc).__name__}: {exc}", hidden)
            failure = f"{failure}\n{closed}" if failure else closed
    try:
        await drop_created(admin_url, created)
    except Exception as exc:
        cleaned = redact(f"cleanup failed: {type(exc).__name__}: {exc}", hidden)
        failure = f"{failure}\n{cleaned}" if failure else cleaned
    if failure:
        raise SystemExit(failure)


def main():
    admin_url = require_admin_url()
    asyncio.run(run(admin_url))


if __name__ == "__main__":
    main()
