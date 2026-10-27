# Draft: asyncpg, new issue in MagicStack/asyncpg

**Filed 2026-10-27** as `KevinBlakeLopez`: https://github.com/MagicStack/asyncpg/issues/1402 The filed title and body match the text below; they were compared through the API. Prepared 2026-10-27. Written by: Cursor Grok 4.7.

**Revised 2026-10-27, after an outside adversarial review.** Verdict: READY WITH CHANGES. The review checked the saved artifacts and the cited sources. It did not rerun the program. Three published sentences were narrowed: diagnostic silence, the `init` prediction, and cleanup. The review is [`../adversarial-review/py6-asyncpg-reset-role/REVIEW.md`](../adversarial-review/py6-asyncpg-reset-role/REVIEW.md). The verdict is not permission to file.

This is tracker item PY-6 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It would be a new issue at https://github.com/MagicStack/asyncpg/issues/new. Do not add it to #1392.

**Proposed title:** `SET ROLE survives the default pool reset`

Everything between the two rules below is the proposed issue body. The rest of this file is internal.

**Before filing:**

1. Get approval of the exact title, body, and destination (`AGENTS.md` rule 9).
2. Search again for a duplicate: issues, pull requests, and discussions created after 2026-10-27. If one exists, comment there instead.
3. Re-check `master`. These should still hold, or the line numbers in the body should be corrected:
   - `master` was `13b01910da3fe01b8241c31cc86eccb1301a2d39` (2026-10-08, "Open 0.33.0 development");
   - `Connection.reset`'s summary is still `asyncpg/connection.py` lines 1570–1576;
   - `get_reset_query` still appends `RESET ALL;` at line 1785 and does not append `RESET ROLE`;
   - `create_pool`'s `reset` parameter still lists the four statements at `asyncpg/pool.py` lines 1329–1332;
   - `init` is still documented at `pool.py` lines 1312–1318.
4. Check PyPI. If a release after 0.32.0 exists, run `repro.py` on it three times before filing. The posted program has to be the program that was run.
5. Re-read #1293, #1392, and #270. If #1392 has started reviewing a role change, do not open a second issue.
6. Run the content guard on the final body. No checker for that guard is in this repository; the 2026-10-27 pass was a manual read of the body for a password, an internal path, the research id, and another project's name.
7. After filing, record the issue in `docs/upstream-submissions.md` and in the tracker. Check that file for another session's uncommitted edits first.

**Checks done 2026-10-27, about 13:00 UTC.** All read-only, with `gh`, PyPI, and the PostgreSQL 18 documentation and `REL_18_STABLE` sources.

- **PyPI `latest`:** 0.32.0. The run used that wheel (`asyncpg-0.32.0.dist-info`, installer `pip`, tag `cp313-cp313-macosx_11_0_arm64`). It was not built from source.
- **`master`:** `13b01910da3fe01b8241c31cc86eccb1301a2d39`. The `reset` docstring and `get_reset_query` text fetched from that commit match the installed 0.32.0 file at the same line numbers.
- **Duplicate search.** No report of `SET ROLE` surviving the pool reset. Queries over issues and pull requests: `RESET ROLE`, `SET ROLE pool`, `reset role release`, `session authorization reset`, `reset query role`, `SET ROLE reset`, `current_user reset`, `role survives`, `RESET ALL role`. The only hits were old and unrelated (#70, #87, #48, from the third query). A discussion search for `SET ROLE`, `RESET ROLE`, and `RESET ALL` did not return a role-reset report. Issues updated since 2026-10-24 were #1400 and #1391, neither of which is this.
- **Related, still open:** #1293 (temp tables, no comments, updated 2025-12-08). #1392 (open, not merged, updated 2026-10-14) adds capability-gated `DISCARD TEMP`. #270 (closed) declined `DISCARD ALL`.
- **No security policy or AI-policy file** was found at the asyncpg root or in `.github/` when this was last recorded (roadmap §9). That absence was not re-checked as a directory listing on 2026-10-27.
- **PostgreSQL 18 `SET ROLE`:** `doc/src/sgml/ref/set_role.sgml` on `REL_18_STABLE`. `RESET ROLE` sets the current user to the connection-time setting from command-line options, `ALTER ROLE`, or `ALTER DATABASE`, if one exists, and otherwise to the session user. Any user may run it. The `RESET` page says `RESET ALL` resets all settable run-time parameters; it does not mention the role. The `role` parameter is flagged `GUC_NO_RESET_ALL` in `src/backend/utils/misc/guc_tables.c` (the entry commented "used by SET ROLE").
- **psql, recorded 2026-10-24** in [`../../python-production-failure-gap-analysis/README.md`](../../python-production-failure-gap-analysis/README.md), not re-run today: `SET ROLE tenant_a; RESET ALL; SELECT current_user` returned `tenant_a`. `RESET ROLE` then returned `postgres`, that session's user.

**Evidence for the body.**

- **Program:** [`../py-6-asyncpg-reset-role/repro.py`](../py-6-asyncpg-reset-role/repro.py), SHA-256 `82ff6d85750bc5eec484af24102ba3e031d44b1dda1fb47ac405ac18d561314b`. The copy inside the body is that file.
- **Output:** `output/run.rep{1,2,3}.out` in that directory. Each file is that run's full stdout. SHA-256 `a917fb40ccf3fe639a982f0d88c555be440f08701a785920b21e9d68e9f942a7`, `834ef9d3d81b64d9b350c91bb748b8ecce5b82000e3c57666b8764bdd30fb893`, `6bf879e7b6bde304ba5160a727a7d83d86751911af015ecfacc29d6211d80b6b`. Exit 0. The users agreed. The backend pid was 93, then 103, then 113.
- **Server:** throwaway container `ppcs-py6-asyncpg-role-pg` on `127.0.0.1:55496`, image `postgres:18.6` digest `sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, tmpfs, random password, random `cluster_name` checked before the runs. Removed afterwards. `ppcs-postgres` was not used. After each run the repro database and the two roles were gone, and the role list and database list matched the lists from before the runs.
- **Host:** macOS 26.6.2, arm64. Python 3.13.11 from `adapters/tortoise/.venv`, invoked as `python -I`. asyncio only.

**Deliberately left out:**

- **Percolate.** Its changelog and `publisher()` describe this on a live database (commit `0d736a3269`). Naming that project in the asyncpg issue would be a public report about someone else's deployment. The outline does not include it.
- **CHK-6.** Not run. The body does not claim that `server_settings={'role': ...}` was measured, and it does not claim a custom `reset=` was tried.
- **The other session state from P2.** The GUC, `search_path`, statement timeout, advisory lock, and temp table are other checks. Temp tables are already #1293.
- **`DISCARD ALL`.** #270 declined it. The proposal is `RESET ROLE`, or a docstring correction.
- **A pull request.** The first step is the issue. The maintainers choose which change they want.

**Length.** Outside `<details>`: the template fields, the prose, and the one-line command. The program and the three outputs are inside `<details>`.

---

* **asyncpg version**: 0.32.0 (the quoted lines are unchanged on `master` `13b01910d`)
* **PostgreSQL version**: 18.6 (Debian 18.6-1.pgdg13+2), local Docker image `postgres:18.6`
* **Do you use a PostgreSQL SaaS?  If so, which?  Can you reproduce
  the issue with a local PostgreSQL install?**: No. A local Docker container.
* **Python version**: 3.13.11
* **Platform**: macOS 26.6.2, arm64
* **Do you use pgbouncer?**: No
* **Did you install asyncpg with pip?**: Yes, the wheel
* **If you built asyncpg locally, which version of Cython did you use?**: n/a
* **Can the issue be reproduced under both asyncio and
  [uvloop](https://github.com/magicstack/uvloop)?**: Reproduced under asyncio, three times. uvloop was not run.

`Connection.reset()` says it returns the session to a state resembling a newly obtained connection, and that session configuration variables are reset to their defaults. The pool documentation lists the statements the default reset runs:

```
SELECT pg_advisory_unlock_all();
CLOSE ALL;
UNLISTEN *;
RESET ALL;
```

Those statements do not include `RESET ROLE`. After a session-level `SET ROLE` is committed and the connection is released, the next checkout of the same backend still has the previous `current_user`. `session_user` is unchanged. The saved stdout contains both checkout results; no stderr or asyncpg diagnostic-log capture is included.

### Reproduction

Point `DATABASE_URL` at a disposable server. The user in that URL must be allowed to create a database and roles. The program creates database `ppcs_repro_asyncpg_role`, role `app_login` (`LOGIN`, with a random password that it does not print), and role `tenant_a` (`NOLOGIN`), grants `tenant_a` to `app_login`, and drops those objects on successful completion; interruption or cleanup failure can leave objects behind. The pool has one connection, logged in as `app_login`, and the call does not pass `reset=`.

```
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python repro.py
```

Three asyncio runs. The users agreed. The backend pid was 93, then 103, then 113, and the two checkouts in each run shared that pid.

<details>
<summary>output</summary>

```
asyncpg 0.32.0
server PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
checkout 1 current_user=tenant_a session_user=app_login backend_pid=93
checkout 2 current_user=tenant_a session_user=app_login backend_pid=93

asyncpg 0.32.0
server PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
checkout 1 current_user=tenant_a session_user=app_login backend_pid=103
checkout 2 current_user=tenant_a session_user=app_login backend_pid=103

asyncpg 0.32.0
server PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
checkout 1 current_user=tenant_a session_user=app_login backend_pid=113
checkout 2 current_user=tenant_a session_user=app_login backend_pid=113
```

</details>

<details>
<summary>repro.py</summary>

```python
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
```

</details>

### PostgreSQL

In psql on PostgreSQL 18.6, `SET ROLE tenant_a; RESET ALL; SELECT current_user` returned `tenant_a`. `RESET ROLE` then returned `postgres`, that session's user.

PostgreSQL 18's `SET ROLE` page says `RESET ROLE` sets the current user identifier to the connection-time setting from command-line options, `ALTER ROLE`, or `ALTER DATABASE`, if one exists, and otherwise to the session user. Any user may run it. The server flags the `role` parameter `GUC_NO_RESET_ALL` (`src/backend/utils/misc/guc_tables.c`, the entry used by `SET ROLE`, on `REL_18_STABLE`).

A pool created with `server_settings={'role': ...}` was not run.

### Documentation

`Connection.reset` (`asyncpg/connection.py`, lines 1570–1576) says:

> Calling this will reset the connection session state to a state resembling that of a newly obtained connection. [...] all session configuration variables are reset to their default values

The same docstring says that description is the default query from `get_reset_query`. `create_pool(reset=)` (`asyncpg/pool.py`, lines 1326–1332) lists the four statements above.

Checkout 2's `current_user` was `tenant_a`. `session_user` stayed `app_login`, the role the pool logged in as.

### What would you like to change?

1. Append `RESET ROLE` to the default reset query, behind a server capability, as #1392 does for `DISCARD TEMP`, and update the docstring and the pool docs.
2. Or correct the docstring and the pool description so they do not say that every session configuration variable is reset, and document a `reset=` callback that adds `RESET ROLE`.

This is not a suggestion to use `DISCARD ALL`. #270 declined that.

A role set in `init` is applied once, when the connection is created. `init` is documented with type codecs as an example (`pool.py`, lines 1312–1318). For a reusable connection, source reading predicts that a committed session-level `SET ROLE` in `init` survives the current default reset unless later code changes it. Adding `RESET ROLE` would instead restore the connection-time role setting, or the session user if no such setting exists; it need not change `current_user` when the init-time role already equals that default. These init-time cases were not run. An application that wants the role on every checkout can set it in `setup`, which runs before `Pool.acquire()` returns the connection.

#1293 and #1392 are about temporary tables that survive this reset. #1392 is open and not merged. Neither covers `SET ROLE`.

---
