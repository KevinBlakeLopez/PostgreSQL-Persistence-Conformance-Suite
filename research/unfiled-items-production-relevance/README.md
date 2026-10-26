Written by: GPT-6 / Codex (effort setting not exposed).

# Production relevance of four unfiled findings

Assessed **2026-10-26**, under [the PPCS standard](../../docs/production-relevance.md). This is a read-only desk assessment of the existing evidence and public sources. No third-party application, reproduction, test or candidate fix was run. No upstream post or contact was made. Runtime statements below are the study's recorded results, not new measurements. The [inspection ledger](searches/inspection.md) distinguishes inspected code from reports and search leads.

## Judgment and filing order

| Finding | Tier | Likelihood, judgment on 2026-10-26 | Strongest real-world evidence | Displaces PY-6 next? |
| --- | --- | --- | --- | --- |
| Laravel nested MySQL 1205, F1 | **Middle** | **Low overall**; deterministic given the complete caught-nested shape and timeout | **Production for the trigger only:** Keystone.guru [#5340](https://github.com/RaiderIO/keystone.guru/issues/5340) quotes production Sentry counts and 1205s. No inspected application establishes the full silent shape | **No.** No incident of committed inner writes, and no complete exposed application path established |
| HikariCP F-H2 | **Middle** | **Low overall**; moderate plausibility in the narrower manual-commit schema/read-only workflows | **Incident for an adjacent cause:** [#2235](https://github.com/brettwooldridge/HikariCP/issues/2235), unusable pool and isolation error; [pgjdbc#3005](https://github.com/pgjdbc/pgjdbc/issues/3005) describes schema-per-tenant use. No report establishes reuse after a reset failure | **No.** The full conjunction is unverified in application code, and close reports an error |
| pdo_pgsql false successful commit | **Middle** | **Low overall** for the caught-error path; moderate plausibility conditional on an older-libpq deployment with rejected destructor SQL | **Reported reproduction of a related silent mechanism:** [GH-21869](https://github.com/php/php-src/issues/21869), a user's Aurora DSQL wire trace, through SQL `exec("COMMIT")`, not `PDO::commit()` | **No.** Same driver mechanism as PY-1a does not transfer its production evidence to PHP |
| Dramatiq Redis failed retry enqueue, F1 | **Higher, lower edge** | **Moderate**; broad Redis/Retry configuration, but an actor failure must coincide with an enqueue that never reaches Redis | **User self-report / acknowledged use of a workaround:** [#545 comment](https://github.com/Bogdanp/dramatiq/pull/545#issuecomment-2170038120). **Exposed configuration:** FitTrackee pins 2.2.1 and selects Redis plus Retries | **No.** Closest challenger, but PY-6 has an identifiable project's incident record and a deterministic normal-use trigger; F1 needs an outage window and its exact-loss report does not identify an application or deployment |

**Keep PY-6 as the next item to file.** Its baseline here is the [tracker's Higher assessment](../python-upstream-contribution-tracker.md#py-6-asyncpg-connectionreset-and-set-role), supported by Percolate's own changelog, not a new re-assessment of PY-6. Place Dramatiq immediately behind PY-6 among these candidates. Higher membership is a judgment about relevance, not an assertion that a production-confirmed loss was found. Dramatiq earns the lower edge through ordinary retry configuration, the exact-path user report, the independently observed Redis deletion, and substantial exposed application configuration. The report is less well sourced than PY-6's named-project record. Requiring a named incident for every Higher item would leave Dramatiq at the top of Middle instead; the facts would not change.

These tiers change neither severity, contract confidence, filing status nor readiness gates. In particular, the Laravel study calls for a human-written issue, and upstream contribution policies still apply. Nothing here is an upstream issue draft.

## 1. Laravel: a caught nested transaction's earlier writes survive MySQL 1205

### 1. Consequence

With MySQL's default `innodb_rollback_on_timeout=OFF`, earlier writes in a failed nested unit commit with the outer transaction, even though Laravel runs the inner `afterRollBack` and discards its `afterCommit` work. The inner call **does throw**; the false signal is that this unit was rolled back, followed by a successful outer commit. The caller receives no later warning that the inner writes survived. Queue/mail/event effects beyond the measured callbacks remain source reasoning, not measured end-to-end effects.

Evidence first: [F1 and controls](../mysql-transaction-state-divergence/findings.md#3-f1-a-nested-dbtransaction-failing-with-1205-is-not-rolled-back-to-its-savepoint), the [standalone reproduction and recorded output](../mysql-transaction-state-divergence/upstream/laravel-nested-1205/README.md), and its [facts package](../mysql-transaction-state-divergence/upstream/laravel-nested-1205/NOTES.md).

### 2. Triggers

**L1 — MySQL 1205 inside a caught nested managed transaction, with rollback-on-timeout OFF.**

- **In production:** **yes for the timeout; unknown for the complete failing shape.** Keystone.guru #5340, by the project's collaborator bot, quotes 14 events affecting 14 users in production v15.29.1 during October 4–8, with the timeout in page-view recording and waits consistent with the default 50 seconds. The Sentry instance was not accessed. [Laravel #40574](https://github.com/laravel/framework/issues/40574), by a user, describes timeouts while dispatching large SQS batches and has corroborating user comments. These establish contention, not F1's inner writes committing.
- **In our runs:** ordinary `DB::transaction()` calls, a real row lock held by another connection, and MySQL's own 1205. Laravel 13.38.0, PHP 8.5.12, MySQL 8.4.11. The 2-second and server-default 50-second arms agree; independent database and callback witnesses and the standalone output establish the consequence. No synthetic exception produces F1.
- **Code shape:** a service owns a nested all-or-nothing unit, performs essential writes before the timed-out statement, and a caller catches `DeadlockException`, `PDOException`, `Exception` or `Throwable` **inside an outer transaction that later commits**. It is reasonable to recover at a savepoint boundary for an independently meaningful subunit. If the entire outer unit is all-or-nothing, a competent design rethrows and rolls it all back. Optional work without its own boundary is not evidence of a reasonable design. A `catch (QueryException)` alone does not catch Laravel's nested `DeadlockException`. The framework comment expects this exception to propagate all the way out; that is important counterevidence about intended use, not a documented guarantee that timeout and deadlock have the same server outcome.
- **Real-world evidence:** strongest is **production for the event**, not the outcome. **0 of 16** inspected eligible files establish the complete failing application path. Bazar's [Cart helper](https://github.com/conedevelopment/bazar/blob/32bc97a593915ca40e1323239b6ffd9582aa2f5f/src/Models/Cart.php#L213) is a lead because it swallows its transaction's failure, but an outer committing caller was not traced. Freegle's retry helper is also latent under untraced nesting. Counterevidence includes Skrum rethrowing `DeadlockException`, VA-Studio rethrowing it after conservative file cleanup, and Likha-HR bypassing its retry catch when already inside a transaction. Commit links and inspected scopes are in the ledger. None is a demonstrated affected deployment.

**L2 — rollback-on-timeout ON, explicit savepoints, or catch outside the outer transaction (boundaries, not additional F1 triggers).**

- **In production:** ON exists in public deployment/configuration material: four inspected `.cnf` files enable it. None was established as a Laravel deployment, so they do not measure how often Laravel escapes F1. Manual savepoint and outer-catch designs also occur in the source sample.
- **In our runs:** the explicit nested `beginTransaction`/`rollBack` path contains 1205 with OFF; allowing the error to escape both managed levels rolls everything back with both settings. ON prevents F1's partial inner commit but produces the study's distinct O1–O3 problems. It is **not a blanket safe fix**.
- **Code shape:** let the full outer transaction fail, or explicitly roll back a surviving nested savepoint. A deployment changing ON must also account for loss of the entire outer transaction and vanished savepoints.
- **Real-world evidence:** **exposed counterexamples/configuration**, not incident evidence for F1. Laravel's `createOrFirst` demonstrates the legitimacy of a caught savepoint boundary, but catches only the unique violation and does not establish this 1205 path.

### 3. Reproduced on real code

**No application from the searches was run.** Existing runs execute the real Laravel package with constructed call sequences. The standalone reproduction is not an application. The default-configuration server timeout is a real database event, not a production incident.

### 4. Searches

GitHub code and issues, **2026-10-26**: `laravel-*`, `l-*` in [query definitions](searches/queries.json), [follow-ups](searches/supplement.json) and [totals](searches/totals.tsv). `laravel-code-07`: 92,928 files; `laravel-code-10`: 73; **0 of 16** eligible inspected files across these and `l-txlevel` establish the full F1 shape. Totals count loose tokens, not nested occurrences. Two queries with bare `1205` matched issue numbers and are excluded; explicit `in:body` replacements are retained. See [inspection rules and exclusions](searches/inspection.md).

History re-read: [#15932](https://github.com/laravel/framework/pull/15932) was explicitly about a deadlock ending the whole outer transaction; [#16140](https://github.com/laravel/framework/issues/16140) already distinguished timeout rollback; [#19749](https://github.com/laravel/framework/pull/19749) added timeout detection for retry purposes. [#61829](https://github.com/laravel/framework/issues/61829) concerns SQL Server's missing savepoint after a server-wide rollback, not F1. [MySQL's manual](https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html) confirms the statement-versus-whole-transaction distinction. The four ON configurations and the outer-catch/rethrow patterns are the negative search results that matter.

### 5. Likelihood (judgment, 2026-10-26)

**Low overall; Middle tier.** Timeouts clearly occur, the default server setting is exposed, and the constructed mechanism is strong. But a caught nested unit with earlier essential writes plus a continuing outer commit was not established in the application sample. The common event must not substitute for evidence of this conjunction. **Does not displace PY-6.**

### 6. Not established

Application frequency, an incident with inner writes surviving, a full affected caller chain, affected deployment configuration, or a Laravel 13 application run. Source equivalence is not a run of other Laravel/MySQL versions. No claim about PostgreSQL nested concurrency errors is added here.

**Single check most likely to change the rating:** a bounded caller search in Bazar for `Cart::toOrder()`, to establish or rule out an outer transaction that commits after the helper fails and retains earlier inner writes. A positive result would justify proposing a disposable MySQL run of that application's own path; no such run was made.

## 2. HikariCP F-H2: cleanup failure does not prevent recycling

### 1. Consequence

After an incomplete reset, another borrower can inherit non-default isolation and an old snapshot, the previous schema, or read-only/autocommit state. The study demonstrated committed cross-schema writes and repeated failed inserts. It did **not** demonstrate unauthorized tenant access or false write success. **`close()` throws first**; the subsequent borrower may see silently wrong reads/schema, or loud `25006`/`25P02` failures. This is unsafe reuse after a reported cleanup error, not a completely silent failure from beginning to end.

Evidence first: [study README, §8 and §18](../connection-pool-session-state/README.md#8-confirmed-defect-f-h2-hikaricp-recycles-a-connection-whose-state-reset-failed), [draft and reproductions](../connection-pool-session-state/upstream-drafts/hikaricp-failed-reset-recycled.md), and [pgjdbc follow-up facts](../connection-pool-session-state/upstream-drafts/pgjdbc-3005-getschema-comment.md).

### 2. Triggers

**H1 — `getSchema()` after the last commit/rollback, manual commit mode, and a dirty isolation or read-only property.**

- **In production:** **unknown for the complete sequence**. Schema/introspection and read-only reporting are ordinary operations, but no inspected application performs the exact sequence that causes reset rejection on close. Reports of the error alone cannot establish that reset failed and the same session was recycled.
- **In our runs:** real pgjdbc calls, no injection. `getSchema()` starts a transaction HikariCP's commit flag misses. A dirty isolation or read-only reset throws `25001`. Existing default-pool read-only reproduction and isolation reproduction agree across five HikariCP versions, through 7.1.0, with pgjdbc 42.7.14. The independent observer and server log establish reuse, snapshot and state. The pool-of-one schedule selects the dirty session deterministically; it does not measure the chance of encountering it in a larger pool.
- **Code shape:** finish ordinary work, then call a JDBC metadata-like getter before close while autocommit remains false; leave a changed property for the pool to restore. Reasonable JDBC usage, but a conjunction. HikariCP's `getSchema()` returns its cached schema after `DIRTY_BIT_SCHEMA` is set, so not every proxy getter reaches pgjdbc. Default `autoCommit=true` alone does not trigger this: the borrower has to disable it, and read-only reset must fail before autocommit can restore the state.
- **Real-world evidence:** **source exposure to components**, not the complete trigger. No full affected application path was found. The maintainer's [#1009 comment](https://github.com/brettwooldridge/HikariCP/pull/1009#issuecomment-345430245) explicitly considered partially reset connections but asked for a concrete failure that avoids eviction; it is not an incident admission. Its author later questioned the original diagnosis.

**H2 — `setSchema()` on a manual-commit pooled connection, plus a dirty property whose earlier reset fails.**

- **In production:** **yes for schema-per-tenant use; unknown for F-H2**. The user in [pgjdbc#3005](https://github.com/pgjdbc/pgjdbc/issues/3005) says this arose while implementing that pattern. HikariCP [#2144](https://github.com/brettwooldridge/HikariCP/issues/2144) and [#2235](https://github.com/brettwooldridge/HikariCP/issues/2235) establish related open-transaction effects. #2235's user reports an unusable pool with Kotlin Exposed 0.51, not a failed close reset followed by confirmed contaminated reuse.
- **In our runs:** real `setSchema`, configured `schema=public`, manual commit, and an earlier isolation reset that rejects the open transaction. The schema reset is skipped and the next borrower's committed unqualified write reaches `tenant_a`. This is distinct from #2081's unconfigured-schema behavior and #2144's reset later undone by rollback.
- **Code shape:** schema-per-tenant provider plus changed isolation/read-only on the same physical session, with no intervening tracked statement or explicit rollback to clear the driver-started transaction. Schema tenancy itself is reasonable; it does not establish the dirty reset prerequisite. Default autocommit restoration can commit the driver-started transaction before isolation reset; framework cleanup may also restore flags before the provider closes. These routes require tracing, not inference from two matching methods in a repository.
- **Real-world evidence:** **4 of 6** eligible inspected application/provider files directly call JDBC `setSchema`, **0 of 6** establish the entire failure sequence. Other hits use tracked SQL or a helper not traced. The ledger names them. Many set the desired schema on every acquire and/or restore it themselves on release, which narrows the particular cross-schema consequence; they are not evidence that the pool itself has fixed F-H2. Spring's example is instructional, not a deployed application. Schema selection is opt-in in Hibernate's inspected settings; SCHEMA multi-tenancy cannot be treated as universal Hibernate exposure.

**H3 — `setSavepoint()` begins a driver transaction HikariCP misses, followed by a rejected reset.**

- **In production:** **unknown for the complete trigger**. The API is ordinary; no matching application sequence or incident was established.
- **In our runs:** the study's real-API variant, not a mocked SQLSTATE. pgjdbc sends savepoint SQL with implicit BEGIN enabled. A savepoint alone does not prove an old query snapshot; the stale snapshot result belongs to the getter/query variant that actually took one.
- **Code shape:** a manual-commit connection with a changed reset property, ending with a savepoint and no subsequent tracked statement/rollback. Less natural than normal savepoint recovery, which executes statements and rolls back/releases appropriately.
- **Real-world evidence:** **source only** for external reach; no exposed full caller path. General failures of reset also have the study's stub regression tests, but injected stub failures establish a pool invariant, not production trigger frequency.

### 3. Reproduced on real code

**No application from the searches was run.** The existing study ran real HikariCP/pgjdbc with constructed programs and HikariCP's own stub-based tests. Spring, Hibernate, jOOQ, Exposed and the schema-tenant applications were not run for F-H2.

### 4. Searches

GitHub code/issues, **2026-10-26**: `hikari-*`, `h-isolation`, definitions and totals in `searches/`. `setSchema` plus `MultiTenantConnectionProvider`: **307** files, **4 of 6** eligible application/provider files directly use the JDBC call and **0 of 6** establish F-H2. `setSchema` plus `HikariDataSource`: **631** files, many datasource configuration setters and wrappers, not tenant checkout calls. Do not use that count as exposure. Exact server isolation-message query: **0**; pgjdbc's actual client message follow-up: **15**, including #2235 and #2144. The matching read-only search: **7**, including [Micronaut #2402](https://github.com/micronaut-projects/micronaut-data/issues/2402), which fails during connection setup, not evidence of recycle-after-reset-failure.

Known threads re-read: #1009, #2081, #2144, #1369, #1633, #2235 and pgjdbc#3005. #1633 documents the `currentSchema` JDBC URL workaround for a **different** configured-schema issue. #3005's maintainers discussed suppressing BEGIN for `setSchema`; the inspected current source still executes it through a Statement. None of those is a new filing opportunity for the already-reported schema defects.

### 5. Likelihood (judgment, 2026-10-26)

**Low overall; Middle tier.** There is credible schema-tenancy exposure and a natural deterministic JDBC trigger, but the critical dirty-reset combination was not found in application code. Within hand-managed, non-autocommit schema/read-only paths it is moderately plausible. The strongest operational reports are adjacent causes. **Does not displace PY-6**, whose session-role leak needs neither cleanup failure nor an unlucky terminal API sequence.

### 6. Not established

A production report of F-H2 itself; the same pool's full schema/isolation/read-only lifecycle in an application; actual tenant-boundary violation; frequency; or runtime behavior of a modern Hibernate/Spring provider. A custom `SQLExceptionOverride` that evicts on `25001` is an existing measured mitigation, not evidence it is commonly deployed. Generic `SQLException` reset failures must not be assumed to avoid HikariCP's eviction checks.

**Single check most likely to change the rating:** run one real Hibernate/Spring schema provider with its own non-default isolation/read-only configuration on a disposable PostgreSQL server, recording the last commit, schema call, framework flag restoration, close exception, backend identity and next borrower's state. This would settle whether routine framework cleanup reaches H2 or avoids it. Proposed only.

## 3. php-src pdo_pgsql: COMMIT answered ROLLBACK still returns true

### 1. Consequence

Every write in the aborted transaction is lost while `PDO::commit()` returns `true`. Laravel can then return normally and run after-commit work. Under exception mode the application usually already saw the statement error it caught; it receives no additional warning at commit. PDO exposes neither the command tag nor a distinction through `inTransaction()` after the transaction ends. The lower-level native pgsql extension exposes the tag; its caller has a different contract.

Evidence first: [Stage 4 review](../transaction-callbacks/stage-4-review.md), [PDO facts/draft](../transaction-callbacks/upstream-drafts/php-src-pdo-pgsql-commit-rollback.md), and [patched-driver runs](../transaction-callbacks/patched-driver/README.md).

### 2. Triggers

**P1 — catch a query error inside an open PostgreSQL transaction, then commit without savepoint recovery.**

- **In production:** **yes for aborted transactions and continued queries; unknown for this complete silent PHP application path**. [Nextcloud #55638](https://github.com/nextcloud/server/issues/55638), by a contributor, supplies deployment details and database errors during a scan; [Laravel #38172](https://github.com/laravel/framework/issues/38172), by a contributor, quotes `25P02` logs. [ARE #103](https://github.com/EDOS-Engineering/are/issues/103) describes production PostgreSQL use and a caught duplicate followed by a failing query, explicitly saying the data rolls back and the user sees a 500. These establish the **loud** continuation path. They do not establish a successful final `PDO::commit()`.
- **In our runs:** genuine `23505` through PDO and Laravel 13.38.0 on PHP 8.5.12/libpq 18.6/PostgreSQL 18.6. Minimal and instrumented runs agree: return `true`, wire tag `ROLLBACK`, aborted transaction and absent row. The locally patched driver raises instead. No third-party application was used.
- **Code shape:** catch an uncontained database error, then reach commit; for fully silent continuation it is the last statement or all later failures are caught too. A per-item batch or once-only final write can motivate catching, but correct PostgreSQL recovery needs a savepoint or rollback. Optional database work should get its own boundary. Calling `commit()` after a caught exception is not automatically a reasonable all-or-nothing design. Raw PDO callers, Laravel callbacks and DBAL callers must be assessed separately; framework adoption does not establish the catch. DBAL's inspected PDO driver delegates commit to PDO, but its ordinary `transactional()` error-escape path rolls back and its nested transactions use savepoints.
- **Real-world evidence:** **0 of 17** eligible inspected PHP files establish the complete silent PostgreSQL application path; **three PDO wrappers** are latent because they return false/swallow errors and delegate commit, but a real caller that ignores the result and commits was not traced. The ledger names ezSQL, h-php and Elefant. Laravel callers including mymate, StarCitizenWiki, m3u-editor and phpvms use a contained nested transaction/savepoint; fspbx catches outside. PHP does not look demonstrably more exposed than the filed study's Node/Java sample on this trigger. Neither convenience sample estimates prevalence.

**P2 — driver-internal destructor `DEALLOCATE` fails after the last application statement.**

- **In production:** **unknown for production; a user reports an abort/silent SQL-COMMIT outcome in their environment**. php-src [GH-21869](https://github.com/php/php-src/issues/21869), by user Benjscho, provides an Aurora DSQL wire trace on PHP 8.2.30 built against libpq 15. It ends in `exec("COMMIT")`, not the method assessed here. The report does not identify a production application. It establishes a related trigger/reproduction, not a production incident or a reproduced PDO::commit application failure. [GH-12940](https://github.com/php/php-src/issues/12940#issuecomment-2450489703) supplies a user's PgBouncer server log, but it is the loud form. The thread [ends with that user reporting the errors gone after rebuilding pdo_pgsql](https://github.com/php/php-src/issues/12940#issuecomment-2451680438).
- **In our runs:** **not run** for older-libpq/PgBouncer/DSQL destructor faults. Existing PDO::commit measurements use a caught query error on libpq 18.6. Protocol-close versus SQL-DEALLOCATE behavior is source reading.
- **Code shape:** a server-prepared statement is destroyed inside a transaction, its cleanup SQL is rejected, then the caller commits with no further query. Reasonable code; no application catch is required. It needs a build without `PQclosePrepared` (normally libpq before 17), and a server/pooler or stale statement name that rejects `DEALLOCATE`. An old server version alone does not establish it. Emulated prepares avoid these server-side statements; Laravel's pooled PostgreSQL mode already enables them in the recorded version.
- **Real-world evidence:** strongest is the **user's wire-level report**, scoped to DSQL and SQL COMMIT. PR [#21870](https://github.com/php/php-src/pull/21870) is still open and changes cleanup, not commit-tag validation. The historical [bugs.php.net #37870](https://bugs.php.net/bug.php?id=37870) is discussed in Stage 4, but could not be re-fetched in this pass and is **inherited evidence only**; its 2018 comment is not used to upgrade the tier.

### 3. Reproduced on real code

**No searched application was run.** Existing runs exercise the real PHP driver and Laravel package in constructed programs. The patched-driver matrix is a mechanism/correction experiment, not a deployed framework or real application run. GH-21869's third-party trace was read, not independently reproduced.

### 4. Searches

GitHub issues/code, **2026-10-26**, `pdo-*`, `php-*` in the definitions and totals. `pdo-code-08` (`DB::transaction`, catch, `23505`): **1,208** files; `pdo-code-09` (begin/commit/catch/UniqueConstraintViolationException): **1,224**; `php-pg-catch`: **774**. The eligible combined sample is **0 of 17** with an established silent PHP/PostgreSQL application path, three latent. Loose token results include non-PDO drivers and compatibility scripts; those are excluded. The broad `PDO`/commit/ROLLBACK/Postgres issue query returns **519**, not 519 affected apps. `25P02` issue queries find continuation, not commit outcomes.

Read GH-21869, PR #21870, GH-12940 and Laravel #61964 with comments. #61964 is a commit-exception callback-retention issue, not this driver's silent-success path. Existing source reading plus this pass's current code inspection support the separate ownership.

### 5. Likelihood (judgment, 2026-10-26)

**Low overall; Middle tier.** The driver has a broad potential surface, but the inspected application sample supports safe handling more than silent exposure. P2 is moderately plausible in an older-libpq deployment using prepared statements behind an incompatible pooler/server, yet neither its prevalence nor the final PDO::commit application path is established. **Does not displace PY-6.** PY-1a's Higher rating rests on its own Python reports; sharing PostgreSQL's command-tag mechanism does not transfer that evidence to PHP.

### 6. Not established

Frequency, a named real application losing writes while `PDO::commit()` returns true, a harmful after-commit consumer reached in that application's code, a real application reproduction, or the driver-internal trigger on current libpq. **A PDO fix alone does not fix Laravel's callbacks**: the existing patched-driver runs move the aborted transaction's `afterCommit` to the next commit through #61964. This is a separate bug and depends on another commit in the same process/connection lifecycle; it must not be described as the original driver's callback timing.

**Single check most likely to change the rating:** trace a real Elefant transaction caller that uses its false-returning `DB::execute()` wrapper, to see whether it preserves earlier writes, ignores a final database failure and then commits on PostgreSQL. That bounded search could turn a latent library shape into a concrete application path; propose a disposable run only if it finds one.

## 4. Dramatiq F1: the retry never reaches Redis, then the original is deleted

### 1. Consequence

A failed actor's original message is acknowledged and its Redis payload deleted even though no retry or dead-letter payload exists. Worker restart/heartbeat maintenance cannot restore an acknowledged, deleted payload. **Operational logs do report the actor failure and a CRITICAL middleware failure**; there is no durable failed-message record or successful retry. Call this lost work without broker recovery, not an absence of every signal.

Evidence first: [findings](../python-dramatiq-lifecycle/findings.md), [adversarial verification](../python-dramatiq-lifecycle/adversarial-verification.md#f1-a-failed-message-whose-retry-cant-be-enqueued-is-acknowledged-and-deleted), and [upstream opportunities](../python-dramatiq-lifecycle/upstream-opportunities.md). The verified scope is Redis, Dramatiq 2.2.1 and the studied master commit.

### 2. Triggers

**D1 — an actor fails with retries left, and its retry enqueue fails before Redis accepts it.**

- **In production:** **yes for Redis/socket failures and Redis/Retry use; exact loss is user-reported without deployment particulars**. User spumer describes this exact hook/enqueue/ACK path and says their workaround marks the message failed in [#545](https://github.com/Bogdanp/dramatiq/pull/545#issuecomment-2170038120). No application, broker configuration, logs, date of a particular outage or loss count is supplied. Treat it as a self-report of encountered behavior/workaround, not a verified production incident. [#894](https://github.com/Bogdanp/dramatiq/issues/894) explicitly reports socket stalls in Linux production, but in fetch, not F1's enqueue. Those are distinct evidence claims.
- **In our runs:** a real Redis stop/restart and refused enqueue; **21 of 21** original scheduled trials lost the work, across macOS/Linux, with Redis MONITOR, payload snapshots and independent execution witnesses. The barrier times an actor failure; it does not inject a Python broker exception. A further Redis restart and replacement worker found no payload to recover. Other adversarial arms use injected lost replies and are controls, not loss-frequency evidence. The ratio is reproducibility under a selected schedule, not production incidence.
- **Code shape:** RedisBroker and ordinary Retries, a failing actor with retries left, and an infrastructure failure during enqueue. No unsafe transaction catch or bespoke cleanup is required. Failures can be correlated when the actor itself relies on Redis. Retries is in the default middleware **only if a custom middleware list does not replace it**. `Retry(...)` and the last permitted retry are affected in the study; `throws`, exhausted retries and `retry_when=False` take the separate failed-message path. Redis client retries may mask a short outage, so a single refused socket is not necessarily enough: the enqueue must finally raise without having been accepted.
- **Real-world evidence:** self-report plus **exposed configuration**, read at commits. FitTrackee (1,174 stars at inspection) [selects Redis outside tests](https://github.com/SamR1/FitTrackee/blob/9ff0bc0412ea3f687e153d027444a50aedb44a75/fittrackee/config.py#L15), [includes Retries](https://github.com/SamR1/FitTrackee/blob/9ff0bc0412ea3f687e153d027444a50aedb44a75/fittrackee/dramatiq_broker.py#L50), and [pins 2.2.1](https://github.com/SamR1/FitTrackee/blob/9ff0bc0412ea3f687e153d027444a50aedb44a75/pyproject.toml#L39). This is an application configuration, not an incident or a run. **9 of 13** inspected unique configurations retain/include Retries; one (Polar) uses an uninspected fork, leaving **8 of 13** with upstream-compatible potential configuration. Four omit Retries. These convenience counts are not market share.

**D2 — retry publishing fails on RabbitMQ while the consumer remains able to ACK (separate, unestablished trigger).**

- **In production:** **unknown for this exact trigger**.
- **In our runs:** **not run**. The study's RabbitMQ statements are source reasoning only.
- **Code shape:** publisher failure without losing the consumer's delivery/channel, followed by its successful ACK. If the consumer connection dies, RabbitMQ's normal unacknowledged redelivery changes the outcome. A general broker outage is not interchangeable with the Redis trigger.
- **Real-world evidence:** none establishing this conjunction. #545's maintainer discussion mentions both brokers but does not validate a RabbitMQ failure. **No RabbitMQ Higher rating is assigned.**

### 3. Reproduced on real code

**No searched application's actor was run.** Existing study runs use real Dramatiq CLI/default middleware and Redis with constructed actors. Upstream-fixture regression tests and candidate fixes are existing evidence, not a new application reproduction. FitTrackee, sbomify and Polar were read only.

### 4. Searches

GitHub code/issues, **2026-10-26**, `dramatiq-*`, `d-*`, definitions and totals in `searches/`. Broad RedisBroker/Dramatiq query: **1,314** files; legacy matching includes Dramatiq itself, virtual environments and harvested copies, excluded from adoption. RedisBroker/custom-middleware query: **89**, inspected with deduplication. Stronger import/Retry follow-up: **411**. The resulting **9 of 13** configuration sample and fork exclusion are in the ledger. Exact user comments on #545 were fetched directly: GitHub issue search did not return them in the comments query, so that query's five results cannot support an absence claim.

Evidence against overgeneralization: [#527](https://github.com/Bogdanp/dramatiq/issues/527) is a **staging** test of delayed jobs that later recovered, not permanent retry loss. sbomify [#1707](https://github.com/sbomify/sbomify/pull/1707) is a named project's audit/fix for stranded delayed messages and consumer errors, **F2/F3/F4**, not F1. Its override does not modify the retry hook. Polar (10,425 stars) has relevant configuration but its pyproject selects `frankie567/dramatiq`; that fork was not checked, so do not count it as confirmed stock exposure. FitTrackee provides the cleaner exact-version application lead.

### 5. Likelihood (judgment, 2026-10-26)

**Moderate; Higher at its lower edge for Redis only.** The common default retry path plus ordinary infrastructure failure, exact-path user report/workaround and confirmed irreversible broker deletion are stronger than the three other candidates' application exposure. The important narrowing is the enqueue must never be accepted, which client retries can prevent for brief faults. The public exact-loss report is not attributable to a named application/deployment. **Does not displace PY-6**: normal session role reuse is deterministic once configured and has a named project's own incident record; this requires a coincident failure window. The ordering is provisional judgment, not a measured rate comparison.

### 6. Not established

Production loss frequency, the fraction of Dramatiq deployments using Redis/default Retries, a named application's F1 incident with logs or payload evidence, Polar's fork behavior, or RabbitMQ loss. A lost enqueue reply is **not** the same trigger: in the study, Redis accepted it and work survived once or twice. A failed ACK after a successful enqueue also did not produce F1 loss. The corrective design remains a maintainer decision: the study's enqueue-retry option introduced duplicates after a lost reply, so readiness of a report is not approval of that fix.

**Single check most likely to change the rating:** run FitTrackee's own retrying background task on its pinned Dramatiq 2.2.1, with Redis unavailable until the retry enqueue definitively fails, then restore Redis and inspect both task outcome and durable payload. Use its application/worker, not a copied call sequence, and only disposable data. Proposed only; a confirmed real-application loss would make the Higher placement much firmer and could move it ahead of PY-6.

## What was independently checked, and what was not

Current code was fetched at these commits on 2026-10-26. This supports mechanisms **by source reading**, not new runtime/version claims:

| Source at commit | Read and verified |
| --- | --- |
| Laravel `13.x` [f3adacd431](https://github.com/laravel/framework/blob/f3adacd43137e2f6771ec4686d97ea05d437c410/src/Illuminate/Database/Concerns/ManagesTransactions.php#L88) | Nested concurrency branch decrements, calls the manager and throws without `rollBack`; detector includes timeout text; manager executes rollback callbacks. Commit-exception handler still does not clear manager records |
| HikariCP `dev` [a4d93f4f85](https://github.com/brettwooldridge/HikariCP/blob/a4d93f4f85517f90e632b795486d7102e933d7ff/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java#L240) | Recycle in finally, conditional rollback, eviction classification, uncaptured schema commit state, cached getter; `PoolBase` reset order read-only, autocommit, isolation, then schema |
| pgjdbc [8747452584](https://github.com/pgjdbc/pgjdbc/blob/874745258455be18708d91a24cc98a0ae5ae85a3/pgjdbc/src/main/java/org/postgresql/jdbc/PgConnection.java#L1737) | Schema getter/setter use Statements; savepoint calls intentionally permit implicit BEGIN; read-only/isolation setters reject non-idle state with the client error text, before a server SET |
| php-src `master` [1b1aa35780](https://github.com/php/php-src/blob/1b1aa35780343de5fadbe25d9cfa5da7c3d5d894/ext/pdo_pgsql/pgsql_driver.c#L637) | Commit helper checks result status, not `PQcmdStatus`; statement cleanup conditionally uses SQL DEALLOCATE without `PQclosePrepared` |
| Doctrine DBAL [fd0dac6f2e](https://github.com/doctrine/dbal/blob/fd0dac6f2ea1fafbb55919559396bfb945939f13/src/Driver/PDO/Connection.php#L111) | PDO driver delegates commit; outer `Connection` has rollback-only checks, rollback-on-escape transactional handling and savepoints. No generic claim that every Doctrine transaction is exposed |
| Dramatiq [08d711a761](https://github.com/Bogdanp/dramatiq/blob/08d711a7611077e3d07ce1006349bc9342ada6e8/dramatiq/broker.py#L121) | `emit_after` logs/swallows the retry hook exception; retries calls enqueue; worker finally calls post-processing, chooses ACK if not failed; Redis ACK deletes payload; default middleware includes Retries |
| Applications/configuration | Exact commit links, scopes and exclusions in [inspection ledger](searches/inspection.md); FitTrackee version/configuration and sbomify override/settings read together; Polar fork override read |

**Reports:** issue bodies/comments were read, including the named history and prior reports. We verified what reporters said, not their private logs, installations, screenshots or outcome measurements. Keystone.guru's event counts, #2235's unusable pool, GH-21869's wire trace and #545's workaround are report evidence. None is an independently executed application check. Bug #37870 is inherited from Stage 4 and unavailable in this pass. Other search hits left at titles/fragments are leads only; none is used as proof of exposure or a production outcome.

## Narrowings and proposed record changes

- Laravel's own caught unique-error/savepoint pattern supports the boundary design, **not** proof that its `createOrFirst` reaches nested 1205. Its catch does not catch the dedicated nested exception. ON changes the failure family rather than fixing all transaction bookkeeping.
- HikariCP's broad risk is real in the recorded runs, but **schema tenancy alone is insufficient**, and `close()` signals failure. Correct-schema selection on every acquire narrows cross-schema harm. Neither source nor reports establish unauthorized tenant access. The first isolation search used the server SET wording; pgjdbc's reset rejection occurs client-side with different wording.
- PHP's evidence does not inherit PY-1a's likelihood. The strongest independent silent report uses SQL COMMIT on DSQL and older libpq; PostgreSQL/PgBouncer reports are loud. GH-12940 includes a successful rebuild mitigation. Driver and Laravel callback fixes remain separate.
- Dramatiq loss is specific to an enqueue not accepted by Redis. #527 and sbomify's report must not be relabeled permanent F1 loss; RabbitMQ remains unmeasured. Polar's fork is unverified.

**Proposed only:** add links to this assessment from the four studies, record the three Middle ratings and Dramatiq Redis's provisional lower-edge Higher rating, and place Dramatiq behind PY-6 in the filing queue. Leave the Python item's own rank and evidence unchanged. Update upstream-submission records only after an actual approved filing. The tracker and `docs/upstream-submissions.md` are not edited by this assessment.
