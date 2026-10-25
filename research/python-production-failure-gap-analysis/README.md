# Premise probes for the Python production-failure gap analysis

Run on 2026-10-24. Written by: Claude Opus 5.5 (max).

These programs checked the runtime facts that the ranking in [`../python-production-failure-gap-analysis.md`](../python-production-failure-gap-analysis.md) depends on. They are **premise probes, not PPCS cases**:

- they run outside `harness/`, so no CTL-01 or `pg-control` gate applies;
- the witness is each script's own autocommit connection, not the runner's observer;
- every result was repeated three times, and every repetition agreed.

Nothing here changes an adapter, the harness, a specification, or a recorded result.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6, `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest). A throwaway container, `ppcs-gap-probe-pg`, on `127.0.0.1:55483`, with a tmpfs data directory, `log_statement=all`, and `cluster_name=ppcs-gap-probe`. Not `ppcs-postgres` |
| Server settings that matter | `synchronous_commit` on; `statement_timeout`, `idle_in_transaction_session_timeout`, and `client_connection_check_interval` all 0; `deadlock_timeout` 1 s; `default_transaction_isolation` read committed |
| Host | macOS arm64, colima (aarch64 VM), Python 3.13.11 |
| Main virtualenv | asyncpg 0.32.0, SQLAlchemy 2.1.5, greenlet 3.5.6, psycopg 3.3.6 (binary implementation, libpq 18.6; corrected 2026-10-24 from "18.0.6", a misreading of psycopg's `180006`), psycopg-pool 3.3.3, Django 6.1.2, tortoise-orm 1.1.9 (pypika-tortoise 0.6.5), anyio 4.15.1. Installed with `pip install --only-binary=:all:` |
| Second virtualenv | The same packages, with SQLAlchemy 2.1.6, released 2026-10-21. Used only for `output/p3c-sa216.jsonl` |

These are PPCS's pinned versions for Django, SQLAlchemy, psycopg, Tortoise and asyncpg. psycopg-pool and anyio are not PPCS dependencies.

## Setup

1. Write the container's password to `.pgpass_token` in this directory. The scripts read it from there. Do not commit it.
2. Create the roles and the first database:

   ```sql
   create role app_login login;
   create role tenant_a nologin;
   grant tenant_a to app_login;
   create database probe owner postgres;
   ```

3. Know what each script creates for itself:
   - `p2` creates `probe2`, and gives `app_login` the probe-only password that is in the script;
   - `p3`, `p45` and `p6` create `probe3`, `probe45` and `probe6`;
   - `p7` reuses `probe2`.

Every script connects only to `127.0.0.1:55483`, a constant in each file. `p1` also asserts it.

## Programs, commands and outputs

Run every command from this directory, with `-I`.

| Program | What it checks | Command | Output |
| --- | --- | --- | --- |
| `p1_commit_tag.py` | A caught `23505`, then the normal completion, across asyncpg, SQLAlchemy Core and ORM on asyncpg, and ORM on psycopg (`Session.execute()` error and flush error) | `python -I p1_commit_tag.py` (three repetitions inside) | `output/p1.out` |
| `p2_session_state.py` | Session state from one unit of work, seen by the next unit on a pool of size 1, across six pool flavours | `python -I p2_session_state.py`, three times | `output/p2.rep{1,2,3}.out` |
| `p3_cancellation.py` | `task.cancel()` or `anyio.CancelScope.cancel()` while COMMIT, or a body statement, waits on a server-side gate; then the next unit of work | `python -I p3_cancellation.py <subject> <commit\|body> <edge\|level\|none> <rep>` | `output/p3.jsonl`, `output/p3b.jsonl`, `output/p3c-sa216.jsonl` |
| `p45_commit_error_and_retry.py` | A COMMIT that PostgreSQL rejects (deferred FK), in Django and Tortoise; then a retried `save()` of the same instance after a rollback, in Tortoise, Django and SQLAlchemy | `python -I p45_commit_error_and_retry.py`, three times | `output/p45.rep{1,2,3}.out` |
| `p6_other_sqlstates.py` | `57014`, `40P01` and `40001`, produced by PostgreSQL at statement level and caught, then the normal completion | `python -I p6_other_sqlstates.py <sa-core\|django\|asyncpg\|tortoise> <57014\|40P01\|40001> <rep>` | `output/p6.jsonl` |
| `p7_sa_reset_recipe.py` | SQLAlchemy's documented PostgreSQL reset-on-return recipe on psycopg 3, against a rollback followed by `DISCARD ALL` in autocommit | `python -I p7_sa_reset_recipe.py`, three times | `output/p7.rep{1,2,3}.out` |
| `p6_log_endings.py` | For each P6 run, the transaction-control statements its subject session sent, read from the server's statement log (`log_statement=all`) | `docker logs ppcs-gap-probe-pg > server.log 2>&1`, then `python -I p6_log_endings.py server.log` | `output/p6.server-log-endings.txt` |

**The server log itself is not kept.** It is large, and it records the probe-only `ALTER ROLE … PASSWORD` statement.

**How the P3 outputs were produced:**

- **`p3.jsonl`:** all 60 combinations of subject, gate, style and repetition.
- **`p3b.jsonl`:** the Tortoise rows again, plus the `none` control for every subject, with 3 repetitions each.
- **`p3c-sa216.jsonl`:** the two SQLAlchemy subjects, COMMIT-gated, both styles, from the second virtualenv.

## Two psql checks

These were run in the same container. Their output is quoted, not saved as files.

**1. `RESET ALL` and session state.**

Statements:

- `set role tenant_a; reset all; select current_user;`

  The result was `tenant_a`. `reset role` then returned `postgres`.
- `set session authorization app_login; reset all;`

  `current_user` and `session_user` stayed `app_login`.
- After `set app.tenant_id = '42'`, `set search_path = 'other, public'` and `set statement_timeout = '1234ms'`, a `reset all` cleared all three.
- A temp table survived asyncpg's whole reset sequence: `SELECT pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;`.
- `begin; select pg_advisory_lock(777); rollback;` left one advisory lock held.
- Inside a transaction already aborted by `select 1/0`, `select pg_advisory_unlock(777)` failed with "current transaction is aborted". The lock was still held after `ROLLBACK`.
- `set role tenant_a; discard all; select current_user;` returned `postgres`.

**2. A COMMIT held by a deferred foreign key.**

- **The setup.** The table `child` has `parent_id int references parent(id) deferrable initially deferred`.
- **The runner.** Session 1 ran `begin; select * from parent where id=1 for update; select pg_sleep(3); commit;`.
- **The subject.** Session 2 ran `begin; insert into child(parent_id) values (1); commit;`.
- **During the wait,** `pg_stat_activity` showed session 2 as `active`, `Lock` / `transactionid`.
- **The outcome.** Session 2's COMMIT returned about 2.5 s later, when session 1 committed, and the row was committed. Django 6.1.2 creates every foreign key this way: `deferrable_sql()` in `django/db/backends/postgresql/operations.py`, lines 150–151.

## Changes between attempts

The scripts here are the versions that produced the outputs listed. Earlier attempts are recorded below rather than hidden.

- **`p2_session_state.py`, first attempt.** All six flavours used one advisory-lock key.
  - Django's persistent connection kept request 1's session lock.
  - The pooled alias's `pg_advisory_lock` then waited 54.3 s. It was cancelled by the `statement_timeout = '54321'` that request 1 had also set, with "canceling statement due to statement timeout".
  - That attempt produced no output file.
  - The script now gives each flavour its own key. The three outputs come from the current version.
- **`p3_cancellation.py`.** `output/p3.jsonl` came from an earlier version.
  - Its 12 Tortoise rows say `"crashed": true`. Tortoise requires a model module: "AppConfig.models must be a non-empty list of strings".
  - The script then gained two things: a trivial Tortoise model registered from `__main__`, and the `none` control style.
  - Neither change touches the asyncpg, psycopg or SQLAlchemy subjects.
  - `output/p3b.jsonl` and `output/p3c-sa216.jsonl` come from the current version.
- **`p45_commit_error_and_retry.py`, first attempt.** It stopped in the setup helper, on `fetchall()` after DDL, before any measurement. The helper now fetches only when there are rows. The three outputs come from the current version.
- **`p1`, `p6` and `p7`** did not change.

## SHA-256

```text
fa8d8b96edc4e5644fd2c5027f4d68e0ee7641dcf33a8a086f1cf2b9cb9dbcf7  p1_commit_tag.py
187fb0884189475010f81e90b2751c01d21eff80e89af98157aa21e950126e3e  p2_session_state.py
63a46517fcb691ff1871da6202e8eda889ecdbf142763327caf97940d7a601a3  p3_cancellation.py
3fe9321631c88e3ecc1716257db224fd6365d25450fd8c3368b87ca1ea571ffb  p45_commit_error_and_retry.py
26c7fbcc87a867b9732aa8454e3369f0a9f5508aa87ddced0aff6713bb3d8f98  p6_other_sqlstates.py
38bfd0cd18e1226d96411e1afb060807c56b67e27a3b0b30d41cbdfad91e6793  p7_sa_reset_recipe.py
0e23b790cf93b71c1caebd34247ae7a1da54ceb4dc9feaa4d1101ada19f9a9af  p6_log_endings.py
a88c677f71e35aba783514961ce6986984aaf23f8c2d7093dc93a4723ddd9ec0  output/p6.server-log-endings.txt
f48c938ae1c5f4241d95925730dda221fb22c2ca7f95f2642decd331c4ee40ec  output/p1.out
8e79cc1bee53c70df7309bce9b71ccf97138c302a40cbdf6c9e379e80c6fffdd  output/p2.rep1.out
8e79cc1bee53c70df7309bce9b71ccf97138c302a40cbdf6c9e379e80c6fffdd  output/p2.rep2.out
8e79cc1bee53c70df7309bce9b71ccf97138c302a40cbdf6c9e379e80c6fffdd  output/p2.rep3.out
8d26e8899d8bcb463809f59e40080e0a6a097033306e07462ef71a5c7c114cc6  output/p3.jsonl
18aceeab95109a09956406d85d177ffc8018c8927fd6f3ebb74d6527856995ca  output/p3b.jsonl
9af9d1e403303b0bd7efc054208e56d10a09fae386f8155b071d30d6be879405  output/p3c-sa216.jsonl
1e2aa3ce36c87560fb75f27a7d5e8550dcd77f266d7a4869a053e1dd28f6af65  output/p45.rep1.out
1e2aa3ce36c87560fb75f27a7d5e8550dcd77f266d7a4869a053e1dd28f6af65  output/p45.rep2.out
1e2aa3ce36c87560fb75f27a7d5e8550dcd77f266d7a4869a053e1dd28f6af65  output/p45.rep3.out
760f4fc37f07260b502e76018a5273faf99ad002b25a9e10d133968d84e62405  output/p6.jsonl
ee6f3ec061d547caf7129ca6ca85d4d87531387b9f19dd9ff96973fc7627bdec  output/p7.rep1.out
ee6f3ec061d547caf7129ca6ca85d4d87531387b9f19dd9ff96973fc7627bdec  output/p7.rep2.out
ee6f3ec061d547caf7129ca6ca85d4d87531387b9f19dd9ff96973fc7627bdec  output/p7.rep3.out
```

Identical hashes across repetitions mean the repetitions printed byte-identical output. That is expected here, because the outputs hold no transaction IDs, PIDs, or timestamps.

## P8, added 2026-10-25

[`p8-uvicorn-shutdown/`](p8-uvicorn-shutdown/README.md) holds P8: Uvicorn's graceful-shutdown timeout expiring while a SQLAlchemy `AsyncSession` COMMIT waits at P3's gate. It ran on 2026-10-24, after the report, in its own container, `ppcs-gap-uvicorn-pg`, not the one above. Its README has its own environment, commands, results and SHA-256 list; the list above does not cover it.
