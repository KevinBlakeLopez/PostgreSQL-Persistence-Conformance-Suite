# Connection-pool session-state contamination

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

**Status.** A research investigation outside the PPCS harness (`AGENTS.md` rule 11). It changes no adapter, harness file, specification, catalog or recorded result. Nothing was filed or posted. The two upstream texts in [`upstream-drafts/`](upstream-drafts/) are drafts that need approval of their exact wording.

**The question.** Can a connection pool return a PostgreSQL session to another borrower while it keeps state that the pool's own documented reset, cleanup or isolation guarantees say it should not keep? The highest priority was cleanup that fails, is cancelled, times out or is interrupted, followed by reuse of the same physical session.

**Evidence labels**

| Label | Meaning |
| --- | --- |
| **Observed** | A recorded run in [`output/`](output/), three repetitions, byte-identical |
| **Log** | The server's statement log, read through [`analysis/server_log_sequences.py`](analysis/server_log_sequences.py) |
| **Src** | Source reading of the stated version, with file and line. Not a runtime observation |
| **Doc** | Documentation, quoted, fetched 2026-10-24 |
| **Upstream** | Issue-tracker state on 2026-10-24 |
| **Judg** | This report's judgment. Not evidence |

## 1. Executive summary

**One new, confirmed defect, F-H2, in HikariCP.**

- **What happens.** When HikariCP's state reset on `close()` throws an `SQLException` with a SQLState it does not treat as a disconnection, `close()` rethrows it but still returns the connection to the pool. The next borrower gets the connection with the reset undone and the remaining reset steps skipped.
  - Src: `ProxyConnection.close()`, `finally { poolEntry.recycle(); }`.
- **A natural trigger exists with pgjdbc, and needs no fault injection.**
  - In non-autocommit mode, pgjdbc's `getSchema()`, `setSchema()` and `setSavepoint()` run SQL that begins a transaction.
  - HikariCP's commit-state tracking doesn't count those calls, so `close()` skips its rollback.
  - pgjdbc then rejects HikariCP's `setTransactionIsolation()` or `setReadOnly()` reset with SQLSTATE `25001`, because a transaction is open.
- **Observed consequences** (3 of 3 each; pool of one; independent observer and server log):
  - **The next borrower runs inside the previous borrower's transaction.** It is SERIALIZABLE although the pool is configured READ COMMITTED, and the borrower reads the previous borrower's snapshot: a value an observer committed in between is invisible. A third borrower still gets SERIALIZABLE.
  - **A cross-schema write.** With `schema=public` configured and `setSchema("tenant_a")` as the previous borrower's last call, the next borrower's committed unqualified insert lands in `tenant_a`.
  - **A poisoned connection on default settings** (`autoCommit=true`, `readOnly=false`). A read-only report that logs `getSchema()` after its `commit()` leaves the connection with autocommit off and read-only on.
    - Each of three later borrowers has its insert fail (`25006`, then `25P02`).
    - HikariCP's alive check passes every time.
- **Versions.** Reproduced with an unchanged single-file program on HikariCP 4.0.3, 5.1.0, 6.3.3, 7.0.2 and 7.1.0 (identical output). `dev` is unchanged.
- **A one-line correction is validated.** When the rollback or reset throws, mark the entry evicted.
  - **The probes:** with the fix, every failing scenario hands the next borrower a fresh connection with the pool's defaults. Both controls produce byte-identical output with and without the fix.
  - **A new regression test** in HikariCP's own suite fails on 7.1.0 and passes with the change. The rest of the suite is unchanged.
  - **A configuration-only workaround works today:** an `SQLExceptionOverride` that evicts on `25001`.
- **Prior art.** In 2017 (#1009) HikariCP's maintainer wrote that the reset calls should not fail in a way that avoids eviction, and asked for a concrete example. This is one. The draft issue is [`upstream-drafts/hikaricp-failed-reset-recycled.md`](upstream-drafts/hikaricp-failed-reset-recycled.md).

**Known upstream issues, reproduced and not new.** HikariCP does not restore a schema set through `setSchema()` unless `schema` is configured (#2081). With `autoCommit=false`, pgjdbc's `setSchema()` begins a transaction (pgjdbc#3005), so:

- HikariCP's configured-schema setup is lost at the first rollback (#1369, #1633, #2235);
- its schema reset on close is undone by the next borrower's rollback (#2144).

These are reproduced here, and will not be re-filed.

**Defensible negative results for the other pools (Outcome B).** asyncpg, SQLAlchemy (sync and async), psycopg_pool and Npgsql never handed the next borrower an unreset session after a cleanup that failed, timed out, was cancelled, or met a terminated backend. Each terminated, invalidated, discarded or broke the connection, or completed the cleanup before reuse (Observed, 3 of 3 each).

**Documented behaviour worth knowing, not defects:**

- **Npgsql's documented lazy reset** sends `DISCARD ALL` with the next borrower's first statement. Until then, an idle pooled connector still holds the previous borrower's session advisory locks and temp tables: a competing session could not take the lock.
- **asyncpg, after a reset timeout,** closes the socket without a cancel request. The server session keeps running its statement, and keeps its advisory locks, until that statement ends.
- **node-postgres resets nothing.** Releasing a client with a transaction open hands that transaction to the next borrower, whose "autocommit" insert is then lost. That is application misuse under its documentation.

**Security significance.** F-H2 and the known schema issues can put one borrower's unqualified writes into another schema. Whether that crosses a tenant boundary depends on the application, and no unauthorized access was demonstrated. The clearest security-relevant item in this area remains the earlier finding PY-6: asyncpg's reset leaves `SET ROLE` in place.

## 2. Scope, prior work and coordination

**Already covered before this study** (not redone):

- the gap analysis §7.2 and probe P2 (normal-release session state across six Python pools);
- PY-6 (asyncpg `SET ROLE` survives `reset()`);
- PY-5 (SQLAlchemy's documented reset recipe);
- PY-7 (SQLAlchemy P5a, failed commit then `close()`);
- PPCS family TX-03 (a failed `ROLLBACK` on a pooled connection, injected client-side).

This study adds the failure paths of cleanup itself, and adds the JVM, .NET and Node pools.

**The concurrent investigation** of transaction hooks after a false commit success was not touched. This study worked only in its own worktree (`../ppcs-session-state-contamination`, branch `research/ppcs-session-state-contamination` from local `main` `4442ae2`) and its own PostgreSQL container (`ppcs-ssc-pg`, port 55473). The cross-investigation observation is §12.

## 3. Subjects, versions and environment

| Subject | Version | Why |
| --- | --- | --- |
| PostgreSQL | 18.6 (`postgres:18.6@sha256:74935e72…c4336`, PPCS's pin) | |
| HikariCP | 7.1.0 (latest release, 2026-06-14); 4.0.3, 5.1.0, 6.3.3, 7.0.2 for the minimal reproduction | PPCS's JVM pooled modes use 7.1.0 |
| PostgreSQL JDBC (pgjdbc) | 42.7.14 (latest release, 2026-10-07) | PPCS pin |
| asyncpg | 0.32.0 | PPCS pin |
| SQLAlchemy | 2.1.6, with greenlet 3.2.4 | Latest; includes the fix for #13699 |
| psycopg / psycopg_pool | 3.3.6 / 3.3.3 | PPCS pins |
| Npgsql | 10.0.3 | PPCS pin |
| node-postgres | pg 8.23.1, pg-pool 3.14.0 | PPCS pin |
| Django | 6.1.2, source only | PPCS pin |

**Runtimes and toolchain.** Python 3.13.11; OpenJDK 21.0.12.1 (Homebrew), with Maven 3.10.0; .NET SDK 10.0.402 and runtime 10.0.13; Node v24.14.1. Everything ran on macOS 26.6.2 (arm64), with Docker through colima. Python pins: [`python/requirements.lock.txt`](python/requirements.lock.txt). Java pins: [`hikari/pom.xml`](hikari/pom.xml). .NET pins: [`npgsql/packages.lock.json`](npgsql/packages.lock.json). Node pins: [`node/package-lock.json`](node/package-lock.json).

## 4. Documented reset contracts

| Pool | What it documents | Source |
| --- | --- | --- |
| HikariCP | No reset section. Its properties describe the state of connections from the pool: `autoCommit` "controls the default auto-commit behavior of connections returned from the pool"; `readOnly`: "whether Connections obtained from the pool are in read-only mode by default"; `transactionIsolation` "controls the default transaction isolation level of connections returned from the pool. If this property is not specified, the default transaction isolation level defined by the JDBC driver is used"; `schema` "sets the default schema … If this property is not specified, the default schema defined by the JDBC driver is used". The maintainer, in #2200 (2024-11-22): HikariCP is "ensuring that configured defaults such as transaction isolation, schema, etc. are reset when a connection is returned to the pool". | Doc: README at tag `HikariCP-7.1.0`; Upstream: #2200 |
| HikariCP, implementation | It tracks JDBC API calls only. It resets read-only, autocommit, isolation, catalog (only if configured), network timeout and schema (only if configured). It rolls back only when autocommit is off and a statement ran through the proxy (`isCommitStateDirty`). Isolation is reset to the driver default captured at startup when unconfigured; schema and catalog are not. | Src: `PoolBase.resetConnectionState` 213–249, `checkDefaultIsolation` 501–515, `ProxyConnection.close` 240–270 |
| asyncpg | `Pool(reset=…)`: "The function is supposed to reset any changes made to the database session so that the next acquirer gets the connection in a well-defined state. The default implementation calls `Connection.reset()`, which runs `SELECT pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;`". `Connection.reset()`: "reset the connection session state to a state resembling that of a newly obtained connection. Namely, an open transaction (if any) is rolled back, open cursors are closed, all LISTEN registrations are removed, all session configuration variables are reset to their default values, and all advisory locks are released." A failed or cancelled reset terminates the connection. | Doc/Src: `pool.py` 1320–1337, `connection.py` 1567–1594; Src: `pool.py` holder `release()` |
| SQLAlchemy | `reset_on_return='rollback'`: the DBAPI connection is rolled back on return. Other session state ("temporary tables as well as other server state") is not reset; a `PoolEvents.reset` recipe is offered (PY-5). | Doc: PostgreSQL dialect docs, `dialects/postgresql/base.py` 275–336 |
| psycopg_pool | On return, a connection inside a transaction is rolled back, and discarded if that fails. The `reset` callback is the user's; a connection it leaves outside the idle state is discarded. | Doc and Src: `pool_async.py` 871–911 |
| Django 6.1.2 | Native pool: psycopg_pool with a `configure` hook (time zone, `assume_role`) that runs only on new physical connections. No `reset` unless the user passes one. Persistent connections (`CONN_MAX_AGE`) are reused per thread, closed when autocommit differs from the setting or `is_usable()` fails after errors. | Src: `db/backends/postgresql/base.py` 194–236, 381–391; `base/base.py` `close_if_unusable_or_obsolete` |
| Npgsql | "When a pooled connection is closed, Npgsql will arrange for its state to be reset the next time it's used … via `DISCARD ALL` … or, if there are any prepared statements at the time of closing, by a combination of the equivalent statements … these statements aren't actually sent when closing the connection … and will be sent with the first user statement after the connection is reopened." `No Reset On Close`: "at the cost of leaking state". A failed prepended reset breaks the connector. | Doc: `performance.md`, `connection-string-parameters.md`; Src: `NpgsqlConnector.Reset` 2711–2777, `ReadMessageLong` 1660–1690 |
| node-postgres | "The `release` method … returns it back to the pool. If you pass a truthy value in the `destroy` parameter … the pool will … disconnect and destroy this client." Transactions: "node-postgres strives to be low level and un-opinionated, it doesn't provide any higher level abstractions specifically around transactions." No reset. | Doc: `docs/pages/apis/pool.mdx`, `features/transactions.mdx`; Src: `pg-pool/index.js` `_release` 384–429 |

## 5. PostgreSQL baseline (Phase 2)

[`baseline/pg_session_baseline.py`](baseline/pg_session_baseline.py): one physical session, an independent observer (pg_stat_activity, pg_locks, catalogs), and a competing connection. Observed, 3 of 3, `d83e849b…`.

Each cell is observed unless it says "not tested". "Persists" means it is still in effect for the session's later transactions.

| Category | Persists after COMMIT | After ROLLBACK of the transaction that set it | After `RESET ALL` | After `DISCARD ALL` |
| --- | --- | --- | --- | --- |
| `application_name`, `search_path` | yes | reverted (also after a failed statement) | reset | reset |
| Custom GUC (`set_config(…, false)`), `statement_timeout`, `SET SESSION CHARACTERISTICS` | yes | not tested | reset (a custom GUC reads `''`, not undefined) | not tested |
| `SET ROLE` | yes | reverted | **kept** | reset |
| `SET SESSION AUTHORIZATION` (superuser session) | yes | not tested | **kept** | reset |
| Session advisory lock | yes | **kept**, even one taken inside the rolled-back transaction; reentrant for the same session | kept | released |
| Temp table | yes | creation undone | kept | dropped |
| LISTEN | yes | not registered (LISTEN takes effect at commit) | kept (a notification is still delivered) | removed |
| SQL `PREPARE` | yes | **kept**, even one made inside the rolled-back transaction | kept | deallocated |
| WITH HOLD cursor | yes | — | kept (`CLOSE ALL` closes it) | not tested |
| `SET LOCAL` | no | no | — | — |

Also observed:

- `pg_advisory_unlock_all()` inside an aborted block fails with `25P02`.
- An unqualified insert with a temp table named `item` goes to the temp table.
- A second `BEGIN` on an open transaction only warns (`25001`), and the next unit's `COMMIT` commits the earlier unit's row (`pg_xact_status` committed).
- A terminated session's replacement starts clean.
- A read-only session default (`default_transaction_read_only = on`) does not stop `CLOSE ALL`, `UNLISTEN *`, `RESET ALL` or `pg_advisory_unlock_all()` (psql check).

## 6. Method

- **Pool of one** physical connection everywhere, and consecutive borrowers A, B, C…
- **Physical identity.** The backend PID the driver reports from BackendKeyData (no SQL), plus that backend's `backend_start` as the observer reads it. "Same backend" requires both.
- **Independent observation.** A separate superuser connection outside the pool reads:
  - `pg_stat_activity` (state, `xact_start`, `backend_xmin`);
  - `pg_locks`;
  - the catalogs;
  - the table a row actually landed in. Each schema's `item` has `inserted_by DEFAULT current_user`, so a row also shows the role it was written as.
  - A competing connection tests advisory locks, because the holding session can always reacquire its own lock.
- **The server's statement log.** `log_statement=all`, with `%v` (virtual transaction ID) in every line, so "B ran inside A's transaction" can be read off the log. [`analysis/server_log_sequences.py`](analysis/server_log_sequences.py) groups each backend's statements by vxid and masks IDs. [`output/server-log/`](output/server-log/) has the full log (`server.log.gz`, no passwords: checked) and per-family extracts. The extracts include probe-development runs, made before a probe was corrected, as extra distinct sequences.
- **Controls.**
  - **Positive:** the documented reset clears what it promises, for example `iso-reset`, `schema-configured` and asyncpg `normal-release`.
  - **Negative:** PostgreSQL keeps state without a reset (the baseline), and Npgsql `No Reset On Close`.
  - **Failure:** the cleanup is shown to fail, for example the exception from `close()` and the reset statement missing from the log.
  - **Recovery:** a replacement connection is clean, for example `reset-fails-configured-evicted` and the patched runs.
- **Faults.** Most triggers are ordinary API calls, with no injection: HikariCP's `getSchema()`/`setSchema()`/`setSavepoint()`, a cancelled task, a raised exception. Two kinds are artificial and labelled as such:
  - the observer terminating a backend with `pg_terminate_backend` (PPCS category B);
  - custom reset callbacks that sleep or raise, to widen the cancellation and timeout windows (client-side, category C).
- **Repetitions.** Every scenario ran three times. The outputs contain no PIDs, timestamps or transaction IDs, so repetitions are compared by SHA-256. All repetitions agreed. The HikariCP scenarios were re-recorded after each change to the probe, two to four times each, and every recording was byte-identical to the earlier ones. [`results-matrix.md`](results-matrix.md) is generated from the outputs and carries each scenario's hash.

## 7. Results by pool

The full matrix is [`results-matrix.md`](results-matrix.md). The highlights:

### 7.1 HikariCP 7.1.0 with pgjdbc 42.7.14

Probe: [`hikari/src/main/java/ssc/HikariProbe.java`](hikari/src/main/java/ssc/HikariProbe.java), run with [`hikari/run.sh`](hikari/run.sh).

- **Positive controls.** An isolation level set through JDBC is reset (`iso-reset`), and a schema set through `setSchema()` is reset when `schema` is configured (`schema-configured`).
- **Known upstream, reproduced:**
  - **`schema-unconfigured`** (#2081). With `schema` unset, `setSchema("tenant_a")` survives to B, and B's unqualified insert lands in `tenant_a`.
  - **`setup-schema-noautocommit`** (#1369, #1633, #2235).
    - Right after pool start, the pooled backend is already `idle in transaction`: the setup's `SET SESSION search_path` was never committed.
    - A's rollback undoes it, and B's committed insert lands in `public`, not in the configured `tenant_b`.
    - Log: the setup's `SET` shares a vxid with A's work and `ROLLBACK`.
  - **`reset-undone`** (#2144).
    - HikariCP's own reset `BEGIN; SET SESSION search_path TO 'public'` is left uncommitted.
    - B's rollback undoes it, and C's committed insert lands in A's `tenant_a`.
    - Log: the reset shares a vxid with B's insert and `ROLLBACK`.
- **Raw SQL state (`raw-sql-state`):** not tracked, so not reset: role, `search_path`, advisory lock and temp table. B's insert lands in `tenant_a` as `ssc_tenant_a`. HikariCP promises nothing for SQL-level changes, so this is CONFIRMED BEHAVIOR — NOT A DEFECT.
- **F-H2:** §8.

### 7.2 asyncpg 0.32.0

Probe: [`python/asyncpg_pool_probe.py`](python/asyncpg_pool_probe.py).

- **Normal release.** `search_path`, a custom GUC, an advisory lock and LISTEN are cleared, and B is on the same backend. A raw `BEGIN` with an insert is rolled back.
  - Role, temp tables and SQL `PREPARE` were not re-measured here. The earlier probe P2 and PY-6 cover role, and asyncpg#1293 covers temp tables.
- **Failure paths.** Each of these ended with B on a new backend with clean state:
  - a custom reset that raises (`reset-raises`);
  - a release timeout (`reset-timeout`);
  - a backend terminated before release (`backend-killed`).

  These ended with B on the same backend, already reset:

  - a release cancelled 0.1 s into a 0.5 s reset (`cancel-during-reset`). `asyncio.shield` lets the reset finish, and B waits for it;
  - a cancelled long query followed by an immediate release (`cancelled-query`). The release waits for the cancellation.
- **One operational effect, after a release timeout:**
  - **What happens.** asyncpg terminates the connection client-side and sends no cancel request. Log, `reset-timeout-long`, four runs: no statement was cancelled, the reset's `pg_sleep(5)` ran to completion, and every session lasted 5.0–5.2 s. The observer saw A's old backend still alive 1 s after the timeout and gone within 6 s.
  - **The consequence.** The old server session keeps running, and holds A's advisory lock, until its statement ends. In `reset-timeout`, B, on its new connection, could not take the lock (`pg_try_advisory_lock` false).
  - **Why it is not a pool defect.** PostgreSQL notices a closed client only at its next socket I/O, unless `client_connection_check_interval` is set. The pool kept its own contract.

### 7.3 SQLAlchemy 2.1.6

Probe: [`python/sqlalchemy_pool_probe.py`](python/sqlalchemy_pool_probe.py).

- **Normal close**, sync on psycopg and async on asyncpg: A's insert is rolled back, and A's committed `search_path` reaches B, as documented.
- **Cleanup failures.** In both cases the connection is invalidated, and B gets a new backend with clean state:
  - an `AsyncConnection.close()` cancelled during a slowed reset;
  - a rollback that fails because the backend was terminated.
- **What these cases do not cover.** The cancellation case is the scenario of #13699 (fixed in 2.1.6), apart from the stale-handle reuse that #13699 is about. PY-7 is the known path in which SQLAlchemy skips the rollback.

### 7.4 psycopg_pool 3.3.3, and Django

Probe: [`python/psycopg_pool_probe.py`](python/psycopg_pool_probe.py).

- **Without a `reset` callback,** session state carries over, as documented.
- **Discarded:** a connection whose rollback fails (backend terminated), and one whose `reset` callback raises.
- **Asynchronous cases:**
  - **A cancelled long query** is cancelled on the server and rolled back.
  - **A borrower cancelled while its reset runs** in the pool's worker task does not stop the reset, and B gets the reset session.

**Django was not run in this study.** Its native pool's failure paths are psycopg_pool's (Src §4). Its normal-release behaviour is in the earlier probe P2.

### 7.5 Npgsql 10.0.3

Probe: [`npgsql/Program.cs`](npgsql/Program.cs).

- **Normal close.** While A's connector is idle in the pool, the observer sees A's advisory lock held and A's temp table present. A competing connection cannot take the lock.
  - B's first statement carries `DISCARD ALL` (Log: `DISCARD ALL` immediately before it). After it, the role, `search_path`, LISTEN, temp table and SQL `PREPARE` are cleared, and the competitor can take the lock.
  - This is the documented lazy reset. With idle pruning (`pruned`), the lock is released when the connector is closed.
- **With an Npgsql-prepared statement present,** the reset sequence omits `DEALLOCATE ALL`. A's own SQL-level `PREPARE` then survives to B: a minor carryover, consistent with the documented intent.
- **`No Reset On Close`** carries everything over, as documented.
- **A failed rollback during the reset** breaks the connector, and B gets a new one.
- **A terminated idle backend:** the next borrower's first statement throws, and the one after gets a clean connector.

### 7.6 node-postgres 8.23.1 (pg-pool 3.14.0)

Probe: [`node/pg_pool_probe.mjs`](node/pg_pool_probe.mjs).

- **Releasing with a transaction open** hands the transaction, role and `search_path` to B.
  - B's insert "succeeds" in what B believes is autocommit mode, but it is never committed. It is gone after `pool.end()`.
  - This is the knex#6546 (K2) shape, and application misuse under node-postgres's documentation.
- **An aborted transaction** makes B fail loudly (`25P02`).
- **`release(err)`** destroys the client.

## 8. Confirmed defect F-H2: HikariCP recycles a connection whose state reset failed

### 8.1 Observations

All Observed 3 of 3, with Log support:

| Scenario | Trigger | What the next borrowers got |
| --- | --- | --- |
| `reset-fails` | `autoCommit=false`, isolation at driver default; A: `setTransactionIsolation(SERIALIZABLE)`, `getSchema()` | A's `close()` threw `25001`. After close the backend was `idle in transaction` with a snapshot (`backend_xmin`). B: same backend, SERIALIZABLE, transaction already more than 500 ms old, read `v = 0` after the observer committed `v = 1`. C: SERIALIZABLE. Log: B's alive-check query, reads, insert and `COMMIT` are in A's vxid, and no isolation reset was sent |
| `reset-fails-configured-getschema` | Same, with `transactionIsolation=TRANSACTION_READ_COMMITTED` and `schema=public` configured | The same: the configured isolation is violated |
| `reset-fails-configured-setschema` | Trigger `setSchema("tenant_a")` (pgjdbc#3005's BEGIN) | Also: the schema reset was skipped, and B's committed unqualified insert landed in `tenant_a`; B and C have `current_schema() = tenant_a` |
| `reset-fails-configured-savepoint` | Trigger `setSavepoint()` | B inside A's transaction, SERIALIZABLE. No stale read: SAVEPOINT takes no snapshot (`backend_xmin` absent) |
| `reset-fails-readonly` | Pool `autoCommit=true`; A: `setAutoCommit(false)`, `setReadOnly(true)`, `getSchema()` | A's `close()` threw `25001` (read-only). B: `getAutoCommit()` false, `isReadOnly()` true, insert fails `25006` |
| `readonly-report-poison` | Pool defaults; A: read-only report, `commit()`, then `getSchema()` | B, C and D, each borrowed after 600 ms so that HikariCP's alive check runs: autocommit off and read-only. Inserts fail `25006`, `25P02`, `25P02`. Log: each alive check (empty query) passes inside A's aborted transaction |
| `reset-fails-isolate-internal` | As configured-getschema, plus `isolateInternalQueries=true` | The alive check's rollback ended A's transaction (B is idle at checkout, fresh read), but B still got SERIALIZABLE: a partial mitigation |
| Controls | `reset-fails-control`, `reset-fails-configured-none` (no trigger) | Reset completed; B gets the defaults on the same backend |
| Recovery | `reset-fails-configured-evicted` (`softEvictConnections()` after A) | A new backend with the defaults |
| Minimal reproduction | [`hikari/minimal/MinimalRepro.java`](hikari/minimal/MinimalRepro.java), HikariCP 4.0.3, 5.1.0, 6.3.3, 7.0.2, 7.1.0 | Identical output on all five (`8cd85f1c…`) |

### 8.2 Adversarial validation

| Check | Result |
| --- | --- |
| CHK-1 Documented guarantee | **Held.** HikariCP documents its `autoCommit`, `readOnly` and `transactionIsolation` values as the defaults of connections returned from the pool. Its maintainer states that configured defaults "are reset when a connection is returned to the pool" (#2200). Nothing documents an exception for a failed reset. |
| CHK-2 Supported usage | **Held.** Only `java.sql.Connection` methods were called through the pool's proxy: no `unwrap`, no SQL transaction control. A closes without `commit()` or `rollback()` after `getSchema()`. JDBC leaves `close()` with an active transaction implementation-defined. Here, though, the application executed no statement after its last `commit()`: the transaction was begun by the driver inside `getSchema()`. |
| CHK-3 PostgreSQL semantics | **Normal.** One session keeps its session characteristics across transactions, and a unit that starts on an open transaction joins it (§5). The pool's reset was required and did not happen. |
| CHK-4 Physical identity | **Held.** Same PID and `backend_start`, and the Log shows the same backend and vxid. |
| CHK-5 Cleanup execution | **Attempted, then rejected client-side.** pgjdbc threw `25001` before sending anything, `close()` rethrew it, and the Log has no reset statement. The remaining reset steps were skipped: the schema reset in `configured-setschema`. |
| CHK-6 Reachability | **Reachable with ordinary API calls, with no artificial state manipulation** (Observed). It needs a transaction that pgjdbc began and HikariCP did not count (`getSchema()`, `setSchema()` or `setSavepoint()` after the last `commit()` or `rollback()`), and a tracked read-only or isolation change still dirty at `close()`. Frequency is not established. Judg: frameworks that restore isolation and read-only before `close()` avoid the failing step. Spring's `DataSourceUtils.resetConnectionAfterTransaction` is one such path (Src, not run). So hand-written JDBC is the likelier source. |
| CHK-7 Layer attribution | **HikariCP:** the decision to recycle after a failed reset is in `ProxyConnection.close()`. **pgjdbc contributes the trigger:** `getSchema()`/`setSchema()` begin transactions, while `getTransactionIsolation()` deliberately does not ("nb: no BEGIN triggered"). The pool-layer defect does not depend on the trigger: any reset step that throws a non-eviction SQLException leaves a partially reset connection in the pool. |
| CHK-8 Existing documentation | **Undocumented.** In #1009 (2017) the maintainer considered it unreachable: "I would expect that any of the invocations in `resetConnectionState()` cannot fail in a manner that would avoid eviction. I could be wrong, and if so I would like a concrete example." No duplicate was found (§15). |
| CHK-9 Minimal reproduction | **Held.** One file, HikariCP and pgjdbc only, five versions. |
| CHK-10 Independent verification | **Held.** The observer's `pg_stat_activity` (`idle in transaction` after `close()`, `backend_xmin`), the observer-committed value against B's read, where the rows landed, and the statement log by vxid. |
| CHK-11 Repeatability | **Held.** 3 of 3 for every scenario, in every recording (two to four per scenario, across probe builds). |
| CHK-12 Security significance | **Not established.** A cross-schema write is demonstrated (`configured-setschema`), but whether it crosses a trust boundary depends on an application that relies on the pool's default schema for separation. Classified CONFIRMED DEFECT, not security-relevant. |

### 8.3 Root cause

Line numbers are HikariCP 7.1.0's (Src):

1. **The responsible code** is `ProxyConnection.close()` (240–270). The rollback and `resetConnectionState()` sit in a `try`. The `catch` rethrows through `checkException()`. The `finally` always calls `poolEntry.recycle()`.
2. **Checkout** (`HikariPool.getConnection`, 152–193). The alive check runs only after 500 ms idle and calls pgjdbc's `isValid()`, which returns true for `25P02`. The proxy is created with the pool's defaults as its tracked state (`PoolEntry.createProxyConnection`, `ProxyConnection` constructor 85–97), not the driver's actual state.
3. **Release:** `closeStatements()`, then `rollback()` if `isCommitStateDirty && !isAutoCommit`, then `resetConnectionState()` for the dirty bits (read-only, autocommit, isolation, catalog, network timeout, schema, in that order), then `clearWarnings()`.
4. **Commit-state tracking.** The flag is set by statement execution through the proxy, and by `getMetaData()` (after #866). It is not set by `getSchema()`, `setSchema()` (which also calls the delegate's `getSchema()`, 505–510) or `setSavepoint()`.
5. **Failure detection.** `checkException()` (151–186) evicts only for SQLSTATE class `08`, a fixed list of states and codes, or an `SQLExceptionOverride` verdict. `25001` is none of these.
6. **Transition to available.** `HikariPool.recycle()` (434–449) returns the entry to the bag unless it is marked evicted.
7. **The earliest incorrect transition** is the `finally` recycling an entry whose reset did not complete. The missing commit-state mark is the trigger, not the defect.
8. **Invalidation should have occurred.** After a reset step fails, the connection's state is unknown, while the next proxy will assume the pool's defaults.
9. **The smallest correction is one line,** `poolEntry.markEvicted()` in the `catch` before rethrowing ([`hikari/patch/hikaricp-7.1.0-evict-on-failed-reset.diff`](hikari/patch/hikaricp-7.1.0-evict-on-failed-reset.diff)).
   - **The API stays the same,** and the application is still told: `close()` still throws.
   - **There is no database-specific logic.** The maintainer's objection in #1633 was to "injecting database specific logic into the pool".
   - **Complementary, not a substitute:** mark the commit state dirty in `getSchema()`, `setSchema()` and `setSavepoint()`, as #866 did for `getMetaData()`. That removes the known triggers, but not the recycling.
   - **Not proposed:** an unconditional `ROLLBACK` or `DISCARD ALL` on return. It would conflict with HikariCP's deliberate avoidance of unneeded rollbacks, and with session state users keep on purpose.
10. **Regression tests:**
    - **Added and run:** `ConnectionStateTest.testConnectionIsNotReusedWhenStateResetFails`, on `StubConnection`. It fails on 7.1.0 and passes with the change.
    - **Suggested:** a PostgreSQL integration test with the `getSchema()` trigger.
    - **For pgjdbc:** `getSchema()` and `setSchema()` should leave the transaction state `IDLE` in non-autocommit mode.

### 8.4 The correction, validated

- **Probes with the fix.** The fix was overlaid on the released 7.1.0 jar; the JVM class-load log names the overlay jar ([`hikari/run-patched.sh`](hikari/run-patched.sh)). Every failing scenario gave B, and C and D in the poison case, a fresh backend with the pool's defaults and a fresh snapshot, while A's `close()` still threw `25001`. Both controls produced byte-identical output with and without the fix (`76a6e4e5…`, `ce507243…`).
- **HikariCP's suite**, at tag `HikariCP-7.1.0` with `mvn test '-Dtest=!PostgresTest'` (`PostgresTest` needs Testcontainers), 192 tests:
  - **unpatched:** 2 failures, the new test and `RampUpDown`;
  - **patched:** 1 failure, `RampUpDown`.

  `RampUpDown` fails the same way without the change (3 of 3 alone), so it is pre-existing in this environment. Summaries: [`output/hikaricp-suite/`](output/hikaricp-suite/).
  - The suite ran with an earlier comment wording of the same one-line change. The final wording was re-tested with `ConnectionStateTest` (7 of 7).
- **The workaround on unmodified 7.1.0** (`readonly-report-override`). An `SQLExceptionOverride` returning `MUST_EVICT` for `25001` ([`hikari/src/main/java/ssc/EvictOnStateResetRejected.java`](hikari/src/main/java/ssc/EvictOnStateResetRejected.java)) made HikariCP log "marked as broken because of SQLSTATE(25001)". B got a fresh connection. It also evicts on `25001` from any other call.

## 9. Rejected hypotheses

| Hypothesis | Result |
| --- | --- |
| HikariCP's `rollback(Savepoint)` clears the commit-state flag, so pending writes reach the next borrower | False in 7.1.0: it sets the flag to true (Src, 392–396). HikariCP #2142 reported it against 5.0.1, and is still open |
| `getMetaData()` opens a transaction HikariCP misses | False since #866: `getMetaData()` marks the flag (Src, 368–371) |
| pgjdbc's `isValid()` (HikariCP's alive check) begins a transaction | False: the empty query ran in its own vxid without `BEGIN` (Log) |
| A read-only session default makes asyncpg's reset fail | False: all four reset statements succeed read-only (psql) |
| A cancelled, timed-out, failing or interrupted cleanup lets asyncpg, SQLAlchemy, psycopg_pool or Npgsql hand out the dirty session | False in every scenario (Observed, §7) |
| Npgsql's lazy reset can be skipped by the next borrower | Not observed. A failed prepended reset breaks the connector, and user cancellation waits until the prepended responses are read (Src, `ReadMessageLong`) |

## 10. Production impact

Judg, from the observations:

- **F-H2, isolation variant:** silent wrong results. Reads come from an old snapshot. Later transactions run SERIALIZABLE (more serialization failures) on a pool configured for READ COMMITTED. A long-lived open transaction holds back vacuum and can be killed by `idle_in_transaction_session_timeout`.
- **F-H2, read-only variant:** every write through that physical connection fails, on a pool with default settings, while validation passes. With one connection that is an outage; with many, intermittent failures.
- **F-H2, `setSchema()` variant:** unqualified writes go to the previous borrower's schema.
- **Frequency** is not established. The trigger needs a driver-begun transaction after the last commit, plus a dirty isolation or read-only setting.
- **Npgsql and asyncpg (operational):**
  - Session advisory locks taken for jobs can stay held after "release", until the connector is reused or pruned (Npgsql).
  - They can also stay held while an orphaned backend finishes its statement (asyncpg after a reset timeout).

  Applications that use session advisory locks should unlock explicitly.

## 11. Known upstream issues reproduced (do not re-file)

| Behaviour | Upstream | State on 2026-10-24 |
| --- | --- | --- |
| `setSchema()` not reset when `schema` is unset | HikariCP #2081 | Open |
| Configured schema reset left in an open transaction (`autoCommit=false`) | HikariCP #2144 | Open |
| Configured schema at setup undone by the first rollback | HikariCP #1369 (open), #1633 (closed with a workaround), #2235 (open; maintainer: "This is disturbing. I do suspect it is caused by the referenced pgjdbc issue.") | |
| `setSchema()` begins a transaction | pgjdbc#3005 | Open; maintainers agreed on 2023-11-22 to "skip creating transactions for `setSchema` calls"; not implemented in 42.7.14 or `master` `874745258` |
| asyncpg reset leaves `SET ROLE` | PY-6 (this repository) | READY_FOR_HUMAN_REVIEW |
| asyncpg reset leaves temp tables | asyncpg#1293, PR #1392 | Open |

## 12. Cross-investigation observation (transaction hooks after a false commit success)

These are not pursued here, and no overlapping issue should be filed.

- **node-postgres `open-transaction`.** B's insert returned success but was never committed; it was lost when the connection closed. That is a false write-success caused by connection reuse (the TX-03/K2 shape), not a callback.
- **F-H2 produced no false write success.** Writes either failed loudly (the read-only variants) or committed inside the inherited transaction, as the observer saw. Its wrong results are reads from a stale snapshot and the wrong isolation level, which callbacks do not report either way. On a default pool, a dirty autocommit setting alone did not leave autocommit off (Observed, `autocommit-reset-commits`). HikariCP resets read-only before autocommit (Src, `resetConnectionState`). With no read-only reset to fail, the autocommit reset ran, and pgjdbc committed the driver-begun transaction (Log: `BEGIN | select current_schema() | COMMIT`, then the isolation reset).

## 13. Limitations

- One machine (macOS arm64, colima), one PostgreSQL version (18.6), loopback networking. No real network partition was tested.
- Spring, Hibernate, jOOQ and Django were not run against these pools, so F-H2's framework-level reachability rests on source reading. PgBouncer was not tested.
- The asyncpg timeout and cancellation windows were widened with custom reset callbacks; the default reset's windows are much shorter.
- HikariCP's suite was run excluding `PostgresTest`.
- Upstream issue states and the "no duplicate" results are as of 2026-10-24.
- Probe outputs include only what each probe checks. For example, asyncpg's role, temp-table and `PREPARE` behaviour come from earlier work.

## 14. Recommended upstream actions

1. **HikariCP: one new issue,** [`upstream-drafts/hikaricp-failed-reset-recycled.md`](upstream-drafts/hikaricp-failed-reset-recycled.md). It contains the minimal reproduction, the evidence, the one-line change and the regression test, and offers a PR.
2. **pgjdbc: one comment on #3005,** [`upstream-drafts/pgjdbc-3005-getschema-comment.md`](upstream-drafts/pgjdbc-3005-getschema-comment.md), saying that `getSchema()` begins a transaction too.
3. **Nothing new for asyncpg, SQLAlchemy, psycopg_pool, Npgsql or node-postgres.**
   - Optional: a documentation note for Npgsql that session advisory locks stay held on idle connectors until reuse or pruning. Not drafted.
   - asyncpg's role item stays PY-6.
4. **Do not re-file** the HikariCP schema issues or pgjdbc#3005.

## 15. Upstream duplicate searches

Run 2026-10-24 with `gh api -X GET search/issues` (AND searches, not phrase searches):

- **HikariCP:** `setSchema reset`, `schema reset pool`, `"middle of a transaction"`, `resetConnectionState`, `schema autoCommit transaction`, `getSchema transaction`, `close exception reset evict`, `recycle exception close`, `setSavepoint dirty`, `markCommitStateDirty`;
- **pgjdbc:** `getSchema transaction`, `getSchema BEGIN autocommit`, `current_schema transaction autoCommit`.

Related items found, none reporting a reset failure followed by reuse:

- **schema handling:** #2081, #2144, #1369, #1633, #2235 (§11), #2170 (schema reset skipped after a rollback, open), #2323 and #2346 (`getSchema()` contract and a `setSchema()` regression, both closed in 2025);
- **commit-state tracking:** #866 (`getMetaData()`, fixed), #2142 (`rollback(Savepoint)`, open);
- **reset failures:** #1009 (closed pull request; the maintainer's 2017 question);
- **the contract:** #2200 (the maintainer's statement);
- **25001 at checkout,** from older pgjdbc `isValid()` behaviour: #102 (2014) and #674 (2016), both closed;
- **broken connections returned to the pool:** #528 (2015, closed);
- **isolation at setup:** #187 (2014, closed);
- **pgjdbc:** #3005.

## 16. Answers to the brief's final questions

1. **Which pools promise to reset session state?**
   - **Fully:** asyncpg (its reset query, "resembling a newly obtained connection") and Npgsql (`DISCARD ALL` or an equivalent, lazily).
   - **JDBC-API-tracked state only:** HikariCP.
   - **The transaction only:** SQLAlchemy and psycopg_pool.
   - **Nothing:** Django and node-postgres (§4).
2. **Which state do those guarantees cover?**
   - **asyncpg:** advisory locks, cursors, LISTEN, GUCs. Not covered: role (PY-6), temp tables (asyncpg#1293), and, from §5 and the reset query rather than an asyncpg run, session authorization and SQL `PREPARE`.
   - **Npgsql:** everything `DISCARD ALL` covers. With prepared statements present, all but SQL `PREPARE`.
   - **HikariCP:** autocommit, read-only, isolation, network timeout, plus catalog and schema when configured.
3. **Can cleanup fail without the connection being invalidated?** Yes in HikariCP (F-H2). Not in asyncpg, SQLAlchemy, psycopg_pool or Npgsql.
4. **Can a later borrower inherit state contrary to a documented guarantee?** Yes, through F-H2: isolation, read-only, autocommit, schema and an open transaction. Through the known issues: HikariCP's schema handling, and asyncpg's role (PY-6).
5. **Through ordinary errors, cancellation or network interruption?** F-H2 needs no error at all: ordinary JDBC calls cause the reset failure. Cancellations, timeouts, raised exceptions and terminated backends were handled safely by asyncpg, SQLAlchemy, psycopg_pool and Npgsql. One asyncpg reset timeout left an orphaned server session holding locks until its statement ended (PostgreSQL behaviour).
6. **Defects or misuse?**
   - **Defects:** F-H2 is a HikariCP defect, with a pgjdbc trigger.
   - **Misuse:** releasing node-postgres clients with an open transaction.
   - **Documented behaviour:** everything else in §7.
7. **Tenant-isolation or security implications?** Cross-schema writes are demonstrated; unauthorized access is not. PY-6 (role) is the clearest security-relevant item, and it is known.
8. **The smallest correction?**
   - **HikariCP:** `poolEntry.markEvicted()` in `close()`'s catch (one line). Optionally, commit-state marks for `getSchema()`, `setSchema()` and `setSavepoint()`.
   - **pgjdbc:** no `BEGIN` from `getSchema()` and `setSchema()`.
   - **Today:** an `SQLExceptionOverride` evicting on `25001`.
9. **Regression tests?** The added `ConnectionStateTest` case; a PostgreSQL integration test with the `getSchema()` trigger; and a pgjdbc test that `getSchema()` and `setSchema()` leave the transaction state idle.
10. **New PPCS conformance cases?** None now. See [`ppcs-integration.md`](ppcs-integration.md): one invariant is proposed for a future session-state family, subject to maintainer approval.
11. **Which findings warrant upstream issues?** One HikariCP issue and one pgjdbc comment (§14).
12. **How do these findings relate to PPCS's existing connection-reuse results?**
    - **What TX-03 tests.** It injects a failed `ROLLBACK` in the framework's own rollback. Its pooled JVM modes run on HikariCP: Spring JDBC, Spring TX and jOOQ fail `TX-03.rollback-not-sent`, because the framework's `setAutoCommit(true)` commits; Hibernate passes, because HikariCP rolls back on close.
    - **What F-H2 adds.** The pool itself skips the rollback, since its commit-state flag misses a driver-begun transaction, and then recycles the connection after its own reset fails. TX-03's unit 1 executes statements, which set the flag, so TX-03 cannot reach F-H2. The node-postgres result is the K2 shape (knex#6546) at the pg-pool level.

## 17. Reproducing

```sh
cd research/connection-pool-session-state
env/pg-up.sh /path/to/instance.json            # own container, port 55473; the file is written mode 0600
python3.13 -m venv .venv && .venv/bin/pip install -r python/requirements.lock.txt
.venv/bin/python -I baseline/pg_session_baseline.py /path/to/instance.json
(cd hikari && mvn -q -B package) && hikari/run.sh /path/to/instance.json reset-fails
.venv/bin/python -I python/asyncpg_pool_probe.py /path/to/instance.json cancel-during-reset
(cd npgsql && dotnet build -c Release) && dotnet exec npgsql/bin/Release/net10.0/SscNpgsqlProbe.dll /path/to/instance.json normal
(cd node && npm ci) && node node/pg_pool_probe.mjs /path/to/instance.json open-transaction
env/pg-down.sh /path/to/server.log             # saves the log, removes only this container
python3.13 -I analysis/build_matrix.py > results-matrix.md
```

The scenario names are each probe's `case` labels and the `output/` file names. The patched runs need the overlay jar. [`hikari/patch/make-overlay.sh`](hikari/patch/make-overlay.sh) builds it from Maven Central's 7.1.0 sources jar and the committed diff; its classes were checked byte-identical to the ones the recorded patched runs used:

```sh
hikari/patch/make-overlay.sh && hikari/run-patched.sh /path/to/instance.json reset-fails
```

**Incidental, not investigated (Src only).** HikariCP 7.1.0 `HikariConfig.setCredentialsProviderClassName()` assigns `this.exceptionOverrideClassName = credentialsProviderClassName` (line 893). It looks like a copy-paste slip. Outside this study's scope, and not run.
