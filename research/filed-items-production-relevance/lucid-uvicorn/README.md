# Production relevance of the filed Lucid and Uvicorn items

Assessed 2026-10-26. Written by: Claude Opus 5.5 (max).

This page rates four findings that have already been filed upstream: three in Lucid, AdonisJS's ORM, and one in Uvicorn. It applies PPCS `docs/production-relevance.md`: its six fields, its kinds of evidence and its searching rules. The IDs L1, L3 and L5 are those of nest-adonis-spike `docs/upstream-submissions.md`.

It is a desk assessment. The searches and reads were read-only. Nothing was run, posted or sent, and no one was contacted. Code found by the searches was read at a commit and not run. Reports that quote production data were not checked beyond the report.

## Summary

The tiers weigh likelihood, the strength and source of the evidence, and whether the failure is silent. They are a judgment, dated 2026-10-26, and they rank neither severity nor the contract.

- **Higher:** none.
- **Middle:** U1. Every deploy can trigger it, large projects set the option in production, and one project's own audit reports a record lost to this race; harm needs specific cleanup, and Uvicorn logs the cancellation.
- **Lower:**
  - L1. Silent and certain once the shape exists, but the shape is rare: one application in the sample requests a stricter level through the manual form.
  - L5. Silent at rollback time, but the filed shape (no `down()` at all) is in none of the 29 migrations inspected, and the silent outcome is mostly a development event.
  - L3. No released version has it; if PR #1168 merges as is, concurrent runners are common, but the lock's session must also end on its own during a migration.
- **No production trigger:** none.
- **Not defects, or folded into other items:** none.

| ID | Filed as | Trigger, and how our runs produced it | Strongest real-world evidence | Real code run | Consequence | Likelihood (judgment) |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Kludex/uvicorn discussion #3232 | A deploy's SIGTERM, or SIGINT, while a request outlives `--timeout-graceful-shutdown`; real signals to a real Uvicorn, with a constructed long request | Audit: CandleViewer#2827 reports a WebSocket close-audit row lost to this race. Exposed code: Polar, Omi, deer-flow, bifrost and spoo set the option and close clients in their lifespan. FastMCP sets it by default (2 s). LiteLLM does too (30 s), and guards | No | Cleanup of the cancelled requests overlaps the lifespan shutdown and is cut off at exit | Moderate |
| L1 | adonisjs/lucid#1202 and PR #1203 | A concurrent write to rows the manual transaction read; a real concurrent update through ordinary APIs, and PPCS TX-05 with no fault | Exposed code: NIAEFEUP/enei opens a manual SERIALIZABLE transaction in an admin action. A user report from tests: #1006 (2024) | No | Runs at the session default; lost updates commit, with no error | Low |
| L5 | adonisjs/lucid#1204 | A rollback that reaches a migration with no `down()`; the ordinary `node ace` commands in a scaffolded app, and Lucid's command classes on PostgreSQL | None in Lucid. Other ecosystem: a Laravel contributor describes the same behaviour (laravel/framework#57429) | A scaffolded app, with a constructed migration | Reported `reverted`, history row deleted, change kept; the next run applies it again | Low |
| L3 | Comment on adonisjs/lucid PR #1168 | The idle lock session ends during a migration; `idle_session_timeout` set to 1 s, and a targeted `pg_terminate_backend()` | None for the regression, which is unreleased. The precondition is documented: AdonisJS's deployment guide migrates at each container start | No | A second runner applies the same migration; for data migrations, applied twice | Low, and none in released versions |

## The findings

One compact block per finding, in the form of PY-2's block in the Python tracker: a trigger's four parts share one line. The details and the inspected samples follow in the next section.

### L1: a manual Lucid transaction ignores its isolation level

- **Filed as:** [adonisjs/lucid#1202](https://github.com/adonisjs/lucid/issues/1202) (issue) and [#1203](https://github.com/adonisjs/lucid/pull/1203) (PR, submitted head `c8188dab8c`), 2026-10-17. Both open; no maintainer reply by 2026-10-26. Checked 2026-10-27 through the API: `thetutlage` merged #1203 at 2026-10-27T06:41:46Z (merge `e4c56d5d`), and #1202 closed `completed`. The merged head is `70fc7ce3`, after two maintainer commits this assessment did not run.
- **Fix status:** on 2026-10-26, not fixed. The option shipped in v14.2.0 (2021-06-02, release notes), and our record dates the faulty line to that commit (`b808f03b`). It is in 22.4.2, the latest release as of 2026-10-27, and it was in `22.x` at `f715bb4ecc` (`src/query_client/index.ts`, lines 231–241). The first report, #1006, was closed by the stale bot. On 2026-10-27 the fix is on `22.x` at `e4c56d5`. npm `latest` is still 22.4.2, published 2026-04-05, so a released Lucid still drops the manual level. The merge was read, not run: it forwards `isolationLevel` and `readOnly`, and a savepoint receives no options.
- **Production relevance (2026-10-26)** ([details](#l1-details)):
  - **Consequence:** `db.transaction({ isolationLevel })`, `db.connection(name).transaction(...)` and `Model.transaction(...)` send a plain `BEGIN`, so the transaction runs at the session default (READ COMMITTED on PostgreSQL, REPEATABLE READ on MySQL). Anomalies the requested level excludes, such as a lost update in a read-modify-write, commit without an error, and a retry loop written for `40001` never fires. Silent.
  - **Trigger, a concurrent write to rows the transaction read:** in production, yes (ordinary concurrency); in our runs, a real concurrent update from a second connection, interleaved by the script, through ordinary APIs (nest-adonis-spike `docs/lucid-isolation-level-fix.md` §2.3–2.4), and PPCS TX-05 with no fault (`reports/examples/2026-10-24T14-19-00Z-4f477e`: explicit FAIL, managed PASS). Code shape: the manual form with a level stricter than the default, which the transactions guide documents; reasonable. Evidence: exposed code, NIAEFEUP/enei's admin "recalculate points" action (3 stars); a user report from tests, #1006 (2024).
  - **Reproduced on real code:** no. The #1006 scenario was re-created; enei's action was not run.
  - **Searches:** 12 application files in 7 repositories pass a level to Lucid. 6 use the manual form: 1 requests SERIALIZABLE directly, 2 are helpers that forward the caller's level, and 3 request a level no stricter than PostgreSQL's default. The other 6 use the managed form. No Lucid code retrying on `40001` was found.
  - **Likelihood (judgment):** low. Few Lucid files set a level at all (18 files with the v6 `db` import, against 644 matching the manual form and 1,332 the managed form), and fewer use the manual form; where the shape exists, the fallback is certain, and the anomaly needs concurrent writes to the same rows.
  - **Not established:** a production report; whether enei's action ran concurrently with point changes; the MySQL side in real applications.

### L3: with PR #1168, a second runner can apply a migration after the lock's session ends

- **Filed as:** a [comment](https://github.com/adonisjs/lucid/pull/1168) on adonisjs/lucid PR #1168, the maintainer's open fix for #1153, 2026-10-17. No reply by 2026-10-26.
- **Fix status:** the regression is only in the unmerged PR, whose head is still `28e650290e`, the head we tested. No released Lucid has it, so it matters only if the PR merges as is. Released 22.4.2 applied each migration once in the same default-pool scenarios.
- **Production relevance (2026-10-26)** ([details](#l3-details)):
  - **Consequence:** with `pool.max > 1`, the PR holds the advisory lock on a pinned connection that stays idle while migrations run on other connections (`src/migration/runner.ts` @ `28e650290e`, lines 294–321). If that session ends, the lock is released and a second runner applies the same migration: a data migration is applied twice, with two history rows. Runner A's `run()` rejects at the unlock, after committing; runner B exits 0; nothing reports the duplicate.
  - **Trigger, `idle_session_timeout` ends the idle lock session:** in production, possible: off by default, discouraged by PostgreSQL's documentation for pooled connections, yet enabled in 5 of 8 inspected PostgreSQL repositories (60 s to 60 min where shown); in our runs, a real server timeout set to 1 s on runner A's sessions. Code shape: concurrent runners, which AdonisJS documents, and a migration longer than the timeout; reasonable. Evidence: none of the regression (unreleased); for concurrent runners, the AdonisJS 7 deployment guide and the maintainer's own Railway sample.
  - **Trigger, an operator or tool terminates idle sessions:** in production, yes in practice (runbooks, a background worker, a serverless library); in our runs, a targeted `pg_terminate_backend()` of the lock session. Code shape: as above. Evidence: as above.
  - **Trigger, a proxy or network idle timeout:** in production, unknown; not run. Code shape: as above. Evidence: none. Judgment: a silent network drop usually leaves the server session, and the lock, alive until TCP keepalive notices, which strands the lock loudly rather than releasing it mid-run.
  - **Reproduced on real code:** no. The real library ran in constructed runner processes.
  - **Searches:** 8 of 10 inspected Dockerfiles and 8 of 10 shell entrypoints migrate at every start; 10 of 10 Procfiles and 4 of 4 `fly.toml` files use a single release step. No report of a double-applied Lucid migration was found. Other ecosystem: MikroORM's maintainer proposes the same design ([mikro-orm#8505](https://github.com/mikro-orm/mikro-orm/pull/8505), open).
  - **Likelihood (judgment):** low, and none for released versions. Concurrent runners are common, but the lock's session must end on its own, during a migration, while another runner starts.
  - **Not established:** any occurrence; how often a lock session ends alone during a migration; MySQL and PgBouncer; whether the PR merges as is.

### L5: rollback reports success for a migration with no `down()`

- **Filed as:** [adonisjs/lucid#1204](https://github.com/adonisjs/lucid/issues/1204), 2026-10-17, as a proposal for a warning. Open; no reply by 2026-10-26.
- **Fix status:** not fixed. `BaseSchema`'s empty `down()` is unchanged on `22.x` (`src/schema/main.ts` @ `f715bb4ecc`, line 188). Our record dates it to 2019, so earlier majors behave the same by source reading; 22.4.2 was run.
- **Production relevance (2026-10-26)** ([details](#l5-details)):
  - **Consequence:** `migration:rollback` prints `reverted`, exits 0 and deletes the history row while the change stays: silent. The next `migration:run` applies `up()` again: a data change that does not conflict is applied twice without an error; a schema change usually fails loudly ("already exists").
  - **Trigger, a rollback of the latest batch in development:** in production, not applicable; in development, routine; in our runs, the ordinary `node ace` commands in a freshly scaffolded API kit (SQLite) and Lucid's command classes on PostgreSQL 18.6. Code shape: a migration with no `down()`, which the guide forbids ("must implement") and both generator stubs avoid, so the method must be deleted by hand; up-only migrations are a known practice elsewhere. Evidence: none in Lucid; other ecosystem, a Laravel contributor describes the same behaviour (laravel/framework#57429).
  - **Trigger, the documented test hook:** in development and CI, routine: `testUtils.db().migrate()` runs `migration:reset` when the test runner exits, and 9 of 10 inspected `tests/bootstrap.ts` files register it; not run. Code shape: as above. Evidence: none. Judgment: in a full reset an earlier `down()` usually drops the touched table (masked), or the next run fails loudly; the silent duplicate needs a change that survives the reset.
  - **Trigger, a production rollback:** in production, rare by design (it needs `--force` or a confirmation, and the guide says production changes "should always move forward"; `disableRollbacksInProduction` is not in the default config); not run. Code shape: as above. Evidence: workflows that roll back outside development exist: a staging deploy that rolls back and re-runs on every push (nationskollen/server, 2 stars) and a production operations workflow with a rollback option (BrightkyEfoo/rexel-modern-backend, 0 stars).
  - **Reproduced on real code:** a scaffolded `create-adonisjs` application through the real CLI, with a constructed migration.
  - **Searches:** 0 of 29 inspected migrations lack `down()` entirely; 4 of the 19 data migrations have a `down()` that does nothing (3 empty on purpose, 1 an unfilled `--alter` stub), which behaves the same but is outside the filed shape.
  - **Likelihood (judgment):** low. The filed shape was not in the sample, and the silent outcome needs a partial rollback of a data migration, mostly a development event.
  - **Not established:** a Lucid report; how many applications have a migration with no `down()`; how often production databases are rolled back.

### U1: Uvicorn sends lifespan shutdown while the requests it cancelled still run

- **Filed as:** discussion [Kludex/uvicorn#3232](https://github.com/Kludex/uvicorn/discussions/3232), 2026-10-25. No reply by 2026-10-26.
- **Fix status:** not fixed. `uvicorn/server.py` at `main` `9d81c12a2c` (2026-10-25) still cancels the tasks and then awaits `lifespan.shutdown()` (lines 295–308). The option exists since 0.22.0 (release notes); our runs covered 0.54.0 and `main` at `e4981ad`.
- **Production relevance (2026-10-26)** ([details](#u1-details)):
  - **Consequence:** after `--timeout-graceful-shutdown` expires, the cancelled requests' `except CancelledError` and `finally` blocks run concurrently with the lifespan shutdown; on SIGTERM the process ends before they finish, and on SIGINT they are cancelled again. Cleanup that uses a resource the lifespan closes fails; cleanup that outlasts it is cut off. Uvicorn logs the cancellation as an error; the interrupted cleanup is not reported.
  - **Trigger, a deploy or restart while a request outlives the timeout:** in production, yes: rolling deploys send SIGTERM, and streaming endpoints (SSE, LLM answers) routinely outlive short timeouts; in our runs, a real SIGTERM or SIGINT to a real Uvicorn process, with a constructed 60 s request and a 0.5 s cleanup (PPCS `research/python-lifecycle-correctness/findings.md`, F1). Code shape: the option set, a lifespan that closes clients or pools, and request cleanup in `finally`; ordinary code. Evidence: audit, [CandleViewer/CandleViewer#2827](https://github.com/CandleViewer/CandleViewer/issues/2827) (2026-10-16, a collaborator, 8 stars, before our post): a cancelled WebSocket handler's close-audit row is lost when the lifespan stops the audit writer first ("logged, never silent"). Exposed code: Polar, Omi, bytedance/deer-flow, gobifrost/bifrost and spoo-me/spoo set the option in production and close clients, pools or backends in their lifespan. Defaults: FastMCP sets 2 s with the lifespan on; LiteLLM sets 30 s and guards with an in-flight drain.
  - **Reproduced on real code:** no.
  - **Searches:** of 9 inspected deployment hits, 6 have the shape, 1 guards it (LiteLLM), and 2 run without a lifespan handler (Saleor's Django application; suitenumerique/docs with `--lifespan=off`), where only the cut-off at exit applies.
  - **Likelihood (judgment):** moderate. Widely used projects set the option in production and two frameworks by default, and long requests during a deploy are routine for streaming applications; harm needs cleanup that a closed resource breaks or that must finish, and a database transaction cut off this way is rolled back by the server.
  - **Not established:** a production incident; whether the inspected projects' request cleanup uses what their lifespan closes; the Gunicorn path, where `uvicorn-worker` sets no timeout today and its open PR #46 would set it from Gunicorn's `graceful_timeout`.

## Details

### <a id="l1-details"></a>L1

**The project's size.** adonisjs/lucid has 1,229 stars, and `@adonisjs/lucid` had 628,470 npm downloads in the month to 2026-10-22.

**The contract.** The Lucid guide recommends managed transactions "for most use cases" (lucid.adonisjs.com `content/docs/guides/transactions.md` @ `798060f49a`, line 19). It then documents the manual form with a level: "The same isolation option is available when creating the transaction manually", followed by `db.transaction({ isolationLevel: 'serializable' })` (lines 96–99). It puts the retry duty for serialization failures on the application (lines 152 and 164).

**Inspected sample.** These are the application files among the hits of `l1-c1` to `l1-c4` and `l1-c7`, all 12 of them:

| File | Form and level | Shape |
| --- | --- | --- |
| NIAEFEUP/enei `apps/website/app/admin/resources/user.ts` @ `038db7eef1`, lines 35–148 | Manual, SERIALIZABLE; five statements recompute a user's points, then `trx.commit()` | **Failing** |
| NIAEFEUP/enei `apps/website/app/services/cart_service.ts` @ `038db7eef1`, lines 8–29 | Managed, SERIALIZABLE | Correct |
| ssortia/adonisjs-transaction `src/transactional.ts` @ `ab34d0b58e`, lines 104–108 | Manual; a `@transaction({ isolationLevel })` decorator forwards the caller's level. It retries on any error (lines 142–155) | **Failing** (a library: 0 stars; npm `adonisjs-transaction-decorator`, 37 downloads in the month to 2026-10-22) |
| denishsharma/adonis-effect-api-starter `app/core/db/internals/db_transaction.ts` @ `63ee5a06cc`, lines 25–30 | Manual; forwards its options | **Failing** if a caller passes a level; callers not checked (0 stars) |
| Wuningson/patronize-application `app/Controllers/Http/TransfersController.ts` @ `5e8ee6ecdb`, line 29; `DepositsController.ts`, line 65 | Manual, READ COMMITTED | No effect on PostgreSQL |
| djmianto/lbi-backend `app/Controllers/Http/SuperAdmin/TransactionsController.ts` @ `b37ece95c9`, line 95 | Manual, READ UNCOMMITTED | No stricter level requested |
| sierraleonez/kamalan-api `OrdersController.ts`, line 147; `RegistryCreationsController.ts`, line 156; `database/seeders/Region.ts`, line 64 @ `7ac71d46b8` | Managed, READ UNCOMMITTED | Correct |
| undernightcore/mockos `app/Controllers/Http/SwaggerController.ts`, line 85; `RoutesController.ts`, line 129 @ `aa58f896c8` | Managed, REPEATABLE READ (25 stars) | Correct |

- The enei hit came from a benchmark mirror, `review-bench/NIAEFEUP_enei`. Commit `038db7eef1` exists in NIAEFEUP/enei itself (2025-04-27).
- The other hits are Lucid's own source and guide, PPCS's adapter and reports, a Portuguese translation of the AdonisJS 5 docs, and AI-agent reference files. One of those copies the guide's manual example: lncitador/adonisjs-maestro `skills/lucid/references/transactions.md` @ `67da0bd147`, line 66.
- **Form counts,** files with Lucid's v6 `db` import:
  - `isolationLevel`, 18 (`l1-c1`): of the 10 hits listed, 3 are application files (in the table) and 7 are documentation or agent references. With the AdonisJS 5 import, 11 (`l1-c2`): of 10 listed, 7 are application files (in the table) and 3 are documentation or an upgrade tool;
  - the manual form, `await db.transaction()`, 644 (`l1-c8`): 8 of 10 inspected hits call `db.transaction()` without options in application or library code; 2 are documentation;
  - the managed form, `db.transaction(async`, 1,332 (`l1-c9`): 8 of 8 inspected hits use the callback form, 7 of them in one repository (kanwas-ai/kanwas).
- **Retry loops.** `l1-c5` found 3 code hits for `40001` in Lucid projects; the 2 inspected are data values, Brazilian company numbers in a seeder and a test, and the third is a test in the same repository. `l1-c6` found none. In these 2 queries on 2026-10-26 I found no Lucid code that retries on `40001`.

**Reports.** In 10 issue queries on 2026-10-26 (`l1-i1` to `l1-i10`), the only reports of the behaviour were:

- [#1006](https://github.com/adonisjs/lucid/issues/1006), opened 2024-02-10 by mkevison (NONE): "I'm running some tests with isolation in Postgres". This is a user's test, not a deployment. Its reproduction repository, mkevison/repeatable-read, returned 404 on 2026-10-26. The stale bot closed the issue on 2025-05-06 with no maintainer reply;
- our own #1202 and #1203. #1203 merged on 2026-10-27; that does not add a production report.

#679 (2021) is the feature request that led to v14.2.0.

**Other ecosystem.** [mysql-net/MySqlConnector#1299](https://github.com/mysql-net/MySqlConnector/issues/1299) (2023-03-24, a user, NONE; the project has 1,505 stars) reports that with XA transactions a `TransactionScope`'s isolation level is ignored, and the transaction runs at the default, "which results in (in our case unwanted) different locking behaviour". It is open. It states no data consequence.

**Evidence against.** The guide steers users to the managed form, and 6 of the 12 inspected files use it. 3 of the 6 manual hits request a level that is not stricter than PostgreSQL's default.

### <a id="l3-details"></a>L3

**The documented precondition:**

- **The Lucid guide** gives the lock's purpose as preventing "concurrent migration runs from racing against each other (for example, two CI deployments rolling out at the same time)" (lucid.adonisjs.com `content/docs/migrations/introduction.md` @ `798060f49a`, line 309).
- **The AdonisJS 7 deployment guide** (adonisjs/v7-docs `content/start/deployment.md` @ `52e3bed7f8`):
  - line 218: "If multiple processes attempt to run migrations simultaneously (for example, during a rolling deployment), only one process will execute the migrations while others wait";
  - lines 280–334: a `docker-entrypoint.js` that runs `node ace migration:run --force` before starting the server; "For horizontal scaling where multiple containers start simultaneously, the migration locking ensures only one container runs migrations while others wait";
  - line 220 prefers a platform's release hook where one exists;
  - the "others wait" claim does not match our record: a losing runner fails at once with `E_UNABLE_ACQUIRE_LOCK`, in 7–21 ms (nest-adonis-spike `docs/ppcs-migration-research/docs/lucid-findings.md`, §4).
- **The AdonisJS 6 guide** (adonisjs/v6-docs `content/docs/getting_started/deployment.md` @ `0c513b5468`, lines 152–156) says to run migrations before restarting the server, through a managed service, CI/CD or SSH.
- **The maintainer's Railway sample** (thetutlage/railway-sample-deploy `DEPLOY.md` @ `4f7de5836e`, lines 101–102 and 174–178; 0 stars) runs `migration:run` as `preDeployCommand` on both the web and the worker service: "That is safe (idempotent - locked)".

**Inspected deployment hits:**

- **Dockerfiles** (`l3-c1`, 105 files). 8 of 10 migrate at every container start: Dolu89/bitcoin-bips @ `67628bff17` (line 53), undernightcore/mockos @ `aa58f896c8` (line 33), open-cogsci/omm-server @ `240c970e81`, Christopher2K/weakassdev @ `2279c80040` (line 59), SPLRGE/traefik @ `747773a081` (line 32), BeemoBot-Enterprise/beemobot-api @ `576594e892`, FaisalHussain95/MiniPlayPartyApi @ `7287f9772e` (line 34) and NeuTroNBZh/CS2-RetakeV4-Panel @ `0571bdb405` (line 22). The other 2: one migrates at image build (alexsandro49/api_restful_adonis), one in a development command (capstoneconnector/Henry-Gets-Moving-Backend).
- **Shell scripts** (`l3-c2`, 109 files). 8 of 10 migrate at container or process start: Crosstalk-Solutions/project-nomad `install/entrypoint.sh` @ `54ee30a449` (40,971 stars), ad-on-is/rachoon (two files) @ `c532aa2fc9`, paxo-phone/paxo-site @ `3dab5d6788`, ferdium/ferdium-server `docker/entrypoint.sh` @ `ce548bb741` (301 stars), bigwill/project-nomad (a copy of project-nomad's script), SavvyMeat/aw-downloader @ `6a3266ae2d` and javascriptcm/javascript.cm @ `ae78cf1199`. The other 2 are a test script and a standalone migrate script. Most of these are self-hosted applications that usually run one instance. Whether they run several replicas was not established.
- **Single runners:**
  - Procfiles (`l3-c3`, 188 files): 10 of 10 inspected use Heroku's `release:` phase;
  - `fly.toml` (`l3-c7`): 4 of 4 use `release_command`;
  - `preDeployCommand` (`l3-c8`) is Railway's and Render's pre-deploy step; most of its hits are deployment notes. One hit (mnfst/llm-gateway `railway.toml`) notes that "Railway runs preDeploy in a single one-off container per deployment, so replicas never migrate concurrently". The maintainer's sample above shows that two services sharing one config each run it.

**How the lock's session ends on its own:**

- **PostgreSQL's documentation** (postgres/postgres `doc/src/sgml/config.sgml` @ `REL_18_0`, lines 10230–10260) says `idle_session_timeout` is off by default. It ends sessions idle outside a transaction, which is exactly the PR's pinned lock connection, and adds: "Be wary of enforcing this timeout on connections made through connection-pooling software or other middleware".
- **Configurations** (`l3-c9`, 99 HCL files, mostly other `idle_session_timeout*` parameters; `l3-c10`, 177 YAML files). I inspected 12 hits, which cover 8 PostgreSQL repositories:
  - 5 enable it: zama-ai/fhevm, 60 s, to free a lock when its holder dies (a CI preview configuration); kyky2347/ALTA, 30 min server-wide; dsx-ai-factory/infra-controller, 60 min; fighthealthinsurance, "already set on the cluster"; bagofwords1/bagofwords, a startup parameter on PostgreSQL 14 and later;
  - 1 disables it explicitly: filipedeschamps/tabnews.com.br, `0`;
  - 2 only document it: OneUptime, xataio/xata.
  - The other hits are a different database (serenedb) and an unrelated Atlas setting.
- **Idle-session killers** (`l3-c11`, 2,984 files combine `pg_terminate_backend` and `state = 'idle'`). Of 10 inspected:
  - 6 are runbooks, blog posts or agent skills that kill idle connections by hand, some after 5 or 10 minutes idle;
  - 2 are database tools: pgcenter and Archery;
  - 2 kill idle connections automatically: michaelpq/pg_plugins `kill_idle` (a background worker) and MatteoGioioso/serverless-pg;
  - fighthealthinsurance also runs a reaper CronJob that terminates connections under connection pressure.
- **PgBouncer.** MikroORM's PR #8505 notes that "session locks don't work behind PgBouncer in transaction mode". That would affect the released Lucid and the PR alike. Lucid behind PgBouncer was not tested.

**#1153 and its reporter.** [#1153](https://github.com/adonisjs/lucid/issues/1153) was opened on 2026-03-08 by simoneNEMO (NONE; account created in 2022; 7 issues and pull requests across AdonisJS repositories: lucid, otel, http-transformers, v6-docs and cache).

- It reports the lock taken and released on different pool connections: "In our production Kubernetes deployment (2 API replicas + 1 admin replica, pool `max: 20`), it reproduces reliably during rolling deployments."
- On #1168 (2026-04-25), the same user reviewed the PR ("looks good to me (minus the unrelated commit ofc)") and wrote: "we got issues related to this only 3 times in 2 years and we do daily deployments".
- The two statements differ on frequency. Neither could be checked.
- thetutlage (MEMBER; with 1,423 contributions, Lucid's largest contributor by far) wrote the PR. On #1153 he wrote that it "does require some manual testing and a second pair to eyes" (2026-04-07). He labelled #1153 "Priority: Critical" after the stale bot closed it, and reopened it (2026-05-07). He reopened #1168 after the bot closed it (2026-05-28), and assigned and labelled it (2026-07-18).
- The other commenters on #1168 are bots: the stale bot three times, and CodeRabbit's automated reviews. Nobody has replied to our comment.

**Earlier reports of the lock-release problem** that the PR fixes, found by `l3-i1` to `l3-i3`:

- [#1040](https://github.com/adonisjs/lucid/issues/1040) (2024-06-22, a user): "Migration completed, but unable to release database lock" on every test run, with three Discord threads. A maintainer asked for a reproduction, and the stale bot closed the issue.
- #932 (2023) added `--disable-locks`.
- #914 (2023) is a PlanetScale-specific variant.

In these queries no report describes a migration applied twice under Lucid.

**Other ecosystems:**

- [mikro-orm#8456](https://github.com/mikro-orm/mikro-orm/issues/8456) (2026-10-14, a user, NONE) reports that MikroORM takes no lock, so data migrations apply twice: "This is common when several deploy replicas run migrations on start". The maintainer's PR #8505 adds an opt-in lock: "The lock is a session lock taken on a pooled connection reserved for the whole run … Only the lock queries use that connection, the migrations keep going through the pool". That is the design of Lucid's PR #1168, so the same exposure would follow by source reading.
- [govpf/mes-demarches#582](https://github.com/govpf/mes-demarches/issues/582) (2026-10-06, a collaborator; generated by an automated triage tool) quotes a production Sentry event: Rails' `ConcurrentMigrationError: Failed to release advisory lock` at deploy, 3 occurrences since 2026-07-21. It points to PgBouncer in transaction mode. This is #1153's class, not the lock loss filed here. The Sentry data was not checked.

**Our evidence.** nest-adonis-spike `docs/ppcs-migration-research/docs/lucid-findings.md` §4 (MG-02.terminate-lock and MG-02.idle-session-timeout on the PR head: effects 2, two history rows). An independent validation, recorded in `docs/ppcs-migration-research/docs/validation-report-openai.md`, reproduced both, including a two-file batch applied twice. PPCS `reports/examples/2026-10-18T00-11-46Z-95887b` ran only released 22.4.2: MG-02.held and MG-02.session-loss PASS, and MG-02.idle-session-timeout is INCONCLUSIVE because no session of runner A ended.

**Evidence against:**

- the PR is unmerged, and its author asked for manual testing;
- `idle_session_timeout` is off by default, and PostgreSQL's documentation discourages it for pooled connections;
- the common platform release steps run one runner;
- the AdonisJS 7 guide prefers them.

### <a id="l5-details"></a>L5

**The contract and the defaults** (Lucid `22.x` @ `f715bb4ecc` unless noted):

- the guide: a migration "must implement `up` (apply the change) and `down` (revert the change)" (lucid.adonisjs.com `content/docs/migrations/introduction.md` @ `798060f49a`, line 39). Lines 321–334 recommend `disableRollbacksInProduction` and forward-only production changes;
- `BaseSchema` defines `async up() {}` and `async down() {}` (`src/schema/main.ts`, lines 187–188);
- both generator stubs emit `down()`: `stubs/make/migration/create.stub`, lines 20–22 (`dropTable`), and `alter.stub`, lines 16–19 (an empty `alterTable` callback);
- the runner refuses a production rollback only when `disableRollbacksInProduction` is set (`src/migration/runner.ts`, lines 615–620). The command asks for consent in production unless `--force` is passed (`commands/migration/rollback.ts`, lines 139–150);
- the PostgreSQL config stub that `node ace configure @adonisjs/lucid` writes does not set the flag (adonisjs/presets `src/lucid/stubs/config/database/postgres.stub` @ `45fe1bc083`);
- the test hook: `migrate()` "returns a cleanup that runs `migration:reset` when the runner exits" (lucid.adonisjs.com `content/docs/testing/introduction.md`, line 40; `src/test_utils/database.ts`, lines 59–69). The AdonisJS 6 testing guide recommends it as "Reset database after each run cycle" (adonisjs/v6-docs `content/docs/testing/database.md` @ `0c513b5468`, lines 13–15).

**Inspected migrations:**

- **Data migrations with `this.defer`,** v6 import (`l5-c1`, 628 files) and v5 import (`l5-c2`, 138 files). Of 19 inspected (a documentation hit excluded):
  - 13 define a real `down()`;
  - 2 define a partial `down()` and say why. Crosstalk-Solutions/project-nomad @ `54ee30a449`: "The orphaned-row deletion is a one-way data change and is not restored here";
  - 4 define a `down()` that does nothing: adonisjs-community/polls-app `1633233019501_add_avatar_columns.ts` @ `cf58b99646` (empty), GTFB/Altrp3 `1644220662765_seed_users_by_uuids.ts` @ `e81b38550e` (a comment only), visualizevalue/opepen-api `1710861144474_migrate_set_submissions.ts` @ `4fe0421d10` (a comment only), and adocasts/adocasts `1764890613419_alter_progresses_table.ts` @ `2026084910` (an unfilled `--alter` stub);
  - none lacks `down()`.
- **Base rate** (`l5-c3`, 15,776 v6 migration files): 10 of 10 inspected define a real `down()`. All 10 come from one repository, adocasts/adocasts, so the sample is narrow.
- **Explicitly empty `async down() {}`** (`l5-c4`, 173 files): 10 of 10 inspected are empty; 3 change data and 7 change schema or extensions. This is the "empty explicit `down()`" case that our records class as the author's declaration. The filed warning would not catch it.

**Rollbacks in real workflows:**

- **Test bootstrap** (`l5-c10`, 246 `tests/bootstrap.ts` files with `testUtils.db().migrate()`): 9 of 10 inspected register it as a runner setup hook: kanwas-ai/kanwas, adocasts/adocasts, ferdium/ferdium-server, Dolu89/bitcoin-bips, arcweb/arcwell, batosai/adonis-starter-kit, RxCP/rxcp, StudyStorm/api-backend and gabrielmaialva33/innkeeper. frontendmu/frontend.mu calls it inside its own setup function. arcweb/arcwell also has an explicitly empty `down()` (`l5-c4`). There, the reset drops the `users` table in an earlier migration, which masks the effect (judgment, not run).
- **YAML** (`l5-c9`, 9 files with `ace migration:rollback`):
  - 5 are Taskfile development commands;
  - 2 are CI checks: LukaMrt/Sporty `.github/workflows/ci.yml` @ `dc6c5e7127`, lines 146–150, "Les migrations doivent être réversibles" (rollback everything, then re-apply), and Solvro/backend-topwr (a PR teardown, 22 stars). The Sporty check catches a missing `down()` only when the re-apply fails, as a schema change does;
  - 1 is a staging deploy that rolls back and re-runs on every push to `main`: nationskollen/server `.github/workflows/staging.yml` @ `311214bb9e`, lines 50–54;
  - 1 is a manual operations workflow that defaults to `production` and offers `rollback`, behind `force_operations`: BrightkyEfoo/rexel-modern-backend `.github/workflows/database-operations.yml` @ `4eaf75a71c`, lines 11–36 and 218–225.
- **`disableRollbacksInProduction`** (`l5-c7`, 87 files): of the 10 hits shown, 3 Lucid applications set it to `true` (acidiney/monolith-adonis5-boilerplate, Salman-Kashfy/Multitenancy-AdonisJS-5, batosai/karaoke). The rest are Lucid's source, documentation, and a ClickHouse package.

**Reports.** In 7 issue queries on 2026-10-26 (`l5-i1` to `l5-i7`), I found no Lucid issue other than #1204 about a migration with no `down()`, a rollback that did nothing, or a re-run after one. The rollback-titled Lucid issues are about other problems.

**Other ecosystem.** In [laravel/framework#57429](https://github.com/laravel/framework/pull/57429) (2025-10-17), a Laravel member proposed `make:migration --no-down`. Taylor Otwell closed it without merging. A contributor wrote: "if no down method exists and rollback called then Laravel just acting like this migration was rolled back successfully. I'm always creating down methods which throws a LogicException". Our record (nest-adonis-spike `docs/ppcs-migration-research/docs/missing-down-review.md` §2.3) has the source: Laravel calls `down` only if the method exists, then deletes the record. knex, MikroORM and Django refuse instead.

**Our evidence.** nest-adonis-spike `docs/ppcs-migration-research/docs/missing-down-review.md` §3: the scaffolded-application session, the command-class runs on PostgreSQL 18.6, and the schema-migration case, which fails loudly with "already exists". PPCS `reports/examples/2026-10-18T00-11-46Z-95887b`, `MG-03.no-reversal` for Lucid 22.4.2: FAIL, "revert reported reverted; marker count 1; history entries 0".

**Evidence against:**

- the guide requires `down()`, and both generators emit one;
- a well-maintained project in the sample writes partial `down()` methods with notes instead of omitting them;
- production rollbacks need `--force` and are discouraged;
- in full resets, earlier `down()` methods usually remove the effect.

### <a id="u1-details"></a>U1

**The project's size.** Kludex/uvicorn has 11,039 stars, and `uvicorn` had about 499 million downloads in the month to 2026-10-26 (pypistats).

**Inspected deployment hits.** From `u1-c1` (Dockerfiles, 1,510 files), `u1-c2` and `u1-c3` (YAML, 197 and 323 files) and `u1-c8` (`CONFIG_KWARGS` with the option, 141 files). Development configurations with `--reload` were skipped.

| Project | Setting | Lifespan shutdown | Shape |
| --- | --- | --- | --- |
| polarsource/polar (10,424 stars) | `server/Dockerfile` @ `7d30e464bc`, lines 103–106: 30 s | `server/polar/app.py`, lines 194–203: `redis.close(True)`, `async_engine.dispose()`, `sync_engine.dispose()` | Yes |
| BasedHardware/omi (13,822) | `backend/Dockerfile` @ `de8c7416e9`, line 63: 60 s | `backend/main.py`, lines 471–507: flushes, drains its own background tasks, then `close_all_clients()` | Yes |
| bytedance/deer-flow (84,448) | `deploy/helm/deer-flow/values.yaml` @ `19768d73cc`, lines 78–83: 10 s | The comment expects Uvicorn to close open connections before lifespan shutdown. The lifespan flushes and closes the memory backend (`backend/app/gateway/app.py`, lines 293–323) | Yes |
| gobifrost/bifrost (66) | `k8s/api/deployment.yaml` @ `ca905d3451`, lines 11 and 44–51: 2 replicas, 300 s | `api/src/main.py`, lines 233–237: closes an HTTP client, pub/sub, Redis and the database | Yes |
| spoo-me/spoo (264) | `deploy/docker-compose.prod.yml` @ `92f2b7269d`, lines 6–13: 30 s, 2 workers | `app/factory.py`, lines 238–243: closes Mongo, two Redis clients and an HTTP client | Yes |
| google/adk-recipes (10,537) | `core/python/long-horizon-harness/Dockerfile` @ `45a6999ec8`, line 35: 4 s | `horizon/fast_api_app.py`, lines 48–67: closes a plugin and a routine store. A recipe, not a deployment | Yes |
| BerriAI/litellm (62,071) | `litellm/proxy/proxy_cli.py` @ `dddbaa803d`, lines 318 and 638–643: the default 30 s, for both Uvicorn and Gunicorn | `litellm/proxy/proxy_server.py`, lines 1828–1831: waits for the in-flight request counter before teardown. The counter drops in a `finally` after the inner application (`litellm/proxy/middleware/in_flight_requests_middleware.py`, lines 47–54) | Guarded (HTTP only) |
| saleor/saleor (23,479) | `Dockerfile` @ `487885d437`, line 67: 30 s, `--lifespan=auto` | None: Django's ASGI handler, wrapped in `saleor/asgi` (source reading) | Cut-off only |
| suitenumerique/docs (16,948) | `Dockerfile` @ `00d8f231a8`, lines 188–194: 300 s | `--lifespan=off` | Cut-off only |

In none of them did I check whether a request's cleanup uses what the lifespan closes.

**Where the option is set, by query:**

- **Dockerfiles** (`u1-c1`, 1,510 files): the 5 inspected in the table all set it in the image's start command.
- **YAML** (`u1-c2` and `u1-c3`, 520 files). Of the 20 hits listed:
  - 11 set it for a deployed, sample or proof-of-concept service. Besides deer-flow, bifrost and spoo: xerrors/Yuxi, 5 s; shaongitbd/doory; yihong1120/Construction-Hazard-Detection, 10 s; NASA-AMMOS/MMGIS's sample, 10 s; hayatky/sdr-dtv-poc, 35 s;
  - 7 are development or local setups, most with `--reload`;
  - 2 only mention it in comments (SonarSource's Helm chart).
- **Server code** (`u1-c8`, 141 files that combine `timeout_graceful_shutdown` and `CONFIG_KWARGS`). Of 10 hits, 8 were inspected:
  - 6 set it in their server's start path: LiteLLM, by default 30 s; FastMCP, by default 2 s; DocsGPT, borg-ui and dramaclaw, in Gunicorn worker subclasses; an AWS sample, 30 s;
  - 2 are vendored copies of FastMCP's file.
- **FastMCP** (PrefectHQ/fastmcp, 28,208 stars; about 53.7 million downloads in the month to 2026-10-26) builds its HTTP server's `uvicorn.Config` with `"timeout_graceful_shutdown": 2` and `"lifespan": "on"` unless the caller passes `uvicorn_config` (`fastmcp_slim/fastmcp/server/mixins/transport.py` @ `57ff608ed5`, lines 339–352). What its application lifespan closes was not checked.
- **Not used:** the totals of the other queries (shell scripts, Procfiles, TOML files, the environment variable, and Python calls to `uvicorn.run`) are in `searches/searches.txt`. They were not inspected. The Python hits shown include local tools that set a short timeout so that Ctrl+C returns quickly. bghira/SimpleTuner, for example, sets 5 s: "Don't wait forever for SSE connection[s]".

**The audit report.** [CandleViewer/CandleViewer#2827](https://github.com/CandleViewer/CandleViewer/issues/2827), opened 2026-10-16 by a collaborator, is open:

- it quotes Uvicorn 0.54's `t.cancel()`, then `await self.lifespan.shutdown()`;
- its consequence: if `AuditWriter.stop()` runs first, "`emit()` raises `AuditWriterStopped`, `audit_close` logs `ws close audit not confirmed`, and the row is lost (logged, never silent)";
- its proposed fix is in the application: the lifespan waits for the handlers' teardown, for at most a bound;
- checked at `bd6f044375`: `services/api/candleviewer/server.py`, line 445, passes `timeout_graceful_shutdown` from `uvicorn_drain_timeout_s`, which defaults to 5 s (`settings.py`, line 671). The docstring at lines 413–415 says "past it uvicorn cancels what is left and still sends the lifespan `shutdown`". `ws/gateway.py`, lines 1306–1316, describes the close audit as best effort;
- not checked: the race itself, which is the project's description.

**Related reports with a different consequence or mechanism:**

- [mindsdb/cowork-server#734](https://github.com/mindsdb/cowork-server/pull/734) (2026-10-20, a contributor, 7 stars): "Every hosted deploy ends the answers running on the pods it replaces". With the option at 2 s, "uvicorn cuts the open stream about 2 s after SIGTERM, before the lifespan writes" its interruption message. The lifespan's write comes too late for the client. This is not the overlap.
- [chintanmehta21/Zettelkasten_KG#174](https://github.com/chintanmehta21/Zettelkasten_KG/pull/174) (2026-08-04, the owner, 0 stars) quotes production timestamps of an ingest lost when Gunicorn recycled a worker. The lost work was in the application's own tasks, which its lifespan never drained.

**Upstream:**

- per our record, discussion #2422 (2024) noted from source that the cancelled tasks are not awaited, got no reply, and was closed as outdated;
- the owner's PR [#2882](https://github.com/Kludex/uvicorn/pull/2882), "Add abort phase to graceful shutdown" (2026-04-02), was closed unmerged on 2026-04-06, with no description;
- Kludex/uvicorn-worker sets no `timeout_graceful_shutdown` today (`uvicorn_worker/_workers.py` @ `cd29cc6447`, lines 67–94). Its open [PR #46](https://github.com/Kludex/uvicorn-worker/pull/46) (2026-09-23, a user) adds `"timeout_graceful_shutdown": self.cfg.graceful_timeout`. `uvicorn-worker` had about 7.4 million downloads in the month to 2026-10-26 (pypistats).

**How common libraries behave when the lifespan closes them** (source reading, not run):

- an asyncpg pool's `close()` waits "until all pool connections are released" (asyncpg `asyncpg/pool.py` @ `13b01910da`, lines 1057–1072). The lifespan then waits for the cancelled request to release its connection;
- SQLAlchemy's `Engine.dispose()` leaves checked-out connections open (`lib/sqlalchemy/engine/base.py` @ `rel_2_0_44`, lines 3164–3183);
- psycopg_pool's `close()` does not close connections in use (`psycopg_pool/psycopg_pool/pool_async.py` @ `99356800e9`, lines 497–507);
- redis-py's asyncio pool disconnects connections in use by default, and its `aclose()` uses that default (`redis/asyncio/connection.py` @ `1923fb2722`, lines 3291–3312 and 3328–3333);
- so a cleanup that already holds a database connection survives these closes. One that needs a new connection, or uses Redis, can fail.

**Evidence against:**

- the option is off by default, and Gunicorn deployments do not set it today;
- LiteLLM guards against the overlap;
- the common database pools spare connections in use;
- PostgreSQL rolls back a transaction whose connection ends;
- where the platform's kill comes before the option expires, there is no overlap.

The Python tracker lists Uvicorn's SIGINT path as a trigger for PY-4. That is a different finding, and it is not reassessed here.

## Method

Read-only GitHub searches, through the shared paced search helper (adapted from PPCS `research/python-upstream-contribution/real-world-evidence/searches/rw_search.py`), on 2026-10-26 between 15:43 and 16:00 UTC.

- **Queries.** `searches/q-batch1.json` (L1), `q-batch2.json` (L3), `q-batch3.json` (L5), `q-batch4.json` (U1), `q-batch5.json` and `q-batch6.json` (follow-ups). 77 queries: 42 code searches and 35 issue searches. None failed.
- **Records.** `searches/searches.txt` lists each query with its total and the hits it showed. `searches/raw/` holds the raw results.
- **Counts.** Totals are GitHub's legacy code-search counts: files where the terms co-occur, including documentation copies and forks. Every count used above has an inspected sample, listed in the details.
- **Code.** Code was read at a commit through the contents API, or raw files at a tag, and not run.
- **Other reads:**
  - issue and pull-request bodies, comments and timelines;
  - npm (api.npmjs.org) and PyPI (pypistats) download counts;
  - the documentation sources cited, at the commits given.
- **Not searched:** GitHub Discussions, which the REST search does not cover, and Discord and Stack Overflow.
- **Our evidence,** read from PPCS `origin/main` and from nest-adonis-spike's `docs/` on branch `docs/lucid-isolation-level-fix`.
