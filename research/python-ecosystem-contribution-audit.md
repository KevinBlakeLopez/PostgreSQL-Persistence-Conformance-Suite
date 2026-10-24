# Python ecosystem contribution audit

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This audit reads what PPCS and the adjacent Python research already establish about Django, SQLAlchemy, psycopg, asyncpg, and Tortoise ORM. It then ranks what remains to contribute upstream.

- It is not a defect report.
- It changes no adapter, harness, specification, catalog, recorded result, or shared document.
- Nothing was filed or posted.

One diagnostic was run, for the one question no recorded run answered (§3.1, B2). Its program, output and provenance are in [`python-ecosystem-contribution-audit/`](python-ecosystem-contribution-audit/README.md).

A concurrent gap analysis (Agent 2) worked in the same checkout on Python production failure modes that PPCS does not cover. Its report is planned as `research/python-production-failure-gap-analysis.md`. Its source readings and runtime results are cited below as **A2**, and §7 lists its candidate gaps as its own. The two `AGENT-*-STATUS.md` files are coordination notes and are not for commit.

**Evidence labels**

| Label | Meaning |
| --- | --- |
| **PPCS** | A recorded run in this repository. Three repetitions. Suite runs are also gated by CTL-01 and `pg-control` |
| **Audit** | The diagnostic run for this audit. Three repetitions, outside the harness, no gates |
| **Ext** | Recorded outside PPCS, in a sibling directory or a separate private repository. Not gated. One run unless stated |
| **Src** | Source reading of the installed version, with file and line. Not a runtime observation |
| **Doc** | Documentation text, quoted, with the date checked |
| **Upstream** | Issue-tracker or forum state, with the date checked |
| **A2** | Agent 2's status note (2026-10-24, through the 07:55 PDT update). Source reading unless marked "runtime". Its runtime probes ran 3 repetitions in its own container. Their program and output are not yet in this repository |
| **Judg** | This audit's assessment |

**Versions.** Unless a row says otherwise:

- Django 6.1.2, SQLAlchemy 2.1.5, psycopg 3.3.6, Tortoise ORM 1.1.9, asyncpg 0.32.0;
- Python 3.13.11;
- PostgreSQL 18.6, `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`.

The installed sources read are in `adapters/{django,sqlalchemy,sqlalchemy-core,tortoise}/.venv`.

## 1. Executive summary

- **Most of the brief is already answered.** The central Python finding is established at every layer:
  - **The sequence.** A transaction catches a unique violation (`23505`) and then ends normally. PostgreSQL completes `COMMIT` with command tag `ROLLBACK`, and the application-facing API reports success.
  - **Covered layers:** PostgreSQL, psycopg, SQLAlchemy Core, and Django's manual `commit()`.
  - **Evidence:** recorded runs `64c5c5`, `b2c174` and `508b7a`, plus a direct psycopg program.
  - **Filed** as [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453) on 2026-10-21. It is still open, with no comments, as of 2026-10-24. The upstream tracker records a decision not to file SQLAlchemy or Django separately. This audit agrees.
- **One new result.** psycopg's own context manager, `with conn.transaction() as tx:`, returns normally and sets the public `tx.status` to `committed` when PostgreSQL aborted the transaction (Audit, 3 of 3). A savepoint-recovery control committed correctly.
  - #1453's posted body covers only `Connection.commit()`.
  - `Transaction.status` was added by psycopg PR #1184, for psycopg #969, to record whether a block committed or rolled back.
  - The smallest actionable contribution in this audit is therefore a short follow-up comment on #1453, after explicit approval. It is not a new issue.
- **Tortoise on asyncpg is the one Python commit-tag finding with no report and no draft. Its layer is now identified as asyncpg.**
  - PPCS run `c45624` records a FAIL. Its driver trace shows asyncpg's `Connection.execute("COMMIT;")` returning `ROLLBACK`.
  - asyncpg's `Transaction.commit()` discards that status (Src).
  - The concurrent gap analysis then ran asyncpg 0.32.0 with no Tortoise (A2, runtime, 3 of 3). `async with conn.transaction()` and `Transaction.commit()` return normally, with transaction state `committed`, while PostgreSQL aborted. SQLAlchemy on asyncpg does the same.
  - What remains is a duplicate search and a draft: a psycopg#1453-shaped report for asyncpg.
- **Django migration concurrency is not a bug report.**
  - PPCS shows `MigrationExecutor` has no cross-process serialization: marker count 2 and history count 2, both runners exit 0.
  - Django documents no concurrency guarantee. Upstream already discussed it and declined: ticket #30490 (wontfix), #34610 (its duplicate), and a 2023 forum thread with no decision.
  - At most, a documentation proposal through the Django Forum.
- **Django's TX-02 FAIL is narrow.**
  - It needs an exception that is not `django.db.Error`, raised before `ROLLBACK TO SAVEPOINT` is sent.
  - The realistic analogues pass: a server-side backend termination at that point (category B), and a PostgreSQL rejection of the statement.
  - No production trigger is established. No upstream action.
- **Adjacent research already covers several Python items PPCS does not:**
  - a SQLAlchemy defect confirmed by an adversarial review (P5a, failed `commit()` then `close()`), whose draft is approved and not posted;
  - Django's `on_commit` running on a raw-cursor path that Django documents as unspecified;
  - an Alembic race study that was deliberately stopped;
  - an earlier Tortoise run.

  Some of it lives in directories that are not under version control.

**Conclusion.** Little new research is needed. The next steps are upstream engagement on what already exists:

- the #1453 comment;
- an asyncpg report, after the duplicate search;
- P5a, posted by its author in their own words, as SQLAlchemy's rules require.

## 2. Existing evidence inventory

### 2.1 In this repository

| Subject | Recording | Covers | Per-case report |
| --- | --- | --- | --- |
| Django, `native` and `persistent` | `reports/examples/2026-10-18T13-08-22Z-6d8443` | CTL-01, TX-01A, TX-01B, TX-02, TX-03 | `adapters/django/FINDINGS.md` |
| Django | `reports/examples/2026-10-21T19-26-59Z-4ccef5` | TX-04, TX-05 | same |
| Django `MigrationExecutor` | `reports/examples/2026-10-21T20-00-04Z-178fa4` | MG-02, MG-03 | same, and the root `README.md` |
| SQLAlchemy ORM `Session` | `reports/examples/2026-10-19T00-49-25Z-3673a3`; TX-04 and TX-05 in `4ccef5` | CTL-01 to TX-05 | `adapters/sqlalchemy/FINDINGS.md` |
| SQLAlchemy Core `Connection` | `reports/examples/2026-10-19T12-35-51Z-64c5c5` | CTL-01 to TX-05 | `adapters/sqlalchemy-core/FINDINGS.md` |
| Tortoise ORM on asyncpg | `reports/examples/2026-10-19T12-45-38Z-c45624` | CTL-01 to TX-04 | `adapters/tortoise/FINDINGS.md` |
| Category E protocol proxy | `reports/examples/2026-10-21T23-50-08Z-87af6a` | `TX-01B.commit-reply-unseen`, all four Python adapters | root `README.md` |
| PR-01, production reachability | `research/production-reachability/runs/2026-10-19T18-15-49Z-b2c174` | Caught `23505`, then managed or explicit completion, plus controls. Covers SQLAlchemy ORM, Core and Django | `research/production-reachability/README.md` |
| PR-01, Django manual `commit()` | `research/production-reachability/runs/2026-10-19T20-58-26Z-508b7a` | Explicit catch, then commit | same |
| psycopg, direct | `research/production-reachability/reproductions/psycopg_commit_tag.py` and `.txt` (2026-10-21) | `Connection.commit()` returns `None`. Tag `ROLLBACK` through `cursor.execute("COMMIT")` | `research/production-reachability/upstream-drafts/psycopg.md` (filed as #1453) |
| SQLAlchemy, standalone | `research/production-reachability/reproductions/sqlalchemy_catch_commit.py` | Core and ORM | No saved output (`docs/research-status.md` §4) |
| This audit | `research/python-ecosystem-contribution-audit/` | psycopg `conn.transaction()` | its `README.md` |

**Runs not to cite** (per `docs/research-status.md` §2):

- `2026-10-19T17-50-05Z-90b4ea` and `2026-10-19T17-50-45Z-a66571`: their controls did not hold, or the run was partial;
- `2026-10-19T18-11-24Z-a70895`: a one-repetition Knex and Kysely subset.

`2026-10-19T18-34-44Z-8139f2` is an earlier Django follow-up with the same outcome as `508b7a`.

### 2.2 Outside this repository

None of these is a PPCS result.

| Location | Status | Contents relevant here |
| --- | --- | --- |
| `../sqla-tx02-repro/` | Local directory, not under version control. 2026-10-19 | **`commit-layer.md`:** three arms, three trials each. `Session.begin()`, `Connection.begin()`, and a bare psycopg `commit()` after a `3B001` all return, and PostgreSQL aborted. **`commit-tag.md`:** one trial. It reads the internal `PGresult` of `commit()`'s own `COMMIT`: `COMMAND_OK`, tag `ROLLBACK`. It quotes PostgreSQL 18.6 `EndTransactionBlock` and `standard_ProcessUtility`. This is the "later measurement" that `adapters/sqlalchemy*/FINDINGS.md` cite without a path |
| `../python-orm-transactions/` | Separate private repository, HEAD `301649a`, some files uncommitted | **`docs/django-transaction-review.md`** with `django-transaction-experiments/recorded/run-1.json`: 2026-10-17, one run per arm, Django at commit `2212534b`. **`docs/sqlalchemy-upstream-issue-drafts.md`:** Drafts A–C and an SA-01 to SA-04 contract table. Not submitted. Evidence `sqlalchemy-transaction-experiments/recorded/run-2.txt`. **`docs/sqlalchemy-p5a-close-issue-draft.md`** and **`docs/sqlalchemy-p5a-close-review.md`:** verdict CONFIRMED DEFECT, 2026-10-18, with `check/p5a_close_v2.py` and `.out`. **`lifecycle-close-reuse.md`:** uncommitted. **`docs/alembic-migration-outcomes/`:** Alembic 1.20.0 |
| `../tortoise-tx-investigation/` | Local directory, not under version control. 2026-10-17 | `run_tx.py` and `recorded/results.json`: 15 cases, one run each. The TO-02 cases ran twice |
| Branch `research/transaction-outcome-propagation`, worktree `../ppcs-transaction-outcome` | Local. Not merged into `main`, not pushed | Driver and framework "information-loss boundary" records for node-postgres, TypeORM, pdo_pgsql, ruby-pg, Knex, Kysely, Drizzle and Prisma. psycopg and asyncpg were not run: "The system Python has no psycopg module, so psycopg was not executed" (run `af4ba2`) |

## 3. Question-by-question status

Statuses: ANSWERED, PARTIALLY ANSWERED, UNANSWERED, BLOCKED, NOT APPLICABLE. "ANSWERED (this audit)" marks a question that PPCS had not answered and this audit's checks did.

### 3.1 SQLAlchemy Core → psycopg → PostgreSQL, `TX-01A.caught-error-then-commit`

**A. PostgreSQL behaviour**

| # | Question | Status | Evidence |
| --- | --- | --- | --- |
| A1 | The exact SQL sequence | ANSWERED | PPCS `64c5c5`, `cases/TX-01A.caught-error-then-commit.sqlalchemy-core.native.json`, trace: `INSERT INTO item …`, `select pg_current_xact_id()…`, `INSERT INTO uniq …` (raises `23505`), `COMMIT (INERROR -> IDLE)`, then the pool's `ROLLBACK (IDLE)` |
| A2 | Transaction state before `COMMIT` | ANSWERED | Same file, checkpoint `before-end`: `idle in transaction (aborted)`, no `backend_xid`, and `pg_xact_status` already `aborted` |
| A3 | The actual command tag | ANSWERED | PPCS `psycopg_commit_tag.txt`: `statusmessage 'ROLLBACK'`, `pgresult.status COMMAND_OK`, through `cursor.execute("COMMIT")`. Ext `../sqla-tx02-repro/commit-tag.md`: the internal `PGresult` of `Connection.commit()`'s own `COMMIT`, one trial, `COMMAND_OK`, tag `ROLLBACK`. The Core case file has no tag field. The tag on the Core path rests on these two and on the shared code path (B4) |
| A4 | Independently verified fate | ANSWERED | `pg_xact_status` was `aborted` at `before-end` and at `after-end`, and the marker was absent, in all 3 repetitions (`64c5c5`). PR-01 `b2c174` agrees |
| A5 | Reproducible without SQLAlchemy | ANSWERED | `psycopg_commit_tag.py`: `commit()` returned `None`, and another connection saw `[]` |

The PostgreSQL 18 `COMMIT` reference page does not state that the tag is `ROLLBACK` (PR-01 README; `commit-tag.md`). The tag comes from `EndTransactionBlock` returning false in `TBLOCK_ABORT`, after which `standard_ProcessUtility` sets `CMDTAG_ROLLBACK`. That is source reading, quoted in `commit-tag.md` (Ext).

**B. psycopg behaviour**

| # | Question | Status | Evidence |
| --- | --- | --- | --- |
| B1 | Does psycopg 3 expose the command tag of `COMMIT`? | ANSWERED | Not through `Connection.commit()`, which returns `None`, nor through `Connection.info` (`commit-tag.md`: "`Connection.info` had none"). Yes through `cursor.execute("COMMIT")`, as `statusmessage` and `pgresult.command_status` (PPCS `psycopg_commit_tag.txt`) |
| B2 | Does its transaction API distinguish a `COMMIT` answered with `ROLLBACK`? | ANSWERED (this audit) | **`Connection.commit()`:** no (PPCS). **`with conn.transaction() as tx:`:** no. The block returns, and `tx.status` is `committed`, while `pg_xact_status` is `aborted`, the marker is absent, and the backend's last statement is `COMMIT`. Audit, 3 of 3, savepoint-recovery control committed. See Appendix A |
| B3 | Does the driver return successfully? | ANSWERED | `commit()` returns `None` and raises nothing (PPCS). The `conn.transaction()` block raises nothing (Audit) |
| B4 | Does the driver observe information it does not expose? | ANSWERED | **The result reaches psycopg:** `_exec_command` returns the `PGresult` and raises only when the status is not `COMMAND_OK` or `TUPLES_OK` (`psycopg/_connection_base.py` 443–493). **Both commit paths discard it:** `Connection._commit_gen` at line 592, and `BaseTransaction._commit_gen` at `psycopg/transaction.py` 140 (Src). **That result carries tag `ROLLBACK`** (Ext `commit-tag.md`) |
| B5 | Is the limitation in psycopg, libpq, or API usage? | ANSWERED | **libpq** exposes the tag: psycopg's cursor path returns it. **psycopg's commit implementations** discard it (Src; PPCS; Audit). **An application can see the state before committing:** `conn.info.transaction_status` is `INERROR` (recorded in the Core trace). Whether `commit()` should raise is psycopg's decision, asked in #1453 |

**C. SQLAlchemy Core behaviour**

| # | Question | Status | Evidence |
| --- | --- | --- | --- |
| C1 | Which API is invoked | ANSWERED | `Connection.begin()` as a context manager (managed), and `Transaction.commit()` (explicit). See `adapters/sqlalchemy-core/adapter.json` and the PR-01 rows in `b2c174`: `committed`, mechanism exercised, 3 of 3 each |
| C2 | Which internal methods execute the commit | ANSWERED | **Src, SQLAlchemy 2.1.5:** `TransactionalContext.__exit__` (`engine/util.py` 126; commits at 140–142), then `RootTransaction._do_commit` (`engine/base.py` 2719), then `Connection._commit_impl` (1157), then `DefaultDialect.do_commit` (`engine/default.py` 953–954), then psycopg `Connection.commit()`. **Order in `_commit_impl`:** `dispatch.commit` fires at line 1159, before `do_commit` at 1170 (Src; A2) |
| C3 | Does SQLAlchemy have the server's command tag? | ANSWERED | No. `do_commit` receives `None`. The psycopg dialect does not override `do_commit`. It reads `transaction_status` only in `get_isolation_level` (`dialects/postgresql/psycopg.py` 548–549) and in the two-phase helper `_twophase_idle_check` (602–607). Neither is on the commit path (Src) |
| C4 | Does SQLAlchemy check transaction state independently? | ANSWERED | No check before `commit()` (Src). After a caught `IntegrityError`, Core leaves the transaction active, so `__exit__` commits (`adapters/sqlalchemy-core/FINDINGS.md`) |
| C5 | Does the documented contract promise more than the implementation? | PARTIALLY ANSWERED | **The recorded contract** is "commits when the block exits without an exception and the transaction is still active" (case-file contract text). It does not promise detection of a server-side rollback. **`ConnectionEvents.commit`** is documented as "Intercept commit() events, as initiated by a Transaction" (quoted from `engine/events.py` 538–540 in the private drafts file §1). It is an initiation hook, not a commit claim (A2; Src). **`SessionEvents.after_commit`** ("Execute after a commit has occurred") ran on the ORM `Session.execute` path after tag `ROLLBACK` (Ext `run-2.txt`, one run). No PPCS run measured that path |
| C6 | Does a correction belong in SQLAlchemy, psycopg, or both? | ANSWERED, as a recorded decision | psycopg. See the tracker's P1, and Core's `FINDINGS.md`: "A second report for `Connection.begin()` would describe one path twice." Judg: agreed. If `commit()` raised, `__exit__` would already roll back and re-raise (`engine/util.py` 140–146). That is Src only, not run |

**D. Upstream work**

| Item | Status |
| --- | --- |
| Upstream issue | [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), filed 2026-10-21. Open, no comments, no labels (Upstream, checked 2026-10-24 with `gh`) |
| Draft | `research/production-reachability/upstream-drafts/psycopg.md`, marked Filed |
| Proposed patch | None. The issue states the expected behaviour and no fix |
| Regression test | None upstream. The reproduction program is in this repository |
| Maintainer response | None as of 2026-10-24. No psycopg commits since 2026-10-20. Open PR #1454 is the fix for #1451, a different bug |
| Root-cause investigation | Yes: Core and ORM `FINDINGS.md`, `psycopg.md` notes, Ext `../sqla-tx02-repro` |
| Documented decision not to file | Yes. `docs/upstream-submissions.md` P1: "Do not also file SQLAlchemy or Django." |

**Remaining work:** wait on #1453, and decide on the follow-up comment in §8.1.

**Smallest useful next investigation:** none. The only open question in this chain was B2 for `conn.transaction()`, and the audit run answered it.

### 3.2 Django migration concurrency (`MG-02`)

| # | Question | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Does `MigrationExecutor` serialize across processes? | ANSWERED: no | **Runtime:** PPCS `178fa4`, `MG-02.held` FAIL 3 of 3, with roles A and B inside the migration at once. **Source:** no lock, `select_for_update`, or `LOCK TABLE` in `django/db/migrations/executor.py`, `recorder.py`, or `core/management/commands/migrate.py` (Src, grep) |
| 2 | Can simultaneous runners execute the same migration twice? | ANSWERED: yes | `MG-02.held` and `MG-02.idle-session-timeout`: A and B both report `applied`, exit 0 |
| 3 | Duplicate writes, or inconsistent history? | ANSWERED for an atomic migration with no deferred SQL | **Duplicates:** marker count 2 (the data write ran twice) and history count 2 (two `django_migrations` rows). **Why two history rows are possible:** the model has no unique constraint on `(app, name)` (`recorder.py` 32–40, Src). **`session-loss`:** marker 1 and history 1, but MG-02.5 fails. **Not measured:** non-atomic migrations (`atomic = False`) and migrations with deferred SQL |
| 4 | Is the `first-deployment` PASS only a history-table collision? | ANSWERED: yes | The losing runner raised `MigrationSchemaMissing`, `23505` on `pg_type_typname_nsp_index` (case file, `178fa4`). `ensure_schema` creates the table in its own transaction (`recorder.py` 69–80, Src). Root README qualifier: "The pass is not evidence of coordination." A redesign of this case exists as uncommitted work on branch `first-deployment-c1`. It is not evidence here |
| 5 | Does it happen when the history table already exists? | ANSWERED: yes | `MG-02.held` starts B after A has created the table and entered the migration. The root README says: "a runner that starts after the table exists, while the first runner is still inside the migration, executes it too" |
| 6 | Does PPCS distinguish executor behaviour from deployment coordination? | PARTIALLY ANSWERED | The adapter drives `MigrationExecutor` directly, not `manage.py migrate` or a deployment pattern (`adapters/django/README.md`). PPCS does not record Django's position that concurrent `migrate` must be prevented at deployment level. Compare Laravel, where the README states that `migrate --isolated` exists and is not measured |
| 7 | Does Django document any concurrency guarantee? | ANSWERED (this audit): no | **Not found** (Doc, checked 2026-10-24): any statement about concurrent or parallel runs or locking, in either [Migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/) or the [`migrate` reference](https://docs.djangoproject.com/en/6.1/ref/django-admin/). **Found**, on the migrations page: "On databases that support DDL transactions (SQLite and PostgreSQL), all migration operations will run inside a single transaction by default." |
| 8 | Does an existing Django ticket or proposal address migration locking? | ANSWERED (this audit): yes, and declined | **#30490** (2019; wontfix; reopened and re-closed 2023). **#34610** (2023; its duplicate). **The 2023 forum thread:** no decision. Details in §5.2 (Upstream, checked 2026-10-24) |

**Classification**

| Category | Applies? | Basis |
| --- | --- | --- |
| A reproducible concurrency hazard | Yes | PPCS `178fa4`, 3 of 3 |
| An explicitly unsupported use case | Yes, by maintainers' statements. Not in the docs | #30490 and the 2023 forum thread: run `migrate` once, or lock outside Django |
| A missing framework capability | Yes | No lock and no uniqueness (Src) |
| A violation of a documented guarantee | No | No guarantee is documented (Doc) |

**Remedies, not implemented**

| Remedy | Fit | Assessment (Judg) |
| --- | --- | --- |
| PostgreSQL advisory lock inside Django | Backend-specific. Django supports several backends and `--database` aliases. A session lock on a separate connection avoids transaction scoping, but needs a design for each backend | Raised in 2019: advisory locks are possible in principle. Also in 2019, a database-level lock held for the whole migration was called "probably not a feasible option" (Simon Charette, #30490). Not accepted |
| Optional locking (opt-in flag) | Smaller change in behaviour. Precedent in other ecosystems, e.g. Laravel's `migrate --isolated` | The 2023 forum advice: "It's worth experimenting in your own projects or a third-party package before suggesting anything to Django." A package outside Django fits that advice |
| Deployment-level serialization | No code change | What the maintainers recommend. Not measured in PPCS |
| A separate migration runner, such as one job per deploy | Same as above | Same as above |
| Documentation | The docs are silent on concurrent `migrate` runs | The one plausible upstream contribution. A forum post first, per Django's process for features (#34610) |
| Unique constraint on `django_migrations(app, name)` | Rejected in 2019, and the 2023 forum thread reached no decision | Even for atomic migrations, both runners do the work, and the loser fails late (2023 forum). It is not measured here |

**Verdict.** Already discussed upstream. Not ready for, and not suited to, a bug report. PPCS's contribution would be its measured PostgreSQL evidence for a documentation proposal on the forum. That is low priority (§7).

### 3.3 Django savepoint recovery (`TX-02`)

| Question | Status | Evidence |
| --- | --- | --- |
| Exact failure-injection point | ANSWERED | `adapters/django/main.py`: `cursor_gate` (232–244) is installed with Django's documented `connection.execute_wrapper` (1227). It raises `RuntimeError("injected client-side failure: ROLLBACK TO SAVEPOINT was not sent")` for the first `ROLLBACK TO SAVEPOINT`. The case file's `diagnostics.adapter.withheld` lists `ROLLBACK TO SAVEPOINT "s8398037376_x1"` |
| Does Django observe an exception? | ANSWERED | Yes. The `RuntimeError` replaces the application's `AppError` as the exception that leaves the inner `atomic()`, and the application catches it (`api_outcome.steps.nested.error.class` is `RuntimeError`, `6d8443`) |
| Before or after the database operation? | ANSWERED | Before. At `after-fault` the session was `idle in transaction`, still holding the savepoint's subtransaction lock (`6d8443`, `adapters/django/FINDINGS.md`) |
| How `atomic()` updates its state | ANSWERED | Src, `django/db/transaction.py`: the failure path clears `needs_rollback` (286). It calls `savepoint_rollback` (294) inside `except Error:` (298), which sets `needs_rollback = True` (302). A `RuntimeError` is not `django.db.Error`, so the flag stays false. The outer exit takes `exc_type is None and not connection.needs_rollback` (253) and calls `connection.commit()` (274) |
| Is the outer transaction marked rollback-only? | ANSWERED: no | Case diagnostics: `needs_rollback: false`, `commit_calls: 1` |
| Does Django then commit the outer transaction? | ANSWERED: yes | xid 838 committed. Both markers were visible. The session was idle, so TX-02.2 held (`6d8443`, 3 of 3) |
| Does this violate a documented guarantee? | PARTIALLY ANSWERED | `FINDINGS.md` quotes "If there is an exception, the changes are rolled back". It notes that the `DatabaseError` admonition covers database errors, not this `RuntimeError`. Judg: no documented sentence covers a failure of the savepoint rollback itself, so a violation is not established |
| Can a realistic production failure produce the same outcome without injection? | UNANSWERED, with negative evidence | **Passes (PPCS `6d8443`):** a backend terminated before the savepoint rollback (category B; Django saw `OperationalError` "the connection is lost"), and a PostgreSQL `3B001` rejection. **Rolls back (Ext `run-1.json`, arm 2a, one run):** the same withhold raised as `DatabaseError`. The FAIL needs an `Exception` that is not `django.db.Error` and not a `BaseException`-only exit, raised before send, that the application then catches. No such source is observed in production |

**Smallest missing experiment.** None worth running now.

- **Already measured:** PPCS's trigger already is a documented Django hook, `execute_wrapper`.
- **The open question** is whether production code raises non-database exceptions at exactly that point, for example from a signal handler or from instrumentation. That is a frequency question, which a fault-injection run cannot answer. It is H7 in §4.2.

**Assessment.**

- **No Django issue, regression test, or documentation change is proposed.**
- **`adapters/django/FINDINGS.md`** already recommends: "Keep the case in PPCS only."
- **The same open question holds SQLAlchemy's Draft B** (§5.1).

### 3.4 Tortoise ORM on asyncpg (`TX-01A`)

| Question | Status | Evidence |
| --- | --- | --- |
| Does Tortoise attempt `COMMIT` after the caught exception? | ANSWERED: yes | PPCS `c45624`, `cases/TX-01A.caught-error-then-commit.tortoise.native.json`, driver trace: `BEGIN; -> BEGIN`, `COMMIT; -> ROLLBACK`, then the pool reset. FAIL in 3 of 3. Ext `../tortoise-tx-investigation`, case `TO-04-commit-of-aborted`: asyncpg state `STARTED` before commit, commit status `ROLLBACK`, nothing visible |
| Does asyncpg report the actual outcome? | ANSWERED at the driver call. The transaction helper discards it | **`Connection.execute()` returns the status string,** documented as ":return str: Status of the last SQL command" (`asyncpg/connection.py` 320, 348). It returned `ROLLBACK` for `COMMIT;` (trace, diagnostic). **`Transaction.__commit` discards that value,** awaiting `self._connection.execute(query)` and then setting `_state = TransactionState.COMMITTED` (`asyncpg/transaction.py` 175–192, Src). **`Transaction.commit()` returned without raising**, because no exception reached Tortoise (observed) |
| Does Tortoise suppress or transform driver information? | ANSWERED for this path | **Tortoise never receives the tag:** `TransactionWrapper.commit()` awaits asyncpg's `self.transaction.commit()` (`tortoise/backends/asyncpg/client.py` 197–203), and `TransactionContextPooled.__aexit__` calls it on a clean exit (`tortoise/backends/base/client.py` 373–381) (Src). **Separate path (A2):** Tortoise maps asyncpg `InvalidTransactionStateError`, class 25 including `25P02`, to `TransactionManagementError`, and `__aexit__` skips rollback for exactly that type. The mapping is observed in Ext `TO-04`, where a query after the caught `23505` raised `TransactionManagementError sqlstate=25P02`. The skipped rollback is not run |
| Does connection-pool cleanup obscure the final transaction state? | ANSWERED: it obscures the mechanism, not the fate | **The pool reset:** on release, asyncpg's `_reset` sends `ROLLBACK` only when the protocol is still in a transaction. It then runs the reset query (`asyncpg/connection.py` 1550–1594, Src). **Its effect on the observer:** at `after-end` the backend's last statement is that query, so `mechanism_exercised` is false. The methodology calls this an understatement (`docs/methodology.md`, "TX-01A reads the session's last statement"). **The fate was settled earlier:** `pg_xact_status` was already `aborted` at `before-end` |
| Driver or ORM? | ANSWERED: the driver's transaction API (A2, runtime) | **Verified:** asyncpg's transaction helper discards a status that asyncpg itself exposes, and Tortoise reports success when that helper returns (PPCS and Src). **asyncpg alone** (A2, runtime, 3 of 3, asyncpg 0.32.0, no Tortoise): `async with conn.transaction()` exits normally, and `repr` shows `state:committed`; `Transaction.start()` and `commit()` return `None`; a raw `execute('COMMIT')` returns `'ROLLBACK'`. PostgreSQL aborted, the last statement was `COMMIT;`, and a nested-savepoint control committed. Tortoise passes the driver's result through |
| Production-reachable reproduction? | ANSWERED: yes | Category A, no injection (`c45624`; Ext `TO-04`). Tortoise is not a PR-01 row, so there are no hook or savepoint-recovery rows for it |

**Compared with the other Python stacks:**

- **SQLAlchemy Core** has the same structure, but the tag is lost one layer lower: psycopg's `commit()` exposes nothing, while asyncpg's `execute()` does expose it.
- **Django `atomic()` and the SQLAlchemy ORM flush** are a different mechanism: the framework never sends `COMMIT` (§4.3).

### 3.5 Cross-language comparison (Part 6)

**PARTIALLY ANSWERED.** `main` has evidence for each stack, and one explanatory paragraph:

- [`docs/caught-unique-violation.md`](../docs/caught-unique-violation.md);
- [`docs/go-persistence.md`](../docs/go-persistence.md);
- PR-01 README "Upstream": "pgx treats command tag `ROLLBACK` as a failed commit. node-postgres, psycopg, and pgjdbc leave that tag for the caller, or do not surface it."

The systematic boundary model is on the unmerged `research/transaction-outcome-propagation` branch, and it has no Python driver records. §4.3 gives the taxonomy the recorded evidence supports.

### 3.6 Production reachability (Part 7)

**ANSWERED** for the recorded findings. See §6. PR-01 already established it for the caught-`23505` path. Do not repeat it.

## 4. Root-cause findings

### 4.1 The five commit APIs, side by side

After a caught `23505`, each API ends normally. In each case PostgreSQL aborted the transaction (`pg_xact_status` `aborted`, marker absent).

| API | What the application sees | What reached PostgreSQL | Responsible layer | Evidence |
| --- | --- | --- | --- | --- |
| psycopg `Connection.commit()` | Returns `None`. No exception | `COMMIT`, completed with tag `ROLLBACK` | **psycopg:** `Connection._commit_gen` discards the `PGresult` | PPCS `psycopg_commit_tag.txt`; Ext `commit-tag.md`; Src |
| psycopg `with conn.transaction() as tx:` | Block exits normally. `tx.status == "committed"` | `COMMIT` (last statement `COMMIT`, backend idle) | **psycopg:** `BaseTransaction._commit_gen` sets `COMMITTED` (line 135) before sending `COMMIT` (line 140), and discards the result | Audit, 3 of 3; Src |
| SQLAlchemy Core `with conn.begin():` and `Transaction.commit()` | Returns normally. The Core `commit` event fired, but it fires before the DBAPI call | `COMMIT` while psycopg was `INERROR` | **psycopg**, surfacing through Core. Core calls `commit()` because its transaction is still active, and does not check driver state | PPCS `64c5c5` FAIL 3 of 3; PR-01 `b2c174`, managed and explicit, 3 of 3; Src |
| Django `transaction.atomic()`, ORM writes | Block exits normally, with no exception. `on_commit` callbacks are discarded | `ROLLBACK`. `COMMIT` is never sent | **Django prevents it.** The ORM write runs under `mark_for_rollback_on_error`, so `needs_rollback` is true, and `Atomic.__exit__` rolls back | PPCS `6d8443` PASS, mechanism not exercised; PR-01 `b2c174` PASS; Src |
| Django manual: `set_autocommit(False)`, then `transaction.commit()` | Returns normally. `on_commit()` is not available in this mode | `COMMIT`, last statement `COMMIT`. A later transaction on the same connection committed | **psycopg.** Django's docs: with autocommit off, "you get the default behavior of your database adapter, and Django won't help you" | PR-01 `508b7a`, 3 of 3; Doc |

**A note on the Django `atomic()` PASS.** It is a silent rollback: the `with` block returns without an exception. PPCS passes it on the database outcome and on Django's documented contract, under which a database error makes Django roll back at the end of the block. The application learns of the rollback only because `on_commit` did not run.

**The same scenario through the remaining Python APIs:**

| API | What the application sees | What reached PostgreSQL | Responsible layer | Evidence |
| --- | --- | --- | --- | --- |
| SQLAlchemy ORM `with Session.begin():`, flush error caught | Block exits normally. `after_commit` does not run; `after_rollback` does | `ROLLBACK`, sent by `Session._flush` | **SQLAlchemy ORM** rolls back during flush | PPCS `3673a3` INCONCLUSIVE (precondition); PR-01 `b2c174` "DOCUMENTED / EXPECTED" |
| SQLAlchemy ORM `SessionTransaction.commit()`, explicit | Raises | `ROLLBACK` | SQLAlchemy ORM | PR-01 `b2c174` PASS |
| SQLAlchemy ORM: `Session.execute()` raises the error (raw SQL, or Core DML through the session), which is caught, then commit | `after_commit` runs | `COMMIT`, tag `ROLLBACK` | **The driver's commit returning**, on psycopg or asyncpg, surfacing through the ORM's event | Ext `run-2.txt`, one run (Draft C); A2, runtime, 3 of 3, on psycopg `Session` and on asyncpg `AsyncSession` |
| Django `atomic()` with a raw-cursor write, error caught | Block exits normally. **`on_commit` runs** | `COMMIT`, tag `ROLLBACK` | **Django precondition, then psycopg.** See §4.1.1 | Ext `run-1.json` arm 4b, one run |
| Tortoise `in_transaction()` | Block exits normally, reported committed | `COMMIT;`. asyncpg's `execute()` returned `ROLLBACK` | **asyncpg's `Transaction.commit()`** discards the status. Tortoise reports the return | PPCS `c45624` FAIL 3 of 3; Ext `TO-04`; Src |
| asyncpg `async with conn.transaction()`, or explicit `Transaction.commit()` | Returns normally. `repr` shows `state:committed` | `COMMIT;`, the last statement | **asyncpg:** `Transaction.__commit` discards the status string | A2, runtime, 3 of 3; Src |
| SQLAlchemy Core on `postgresql+asyncpg`, `engine.begin()` | Returns normally | `COMMIT;` | **asyncpg**, surfacing through Core | A2, runtime, 3 of 3 |

#### 4.1.1 Django `on_commit` on the raw-cursor path (Ext, one run)

Source: `../python-orm-transactions/docs/django-transaction-review.md` §4. Recorded run: `docs/django-transaction-experiments/recorded/run-1.json`. Django 6.1.2 at commit `2212534b`, psycopg 3.3.6, PostgreSQL 18.6, same image digest. Each arm ran once.

| Arm | Path | Ending command | `on_commit` | Visible |
| --- | --- | --- | --- | --- |
| 4a | ORM `23505` caught inside `atomic()` | `ROLLBACK`, tag `ROLLBACK` | not called | none |
| 4b | Raw-cursor `23505` caught inside `atomic()` | `COMMIT`, tag `ROLLBACK` | ran | none |
| 4c | ORM `23505`, then `set_rollback(False)` while still `INERROR` | `COMMIT`, tag `ROLLBACK` | ran | none |
| 1b, 5c | Raw `23505`, then a nested `atomic()`, or `savepoint=False` | `COMMIT`, tag `ROLLBACK` | ran | none |

In arm 4b, the recorded flags after the raw error were `needs_rollback: false`, psycopg `INERROR`, and one pending `on_commit`. A follow-up insert failed with `25P02`. The API raised nothing. The commands were `BEGIN` (tag `BEGIN`) and `COMMIT` (tag `ROLLBACK`).

**Why.** The private review reads Django's source as follows:

- `Model.save()` and `QuerySet.update()` wrap writes in `mark_for_rollback_on_error`, and `CursorWrapper.execute()` does not. So a caught raw error leaves the flag false.
- With the flag false, `Atomic.__exit__` calls `connection.commit()`.
- psycopg returns (§4.1).
- Django then runs the `on_commit` callbacks.

This audit confirmed the `Atomic.__exit__` lines, not the `models/base.py` lines.

**Qualification.** Django documents this path as unspecified (Doc, [transactions](https://docs.djangoproject.com/en/6.1/topics/db/transactions/), checked 2026-10-24): "If you catch exceptions raised by raw SQL queries, Django's behavior is unspecified and database-dependent." Arm 4c clears the flag in a state the documentation tells callers not to clear it in. The `on_commit` contract reads: "Callbacks are called after the open transaction is successfully committed. If the transaction is instead rolled back (…), the callback will be discarded, and never called."

**Assessment (Judg).**

- **A documented after-commit hook ran for a transaction PostgreSQL aborted.** That is a stronger consequence than a returned call, because applications use `on_commit` for side effects.
- **The trigger is a path Django disclaims**, and the false success is psycopg's `commit()` returning. If psycopg raised, `Atomic.__exit__` would roll back and discard the callbacks. That is H1 below, and it was not run.
- **Not a Django report.** It is impact context for #1453. This is consistent with the tracker's P1 decision.

### 4.2 Verified root causes and hypotheses

**Verified**, by runtime observation and source:

| ID | Root cause | Layer | Evidence |
| --- | --- | --- | --- |
| V1 | `COMMIT` of a failed transaction block completes with `COMMAND_OK` and tag `ROLLBACK`. No error | PostgreSQL, by design | PPCS `psycopg_commit_tag.txt`; Ext `commit-tag.md` (source quoted) |
| V2 | `Connection.commit()` discards that result and returns `None` | psycopg 3.3.6 | PPCS; Src `_connection_base.py` 577–592 |
| V3 | `conn.transaction()` discards it too, and reports `Transaction.status` `committed` | psycopg 3.3.6 | Audit; Src `transaction.py` 133–140 |
| V4 | SQLAlchemy Core's success on TX-01A is V2. Core leaves the transaction active after a caught error, and commits without checking driver state | SQLAlchemy Core, then psycopg | PPCS `64c5c5` and `b2c174`; Src |
| V5 | Django manual `commit()` success is V2 | psycopg, through Django's documented manual mode | PR-01 `508b7a`; Doc |
| V6 | Django `atomic()` with ORM writes never sends `COMMIT`: `needs_rollback` is set, and the block rolls back | Django | PPCS `6d8443`, PR-01 `b2c174`; Src `transaction.py` 253, 274, 286–302 |
| V7 | Django `atomic()` with a caught raw-cursor error commits, gets tag `ROLLBACK`, and runs `on_commit` | Django precondition (documented as unspecified), then V2 | Ext `run-1.json` arm 4b, one run; Doc |
| V8 | SQLAlchemy ORM managed: the flush rolls back before the block ends, so there is no `COMMIT` | SQLAlchemy ORM | PPCS `3673a3`; PR-01 `b2c174` |
| V9 | Tortoise reports success: asyncpg `execute("COMMIT;")` returned `ROLLBACK`, and `Transaction.commit()` discarded it. The pool reset then hides `COMMIT` from `pg_stat_activity` | asyncpg transaction helper, then Tortoise | PPCS `c45624` trace; Src asyncpg `transaction.py` 175–192, `connection.py` 1550–1594 |
| V10 | Django TX-02 not-sent: a non-`django.db.Error` raised during `savepoint_rollback` leaves `needs_rollback` false, so the outer block commits both scopes. Raised as `DatabaseError`, the same withhold rolls back | Django error handling (`except Error` only) | PPCS `6d8443`; Src `transaction.py` 294–302; Ext arm 2b against 2a |
| V11 | Django MG-02: no lock and no uniqueness. History is recorded inside the migration's transaction when there is no deferred SQL. Both runners commit | Django migrations | PPCS `178fa4`; Src `executor.py` 254–260, `recorder.py` 32–40 |
| V12 | `MG-02.first-deployment` passes only because creating the history table collides | Django migrations, then PostgreSQL catalog uniqueness | PPCS `178fa4`; Src `recorder.py` 69–80 |
| V13 | asyncpg's public transaction API returns normally, with state `committed`, after tag `ROLLBACK`. A raw `execute('COMMIT')` returns `'ROLLBACK'` | asyncpg 0.32.0 | A2, runtime, 3 of 3; Src `asyncpg/transaction.py` 175–192 |
| V14 | SQLAlchemy Core on asyncpg returns normally from `engine.begin()` | asyncpg, surfacing through SQLAlchemy's adapter (`dialects/postgresql/asyncpg.py` 919–926) | A2, runtime, 3 of 3 |
| V15 | SQLAlchemy ORM runs `after_commit` when `Session.execute()` raised the caught error, on psycopg and on asyncpg. It does not when flush raised | The driver's discard, surfacing through the ORM event | A2, runtime, 3 of 3; Ext `run-2.txt` |

**Hypotheses** (not verified):

| ID | Hypothesis | Basis |
| --- | --- | --- |
| H1 | If psycopg raised on tag `ROLLBACK`, SQLAlchemy Core would roll back and re-raise, and Django `atomic()` would roll back and discard `on_commit` | Src: SQLAlchemy `engine/util.py` 140–146; Django `Atomic.__exit__`'s `except DatabaseError` around `commit()` (`transaction.py` 274–275) |
| H2 | A psycopg fix in `_exec_command` would cover both commit paths. A fix only in `Connection._commit_gen` would not cover `conn.transaction()` | Src |
| H3 | asyncpg's public `Connection.transaction()`, without Tortoise, also returns normally on tag `ROLLBACK` | Verified by Agent 2's runtime run after this section was drafted. Now V13 |
| H4 | SQLAlchemy's asyncpg dialect reports success the same way. `commit()` calls asyncpg's `Transaction.commit` through `_call_and_discard` (`dialects/postgresql/asyncpg.py` 919–926) | Verified by Agent 2's runtime run. Now V14 |
| H5 | In Tortoise, a nested block that leaves with `25P02` never sends `ROLLBACK TO SAVEPOINT` | A2, Src (`backends/asyncpg/client.py` 96–97; `backends/base/client.py` 378–379, 403–404). The mapping is observed in Ext `TO-04`. The consequence is not run |
| H6 | A `COMMIT` that raises inside `conn.transaction()` also leaves `status` as `committed` | Src `transaction.py`: status set at 135, before the command at 140; `FAILED` set only at 272–274. Not run |
| H7 | Production code raises non-database exceptions inside the savepoint-rollback window, for example from signal handlers or instrumentation | None observed |
| H8 | A unique constraint on `django_migrations(app, name)` would make the second runner of an atomic migration fail | Src. The 2023 forum thread says the loser still does the work and fails late. Not measured |
| H9 | Non-atomic Django migrations, and migrations with deferred SQL, also double-apply. With deferred SQL, history may be recorded after `COMMIT` | Not measured in PPCS. A comment on Django #29721 reports recording after `COMMIT` for deferred SQL (Upstream) |

### 4.3 Taxonomy of mechanisms across stacks

Where the `ROLLBACK` tag stops being acted on. It is built from recorded evidence. Where the evidence is source reading, that is stated.

| Mechanism | Where the information stops | Stacks, with evidence | Recorded outcome |
| --- | --- | --- | --- |
| T1. The driver turns the tag into an error | Nowhere | pgx v5.11.0 `Tx.Commit` returns `ErrTxCommitRollback`, and so do `database/sql` and GORM through it (`reports/examples/2026-10-22T13-24-28Z-606909`, `docs/go-persistence.md`) | PASS, mechanism exercised |
| T2. The framework or application reads the driver's public tag | Nowhere | MikroORM 7.2.6-dev.19 (`research/production-reachability/runs/2026-10-22T12-18-31Z-928c75`); `pg-control` `correct`; node-postgres "check-tag" (PR-01) | PASS |
| T3. The driver exposes the tag in a return value, and the layer above discards it | The framework, or the driver's own transaction helper | **node-postgres `Result.command`:** Knex, Kysely, Lucid, MikroORM 7.2.5, TypeORM, Drizzle, Prisma (PR-01; suite). **asyncpg `Connection.execute()` status:** asyncpg `Transaction.commit()`, then Tortoise and SQLAlchemy's asyncpg dialect (V9, V13, V14). **ruby-pg `cmd_status`:** Active Record (suite FAIL, mechanism exercised; the ruby-pg probe on the propagation branch read `ROLLBACK`) | FAIL |
| T4. The driver's commit API returns success and does not expose the tag | The driver API | **psycopg** `Connection.commit()` and `conn.transaction()`, then SQLAlchemy Core and Django manual `commit()` (V2–V5). **pgjdbc** `commit()` is void, and the driver state was `FAILED` before it; then Spring and jOOQ (pgjdbc #4494 asks whether `commit()` should report it). **pdo_pgsql** `PDO::commit()` returned true, with the tag "not exposed"; then Laravel. **Npgsql** `CommitAsync` and **SQLx** `commit` returned success. Whether those two expose the tag elsewhere is not established here | FAIL |
| T5. The framework tracks the failure and never sends `COMMIT` | n/a | Django `atomic()` with ORM writes (V6). SQLAlchemy ORM flush (V8). Hibernate sends `ROLLBACK`, then `commit()` returns, so its PPCS report is still `committed`. EF Core `SaveChangesAsync` rolls back to an automatic savepoint and the transaction stays usable | PASS (Django). INCONCLUSIVE (SQLAlchemy ORM, EF Core native). FAIL (Hibernate: success reported after its own rollback) |
| T6. Application-side hardening | n/a | Lucid `pre-commit-probe` | PASS, mechanism not exercised |

The Python stacks span T3 (asyncpg), T4 (psycopg) and T5 (Django `atomic()`, SQLAlchemy ORM). They should not be grouped as one TX-01A failure.

- **The T4 rows have one remedy:** a driver change, which is #1453.
- **The T3 asyncpg row's remedy is in asyncpg's transaction helper.** Agent 2's driver-only run (V13) places it there. The report is §8.2.
- **The T5 rows are correct prevention,** with an application-visible signal that is easy to miss: no exception. Rows that need the framework to have a rollback signal at all are V7 and arm 4c.

### 4.4 Contradictions with existing PPCS text, and suggested corrections

These are documentation corrections. No measurement changes. None of them was applied: the shared files are outside this audit's scope, and some carry another session's uncommitted edits.

1. **The SQLAlchemy Core commit event.**
   - **Where:** `docs/caught-unique-violation.md` lists "SQLAlchemy Core 2.1.5, including the connection commit event". The PR-01 README matrix says "connection `commit` event fired".
   - **The problem:** that event fires before the DBAPI call (`engine/base.py` 1159 before 1170), and is documented as intercepting a commit "as initiated by a Transaction". It is not a commit claim. The false-success signal is `Connection.begin()` or `Transaction.commit()` returning. (A2; Src.)
2. **"Django `atomic()` rolls back."**
   - **Where:** the root README, `docs/caught-unique-violation.md`, and the PR-01 "Answers".
   - **The problem:** this holds for ORM writes. A caught raw-cursor error inside `atomic()` takes the commit path, and `on_commit` runs (§4.1.1, Ext, a path documented as unspecified). The scope of the sentence should say ORM writes.
3. **Stale Django FAIL count.** The root README's Django bullet says "One framework FAIL", then lists FAILs for `MG-02.held`, `MG-02.session-loss` and `MG-02.idle-session-timeout`. The count predates the migration recording.
4. **"Same shape as a failed send."**
   - **Where:** `adapters/django/README.md` says the withheld statement "raises `RuntimeError` with no SQLSTATE, the same shape as a failed send."
   - **The problem:** in Django's category B case (`6d8443`, `TX-02.conn-lost-before-savepoint-rollback`), the lost connection surfaced as `OperationalError` ("the connection is lost"), which is a `django.db.Error`. The injected shape is what makes the FAIL. A send that fails on a live socket was not measured.
5. **Catalog wording in Python case files.** The case files' `fault.mechanism` for `TX-02.savepoint-rollback-not-sent` names node-postgres's `pg.Client.prototype.query`, even for the Python adapters (`6d8443`, `c45624`). The adapters' manifests describe their own injection. The catalog text does not.
6. **Uncited provenance.** `adapters/sqlalchemy/FINDINGS.md` and `adapters/sqlalchemy-core/FINDINGS.md` cite "a later measurement on these same versions" without a path. It is `../sqla-tx02-repro/commit-tag.md`, which is not under version control (§8, housekeeping).
7. **Known, not new.** The mapping of SQLAlchemy ORM managed `reported: committed` differs from Django `atomic()`'s `rolled_back`, though both blocks returned normally after an internal rollback. `docs/research-status.md` §6 already says to read the hooks before treating that field as a commit claim.
8. **SQLAlchemy ORM `after_commit` in PR-01's "Answers".**
   - **Where:** the PR-01 README lists "SQLAlchemy ORM's `after_commit` / `after_rollback` events" among the signals that distinguished the abort.
   - **The problem:** that holds when flush raised the error. When `Session.execute()` raised it, `after_commit` fires on a transaction PostgreSQL aborted, on psycopg and on asyncpg (V15: A2, runtime, 3 of 3; Ext `run-2.txt`). The sentence needs that scope.

## 5. Existing upstream work

### 5.1 Python items

| Project | Finding | Evidence | Existing issue | Status | Maintainer response | Remaining action |
| --- | --- | --- | --- | --- | --- | --- |
| psycopg | `Connection.commit()` returns after tag `ROLLBACK` | `psycopg_commit_tag.py` and `.txt`; `64c5c5`; `b2c174`; `508b7a`; Ext `commit-tag.md` | [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453) | Filed 2026-10-21. Open | None (checked 2026-10-24) | Wait. Optional follow-up comment (§8.1) |
| psycopg | `conn.transaction()` returns, and `Transaction.status` is `committed` | Audit (Appendix A) | Not in #1453's body (checked 2026-10-24) | Not filed | — | A comment on #1453 after approval, not a new issue (§8.1) |
| SQLAlchemy | Core `Connection.begin()` reports success on TX-01A | `64c5c5`, `b2c174` | None | Not filed, by decision (tracker P1; Core `FINDINGS.md`) | — | None while #1453 is open |
| SQLAlchemy | P5a: failed `commit()`, then `Connection.close()` returns the connection with its transaction open; the next checkout commits the doomed writes | Ext `sqlalchemy-p5a-close-review.md`: CONFIRMED DEFECT; two documented guarantees contradicted; reachable without replacing a DBAPI method, through a raising `ConnectionEvents.commit` listener; absent in 1.3.24 | None found (the review's duplicate search, 2026-10-18) | Draft approved, not submitted | — | Post in the author's own words (§8.3) |
| SQLAlchemy | Draft A, SA-03: a failed root `rollback()` clears the marker. The next `begin()` on the same checked-out connection commits the doomed writes | Ext `run-2.txt`, `lifecycle-close-reuse.md` | None | Draft, not submitted. Posting order: after P5a | — | After P5a's reception |
| SQLAlchemy | Draft B, SA-02: a caught failed `ROLLBACK TO SAVEPOINT`, then the outer commit commits the inner writes. The same ending as PPCS TX-02 not-sent | PPCS `3673a3`, `64c5c5`; Ext `run-2.txt` | None | Draft held "until a driver-boundary failure is tried" | — | Hold (H7) |
| SQLAlchemy | Draft C, SA-04: tag `ROLLBACK` reported as success; `after_commit` runs on the `Session.execute` path | Ext `run-2.txt`, one run; A2, runtime, 3 of 3 on psycopg and asyncpg (V15) | None | Draft, not submitted. Overlaps #1453, the tracker's later decision | — | Hold. Reconsider if psycopg or asyncpg declines; the `after_commit` contract is then SQLAlchemy's own question |
| Django | Manual `transaction.commit()` after a caught error | PR-01 `508b7a` | Named in #1453's body | Not filed, by decision | — | None |
| Django | `atomic()` raw-cursor path runs `on_commit` after tag `ROLLBACK` | Ext `run-1.json` arm 4b, one run | None | Not filed. Documented as unspecified | — | None. It is downstream of #1453 (H1) |
| Django | `MigrationExecutor` does not serialize runners | PPCS `178fa4` | #30490, #34610, forum 2023 | Already discussed; declined | "avoid to run the `migrate` command in parallel" (forum 2023) | Optional documentation proposal on the forum (§10) |
| Django | TX-02 not-sent FAIL | PPCS `6d8443` | None | Not filed. `FINDINGS.md`: "Keep the case in PPCS only" | — | None |
| asyncpg (Tortoise and SQLAlchemy's asyncpg dialect pass it through) | `Transaction.commit()` and `async with conn.transaction()` report success after tag `ROLLBACK` | PPCS `c45624`; Ext `TO-04`; A2, runtime, 3 of 3, driver only (V13); Src | None known. Agent 2's duplicate search was in progress at 07:55 PDT | Not drafted | — | Draft a #1453-shaped report after the search (§8.2) |
| Alembic | Two concurrent `upgrade head` runs on an empty database | Ext `alembic-upgrade-race/REPORT.md`, a passing control | None | Not planned: "No further Alembic work from this result" | — | None |

### 5.2 Django migration-locking history (Upstream, checked 2026-10-24)

- **[#30490](https://code.djangoproject.com/ticket/30490), "migrations unique_index on (app, name)."**
  - **2019:** opened 2019-05-19 after a `RunPython` migration ran twice from several Kubernetes replicas. Closed wontfix in 2019.
  - **The 2019 discussion:**
    - a database-level lock held for the whole migration was called "probably not a feasible option";
    - advisory locks were mentioned as possible in principle;
    - running `migrate` as a separate job was recommended.
  - **2023:** reopened on 2023-06-05 with the argument that application and recording now share a transaction. Closed again: "before reaching a consensus on the forum".
- **[#34610](https://code.djangoproject.com/ticket/34610)** (2023-05-31). A unique constraint on `django_migrations`. Closed as a duplicate of #30490.
- **[The forum thread](https://forum.djangoproject.com/t/add-unique-key-for-django-migration-tracking-model/21283)** (June 2023, last post 2023-06-16). No decision. Participants recommended avoiding parallel `migrate` runs, and said a unique constraint would let both runners do the work, with the loser failing late. "It's worth experimenting in your own projects or a third-party package before suggesting anything to Django."
- **Adjacent work:**
  - **[#29721](https://code.djangoproject.com/ticket/29721)** (fixed: "Ensured migrations are applied and recorded atomically"). A later comment reports that migrations with deferred SQL still record after `COMMIT`.
  - **[#37406](https://code.djangoproject.com/ticket/37406)** (opened 2026-10-07, accepted, patch pending). The schema editor's atomic block is not exited when deferred SQL raises.
  - Neither ticket is about concurrency.

Quotations are as the pages rendered on 2026-10-24.

## 6. Production-reachability assessment

Fault categories follow [`docs/methodology.md`](../docs/methodology.md):

- **A:** an error PostgreSQL generated;
- **B:** a server-side termination;
- **C:** a client-side injection;
- **D:** a client-side simulation;
- **E:** a protocol-proxy fault.

Injected and simulated results show what a framework does if the failure happens. They say nothing about frequency.

| Finding | Trigger | Reachable without injection? | Evidence |
| --- | --- | --- | --- |
| psycopg `Connection.commit()` after a caught error (and Core, and Django manual) | A: an ordinary `23505` | Yes. PR-01 R1 for Core; R2 for Django manual (a documented API, but not the one Django recommends) | PR-01 `b2c174`, `508b7a` |
| psycopg `conn.transaction()` | A | Yes | Audit |
| Tortoise `in_transaction()` | A | Yes | PPCS `c45624`; Ext `TO-04` |
| asyncpg `conn.transaction()` and `Transaction.commit()`; SQLAlchemy on asyncpg | A | Yes | A2, runtime, 3 of 3 |
| Django `atomic()` raw-cursor `on_commit` | A, on a path Django documents as unspecified | Yes, but documented as unsupported behaviour | Ext arm 4b |
| SQLAlchemy ORM `Session.execute` `after_commit` | A | Yes | Ext `run-2.txt`; A2, runtime, 3 of 3 |
| TX-02 rejected, `3B001` (SQLAlchemy ORM, Core, Tortoise) | C: an artificial trigger of a real PostgreSQL error | The trigger is not. The ending reduces to the TX-01A mechanism, which is reachable | PPCS `3673a3`, `64c5c5`, `c45624` |
| TX-02 not-sent (Django, SQLAlchemy ORM and Core, Tortoise) | C: a non-database exception raised before send | Not established. Django's B and `3B001` analogues pass | PPCS `6d8443`, `3673a3`, `64c5c5`, `c45624` |
| TX-03, all three cases (all Python adapters) | C and B | — (all PASS) | PPCS runs above |
| Lost `COMMIT` reply (all Python adapters) | E | — (PASS, TX-01B.2 not exercised) | PPCS `87af6a` |
| SQLAlchemy P5a | A commit that raises before PostgreSQL processes `COMMIT`, on a healthy connection | Through documented hooks (a raising `ConnectionEvents.commit` listener), or by mixing psycopg's `transaction()` with SQLAlchemy. The review: "No real driver failure produces this", and frequency is not established | Ext review |
| SQLAlchemy Draft A (SA-03) | An injected rollback failure | Not established | Ext |
| Django MG-02 | No fault, only concurrency (B for `session-loss`) | Yes, wherever deployments run `migrate` concurrently, which maintainers advise against | PPCS `178fa4` |

**Not executed anywhere:** deadlock (`40P01`), serialization failure (`40001`) and statement timeout (`57014`) inside a caught-then-commit block. PR-01 argues they take the same command-tag path. Agent 2 treats them as PR-01 variants unless a framework branches on the SQLSTATE.

## 7. Ranked remaining opportunities

Category key:

- **Solved:** already solved internally;
- **Ready:** ready for upstream;
- **One exp.:** one experiment away;
- **Research:** requires substantial research;
- **Low:** low priority.

| Rank | Opportunity | Category | Production relevance | Severity | Evidence | Effort | Acceptance (Judg) | Layer identified | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | psycopg `conn.transaction()` and `Transaction.status` on #1453 | Ready (comment) | High: A-category, psycopg's own recommended transaction API | A false commit report, through a public status flag | Strong: Audit 3 of 3 with control, plus Src | Hours | Likely useful: the attribute exists to record this | Yes (psycopg) | §8.1 |
| 2 | asyncpg `Transaction.commit()`, under Tortoise and SQLAlchemy's asyncpg dialect | Ready, after the duplicate search | High: A-category. asyncpg underlies Tortoise and SQLAlchemy's asyncio dialect (V13, V14) | A false commit report, with transaction state `committed` | Strong: PPCS FAIL plus Agent 2's driver-only run, 3 of 3. That run is not yet in this repository | Hours | Unknown. The same question is open with psycopg | Yes (asyncpg) | §8.2 |
| 3 | SQLAlchemy P5a | Ready (outside PPCS) | Moderate: needs a commit that raises before `COMMIT` is processed | Doomed writes committed by later work | Strong: adversarial review | Hours, user-written | Uncertain: a precedent (#13381) rejected a similar class | Yes (SQLAlchemy) | §8.3 |
| 4 | Preserve the unversioned evidence; correct the PPCS text in §4.4 | Solved, needs preservation | Indirect | — | n/a | Hours | n/a | n/a | Housekeeping, below |
| 5 | Python records in the propagation study (psycopg, asyncpg), using the adapter virtualenvs | One exp. (internal) | Indirect: completes §4.3 | — | n/a | Half a day | n/a | n/a | After rank 2 |
| 6 | Django migration documentation proposal | Low | Real for multi-replica deploys | Duplicate data migrations | Strong (PPCS) | Hours | Low to moderate: the topic was declined twice | Yes | Forum first, only if wanted |
| 7 | SQLAlchemy Draft A (SA-03) | Ready, but the trigger is injected | Low to moderate | Doomed writes committed | Moderate | Hours | Uncertain | Yes | After P5a |
| 8 | Django and SQLAlchemy TX-02 not-sent (Draft B) | Research | Unknown (H7) | Inner writes committed | The mechanism is strong; the trigger is unknown | Open-ended | Low without a trigger | Yes | None |
| 9 | SQLAlchemy Draft C; Django raw-cursor `on_commit` | Low | Real, but downstream of #1453 or documented as unspecified | Hooks run without a commit | Ext, one run each | — | Low as separate reports | Yes (psycopg) | Hold |
| 10 | Re-running PR-01, or new SQLSTATEs in the same path | Low | — | — | Already argued | — | — | — | None |

**Agent 2's candidate gaps.** They are not ranked here and not duplicated, so see its report:

- a `COMMIT` that PostgreSQL rejects with an error, such as a deferred constraint, or `40001` at `COMMIT`;
- asyncio cancellation and timeouts inside a transaction;
- session state that survives the pool (`SET`, roles, advisory locks, temporary tables);
- ORM instance state reused after a rolled-back transaction.

**Housekeeping (internal, no upstream content).** Each item needs approval:

1. Copy `../sqla-tx02-repro/{commit-layer,commit-tag}.md` and `../tortoise-tx-investigation/recorded/results.json` into a versioned location with their scripts. PPCS `FINDINGS.md` text depends on the first.
2. Apply the corrections in §4.4.
3. Decide whether the adjacent SQLAlchemy and Django items belong in `docs/upstream-submissions.md`. Today the tracker does not list P5a or Drafts A–C.

## 8. Recommended next three actions

### 8.1 Prepare (do not post) a follow-up comment on psycopg#1453 for `conn.transaction()`

- **Objective.** Tell psycopg's maintainers that the open issue has a second surface: the context manager, whose public `Transaction.status` reports `committed`.
- **Why it matters.**
  - `conn.transaction()` is psycopg's own transaction API.
  - Its `status` attribute was added (PR #1184, merged 2025-11-22, closing #969: "store on the object whether the block was exited with a commit or a rollback") so callers can tell those two outcomes apart.
  - The audit shows it reporting `committed` for a transaction PostgreSQL rolled back.
  - A fix placed only in `Connection._commit_gen` would miss this path (H2).
- **What evidence already exists.**
  - Appendix A: three repetitions, a savepoint-recovery control, versions, hashes.
  - #1453's own reproduction and output.
  - Src lines: `transaction.py` 133–140 and 272–274; `_connection_base.py` 443–493 and 577–592.
- **What is unknown.**
  - Whether the maintainers read `status` as "the block left through the commit path" or as "committed".
  - Whether they plan a fix in `_exec_command`.
  - H6, a `COMMIT` that raises: not run, so do not claim it.
- **Files.** `research/python-ecosystem-contribution-audit/`; `research/production-reachability/upstream-drafts/psycopg.md`.
- **Plan.**
  1. Re-check #1453, psycopg's default branch, and the PyPI release on the day.
  2. Re-run Appendix A only if psycopg has released a version after 3.3.6.
  3. Draft a comment of about 30–40 visible lines: the observation, the output in a `<details>` block, and one sentence linking #969 and #1184. Prescribe no fix.
  4. Get approval of the exact text.
  5. Record the result in `docs/upstream-submissions.md`, which another session maintains.
- **Success criteria.** The exact text is approved. If posted, the URL and date are recorded in the tracker, and the maintainers can see both surfaces.
- **Abandon if:**
  - #1453 is closed as intended behaviour, in which case record that and do not argue separately;
  - a fix lands that already covers `Transaction`, in which case verify it and record that;
  - a maintainer has already mentioned `transaction()`.

### 8.2 Prepare (do not post) an asyncpg report on `Transaction.commit()`

- **Objective.** Report to asyncpg that its public transaction API returns normally, and records the transaction as `committed`, when PostgreSQL completes `COMMIT` with tag `ROLLBACK`. This is the asyncpg counterpart of psycopg#1453. Tortoise and SQLAlchemy's asyncpg dialect inherit it.
- **Why it matters.** It is the one Python commit-tag finding with no upstream report. One driver change would cover Tortoise (PPCS `c45624`) and SQLAlchemy on asyncpg (V14).
- **What evidence already exists.**
  - PPCS `c45624`: FAIL, with trace `COMMIT; -> ROLLBACK`.
  - Ext `TO-04`.
  - Agent 2's driver-only run (status note, 07:55 PDT; asyncpg 0.32.0; its own container; 3 of 3; savepoint control committed). This audit planned that run, and Agent 2 took it on to avoid duplication. Its program and output are in Agent 2's scratchpad, and Agent 2's report is expected to carry them.
  - Src: asyncpg `transaction.py` 175–219 and `connection.py` 320–388 and 1550–1594; Tortoise `backends/asyncpg/client.py` 189–216 and `backends/base/client.py` 373–406.
- **What is unknown.**
  - Whether an asyncpg issue already exists. Agent 2's search was in progress.
  - Whether asyncpg documents anything about committing a failed block.
  - Whether its maintainers would want `commit()` to raise, or to expose the status.
- **Plan.**
  1. Wait for Agent 2's search and report, and make sure the program and output are preserved in this repository.
  2. Re-check asyncpg's latest release.
  3. Draft a short issue in #1453's shape: the observation, the three repetitions, and the expected behaviour stated without prescribing an implementation. Mention Tortoise and SQLAlchemy only as callers.
  4. Get approval of the exact text, then record it in `docs/upstream-submissions.md`.
- **Success criteria.** An approved draft, no duplicate found, and the evidence preserved in this repository.
- **Abandon if:**
  - an existing issue covers it. Then comment there instead.
  - asyncpg documents `Transaction.commit()` as not checking the outcome. Then consider a documentation note in Tortoise or SQLAlchemy instead.

### 8.3 SQLAlchemy P5a, posted by its author in their own words

- **Objective.** Turn a defect that an adversarial review already confirmed into an upstream report.
- **Why it matters.** It is the most complete Python defect finding that has not been posted:
  - two documented guarantees are contradicted: `Connection.close()` releases transactional state through `rollback()`, and `PoolResetState.transaction_was_reset`;
  - it is reachable through a documented hook, with no DBAPI method replaced;
  - SQLAlchemy 1.3.24 does not have it.
- **What evidence already exists** in `../python-orm-transactions` (private): the review, the revised draft, `check/p5a_close_v2.py` and `.out`, the version comparison harness, and `lifecycle-close-reuse.md`, which is uncommitted.
- **What is unknown.**
  - The behaviour on the current SQLAlchemy release, if newer than 2.1.5.
  - Duplicates since 2026-10-18.
  - The maintainers' view of reachability. The review's own "strongest argument against filing" is that no real driver failure produces it, and #13381 is a precedent.
- **Constraint (Doc, checked 2026-10-24).** SQLAlchemy's `.github/CONTRIBUTING.md` asks that "AI/LLM generated content is not spammed onto SQLAlchemy discussions, issues, or PRs, whether this is cut and pasted, fully automated, or even just lightly edited. Please use your own words". Its `CODE_OF_CONDUCT.md` says "you must communicate with the github interface as a human, in a non-automated fashion." Code written to demonstrate an issue may be LLM-assisted. So the prose must be the author's own, and no agent may post it.
- **Plan.**
  1. Check the current SQLAlchemy release and `main` for changes to `Connection.close()` and `RootTransaction._close_impl`.
  2. Re-run `check/p5a_close_v2.py` only if the release changed.
  3. Repeat the duplicate search.
  4. Choose the venue. The review notes that SQLAlchemy's bug form directs reporters to a Usage Questions discussion.
  5. The author writes and posts the text.
  6. Record the URL in that repository. Optionally add an adjacent-item row to `docs/upstream-submissions.md`.
- **Success criteria.** Posted, with the URL recorded, and any maintainer response logged.
- **Abandon if:** a duplicate exists, current SQLAlchemy no longer reproduces it, or the author decides not to engage.

## 9. Work that should not be repeated

- **PR-01 for psycopg, SQLAlchemy ORM or Core, or Django.** It is complete: `b2c174` and `508b7a`. `docs/research-status.md` says "Do not rerun PR-01."
- **Reproducing psycopg `Connection.commit()` on tag `ROLLBACK`.** Done: `psycopg_commit_tag.py` and `.txt`, plus Ext `commit-tag.md`. Filed as #1453.
- **psycopg `conn.transaction()` on psycopg 3.3.6.** Done by this audit (Appendix A).
- **Any new psycopg, SQLAlchemy or Django report for the commit-tag return.** #1453 is the vehicle. The tracker's P1 says not to file SQLAlchemy or Django.
- **Tracing SQLAlchemy Core's commit path.** Done: Core `FINDINGS.md` "Where the failing calls go", `commit-layer.md`, and §3.1 C2.
- **Django `atomic()` on TX-01A with ORM writes.** Done: `6d8443` and `b2c174`.
- **Django `on_commit` after a caught raw-cursor error.** Done once, outside PPCS (arm 4b). Documented as unspecified.
- **Django TX-02 with a different injected exception class.** Done: arm 2a (`DatabaseError`, rolls back) against 2b (`RuntimeError`, commits), and PPCS `6d8443`. An `execute_wrapper` trigger is already PPCS's mechanism.
- **Django MG-02 held, first-deployment, session-loss and idle-timeout on 6.1.2.** Done: `178fa4`.
- **Searching Django's tracker for migration locking.** Done (§5.2).
- **Alembic `upgrade head` races on an empty database.** Done, stopped by decision (Ext `alembic-upgrade-race/REPORT.md`).
- **The Tortoise TX-01A suite case.** Done: `c45624` and Ext `TO-04`.
- **asyncpg 0.32.0 TX-01A without Tortoise, and SQLAlchemy on asyncpg.** Done by Agent 2 (runtime, 3 of 3, status note 07:55 PDT).
- **SQLAlchemy ORM `after_commit` when `Session.execute()` raised the error.** Done by Agent 2 (runtime, 3 of 3, on psycopg and asyncpg), and once in Ext `run-2.txt`.
- **A `COMMIT` that fails, under SQLAlchemy 2.1.5 on psycopg.** Covered in `../python-orm-transactions/docs/sqlalchemy-transaction-experiments/p5a-review/harness/summary.txt`, per Agent 2's reading:
  - a deferred `23505` and a `40001` at `COMMIT`;
  - cancel and terminate during a slow `COMMIT`;
  - an alarm-raised exception during `COMMIT`;
  - injected `CancelledError`, `KeyboardInterrupt` and `TimeoutError`.

  This audit confirmed only that the file exists and is tracked.
- **SQLAlchemy identity-map concurrency.** `../python-orm-transactions/docs/sqlalchemy-identity-map/REPORT.md`. Every cell matched its contract, per Agent 2.
- **Category B and E connection-loss cases for the Python adapters.** Done: `6d8443`, `3673a3`, `64c5c5`, `c45624`, `87af6a`.
- **`TX-01B.commit-reply-discarded` for psycopg and asyncpg.** NOT APPLICABLE by design. Both drivers consume the reply inside `commit()`. Category E replaces it (adapter READMEs).
- **The SQLAlchemy P5a reproduction and adversarial review.** Done: Ext `cca9b98`.
- **Reproducing the first-deployment collision.** Explained, and a redesign is in progress on branch `first-deployment-c1`.

## 10. Recommended upstream contribution strategy

| Project | Recommended | Type | Not recommended |
| --- | --- | --- | --- |
| psycopg | One follow-up comment on #1453 covering `conn.transaction()` and `Transaction.status` (§8.1). A regression-test or patch offer only if maintainers ask, phrased conditionally | Comment on an existing bug report | A new issue; prescribing where the fix goes |
| asyncpg | A #1453-shaped issue after the duplicate search (§8.2). Agent 2's driver-only run establishes the behaviour | Bug report, or a question if the docs disclaim it | Separate Tortoise or SQLAlchemy reports for the same discard |
| Tortoise ORM | None while an asyncpg report is pending. Reconsider only if asyncpg declines; then possibly a documentation note about catching database errors inside `in_transaction()` | Docs, or a bug report | A report for the asyncpg discard |
| SQLAlchemy | P5a, written and posted by its author in their own words (§8.3). Then possibly Draft A. Drafts B and C held | Usage Questions discussion (the bug form's routing), then possibly an issue | Any agent-posted text (SQLAlchemy's rules); a Core commit-tag report (#1453 covers it) |
| Django | No bug reports. Optionally a forum post proposing a short docs note that `migrate` does not coordinate concurrent invocations, citing PPCS's measurement | Documentation proposal | Reopening #30490 or #34610; a TX-02 report; an `on_commit` report for the documented-unspecified raw-SQL path |
| Alembic | None | — | New race work, against the recorded decision |

Every row is outward-facing and needs explicit approval of its exact text and destination first (`AGENTS.md` rule 9). Before any post, re-check the issue state, duplicates and releases on the day.

## Appendix A. psycopg `conn.transaction()` reproduction

Program `research/python-ecosystem-contribution-audit/psycopg_transaction_block.py` (SHA-256 `951bcb49…`). Run 2026-10-24T14:10:49Z against a throwaway `postgres:18.6` container from PPCS's pinned digest, with `adapters/sqlalchemy-core/.venv/bin/python -I`. Provenance is in that directory's [`README.md`](python-ecosystem-contribution-audit/README.md).

```python
"""psycopg Connection.transaction() after a caught 23505. Diagnostic, not a PPCS case.

    DATABASE_URL=postgresql://postgres:...@127.0.0.1:55479/postgres python psycopg_transaction_block.py

Creates database audit_psycopg_tx, drops it at the end. Prints what the transaction
block reported (exception, Transaction.status, driver status) and what PostgreSQL did
(pg_xact_status of the xid captured inside the block, marker visibility, and the
backend's state and last statement), read from a separate connection.
"""

import os
import sys

import psycopg
from psycopg import errors
from psycopg.pq import TransactionStatus

URL = os.environ["DATABASE_URL"]
NAME = "audit_psycopg_tx"
REPS = 3


def connect(dbname, autocommit=True):
    return psycopg.connect(URL, dbname=dbname, autocommit=autocommit)


def tstatus(conn):
    return TransactionStatus(conn.info.transaction_status).name


def observe(xid, pid, marker):
    with connect(NAME) as probe:
        fate = probe.execute("select pg_xact_status(%s::xid8)", (xid,)).fetchone()[0]
        seen = probe.execute("select count(*) from item where name = %s", (marker,)).fetchone()[0]
        row = probe.execute(
            "select state, query from pg_stat_activity where pid = %s", (pid,)
        ).fetchone()
    return fate, seen, row


def subject(marker, recover_with_savepoint):
    conn = connect(NAME)
    pid = conn.info.backend_pid
    raised = None
    caught = None
    status_before_exit = None
    try:
        with conn.transaction() as tx:
            conn.execute("insert into item (name) values (%s)", (marker,))
            xid = conn.execute("select pg_current_xact_id()::text").fetchone()[0]
            if recover_with_savepoint:
                try:
                    with conn.transaction():
                        conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            else:
                try:
                    conn.execute("insert into uniq (code) values ('taken')")
                except errors.UniqueViolation as exc:
                    caught = exc.sqlstate
            status_before_exit = tstatus(conn)
    except Exception as exc:  # what the block raised on exit, if anything
        raised = f"{type(exc).__name__}: {exc}"
    status_after_exit = tstatus(conn)
    fate, seen, row = observe(xid, pid, marker)
    conn.close()
    return {
        "caught": caught,
        "driver status before block exit": status_before_exit,
        "block raised on exit": raised,
        "Transaction.status": tx.status.value,
        "driver status after block exit": status_after_exit,
        "pg_xact_status": fate,
        "marker visible": bool(seen),
        "backend state, last statement": row,
    }


def main():
    admin = connect("postgres")
    print(f"python {sys.version.split()[0]}")
    print(f"psycopg {psycopg.__version__}, impl {psycopg.pq.__impl__}, libpq {psycopg.pq.version()}")
    print(f"server_version {admin.execute('show server_version').fetchone()[0]}")
    admin.execute(f"drop database if exists {NAME} with (force)")
    admin.execute(f"create database {NAME}")
    admin.close()
    with connect(NAME) as setup:
        setup.execute("create table item (id serial primary key, name text not null)")
        setup.execute("create table uniq (id serial primary key, code text not null unique)")
        setup.execute("insert into uniq (code) values ('taken')")

    # Control: a normal transaction block.
    conn = connect(NAME)
    with conn.transaction() as tx:
        conn.execute("insert into item (name) values ('control')")
    print("control: normal block")
    print(f"  Transaction.status {tx.status.value}")
    conn.close()
    with connect(NAME) as probe:
        n = probe.execute("select count(*) from item where name = 'control'").fetchone()[0]
    print(f"  marker visible {bool(n)}")

    for rep in range(1, REPS + 1):
        print(f"repetition {rep}: caught 23505 inside conn.transaction(), block exits normally")
        for key, value in subject(f"caught-{rep}", recover_with_savepoint=False).items():
            print(f"  {key}: {value}")
        print(f"repetition {rep}: savepoint recovery, inner conn.transaction() catches 23505")
        for key, value in subject(f"recovered-{rep}", recover_with_savepoint=True).items():
            print(f"  {key}: {value}")

    admin = connect("postgres")
    admin.execute(f"drop database {NAME} with (force)")
    admin.close()


if __name__ == "__main__":
    main()
```

Output, complete (`psycopg_transaction_block.txt`, SHA-256 `079ce18a…`):

```
python 3.13.11
psycopg 3.3.6, impl binary, libpq 180006
server_version 18.6 (Debian 18.6-1.pgdg13+2)
control: normal block
  Transaction.status committed
  marker visible True
repetition 1: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 1: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
repetition 2: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 2: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
repetition 3: caught 23505 inside conn.transaction(), block exits normally
  caught: 23505
  driver status before block exit: INERROR
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: aborted
  marker visible: False
  backend state, last statement: ('idle', 'COMMIT')
repetition 3: savepoint recovery, inner conn.transaction() catches 23505
  caught: 23505
  driver status before block exit: INTRANS
  block raised on exit: None
  Transaction.status: committed
  driver status after block exit: IDLE
  pg_xact_status: committed
  marker visible: True
  backend state, last statement: ('idle', 'COMMIT')
```

## Appendix B. External sources checked on 2026-10-24

Read-only. Nothing was posted.

| Source | What was checked |
| --- | --- |
| [psycopg#1453](https://github.com/psycopg/psycopg/issues/1453), with `gh` | Open, no comments, no labels. The posted body covers `Connection.commit()`, with the cursor `COMMIT` as tag evidence |
| psycopg commits since 2026-10-20, with `gh api` | None returned |
| psycopg [#969](https://github.com/psycopg/psycopg/issues/969) and [PR #1184](https://github.com/psycopg/psycopg/pull/1184) | The request to store commit or rollback on the transaction object. Merged 2025-11-22 |
| psycopg [PR #1454](https://github.com/psycopg/psycopg/pull/1454) | Open. The cancellation fix for #1451. Not #1453 |
| Django tickets [#30490](https://code.djangoproject.com/ticket/30490), [#34610](https://code.djangoproject.com/ticket/34610), [#29721](https://code.djangoproject.com/ticket/29721), [#37406](https://code.djangoproject.com/ticket/37406), and the [forum thread](https://forum.djangoproject.com/t/add-unique-key-for-django-migration-tracking-model/21283) | §5.2 |
| Django 6.1 docs: [transactions](https://docs.djangoproject.com/en/6.1/topics/db/transactions/), [migrations](https://docs.djangoproject.com/en/6.1/topics/migrations/), [`migrate`](https://docs.djangoproject.com/en/6.1/ref/django-admin/) | Quoted in §3.2, §4.1 and §4.1.1 |
| SQLAlchemy `.github/CONTRIBUTING.md` (lines 54–56) and `.github/CODE_OF_CONDUCT.md` (lines 12–23), `main` | The policy on AI-written posts (§8.3) |
