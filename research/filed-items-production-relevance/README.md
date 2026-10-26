# Production relevance of the filed upstream items

Assessed 2026-10-26. Written by: Claude Opus 5.5 (low), from four group assessments written by Claude Opus 5.5 (max).

This page rates every non-Python finding that has been filed upstream as an issue, pull request, comment or discussion, under [`docs/production-relevance.md`](../../docs/production-relevance.md). The Python items are rated in the [Python tracker](../python-upstream-contribution-tracker.md).

The list of filed items comes from the filer's public GitHub activity since 2026-10-17, checked against [`docs/upstream-submissions.md`](../../docs/upstream-submissions.md). They agree. Uvicorn discussion #3232 is the one filed item that tracker does not list.

**Not rated:**

- A1 (adonisjs discussion #5166) asks a question; it reports no finding.
- P1 (psycopg#1453) is PY-1a in the Python tracker.

This is a desk assessment. The searches and reads were read-only, and nothing was run, posted or sent. Claims about third-party code are source reading at the commits cited. Reports that quote production data were not checked beyond the report.

## Tiers (judgment, 2026-10-26)

The tiers follow the Python tracker's. They weigh likelihood, the strength and source of the evidence, and whether the failure is silent. They are a judgment. They change no severity rank and no status.

- **Higher:** none. No production report of a silent outcome names one of these libraries.
- **Middle:**
  - CI2 (CodeIgniter, a deadlock) and U1 (Uvicorn's shutdown overlap), both moderate;
  - K3 (knex, a failed `BEGIN`), moderate but loud;
  - L2 (Lucid's false commit), Y2 (Kysely `isCommitted`) and T2 (TypeORM `release()`), low to moderate;
  - Y1 (Kysely reuse after a `ROLLBACK` that was never sent), T3 (TypeORM `afterTransactionCommit`) and J1 (pgjdbc), low.
- **Lower:**
  - CI1, L1, L5, K1, D1, PI1, K2, T1, M4 and M2, all low;
  - M3, fixed on MikroORM's default branch but in no stable release;
  - L3, which is in no released version.
- **No production trigger:** L2's case 3, a failed `ROLLBACK TO SAVEPOINT`, which our runs produced only by injection.
- **Folded into other items:** Y3 is our validation of Kysely's fix for Y2. K2-PR is our fix for K2.

| ID | Filed as | Tier | Likelihood | Strongest real-world evidence | Details |
| --- | --- | --- | --- | --- | --- |
| CI2 | codeigniter4/CodeIgniter4#10649, PR #10651 | Middle | Moderate | Production, for the trigger: opensourcepos#4320 quotes a deadlock in OSPOS's sale transaction. OSPOS 3.4.3 ships that code on CodeIgniter 4.7.4, an affected version | [codeigniter](codeigniter/README.md) |
| U1 | Kludex/uvicorn discussion #3232 | Middle | Moderate | Audit: CandleViewer#2827 reports a close-audit row lost to this race. Exposed code: Polar sets the option and disposes its engines in the lifespan; FastMCP sets 2 s by default | [lucid-uvicorn](lucid-uvicorn/README.md) |
| K3 | Comment on knex/knex#4709 | Middle | Moderate (loud) | Production: knex#4630 quotes production logs. Audit: supabase/storage works around #4709 | [control-failures](control-failures/README.md) |
| L2 | adonisjs/lucid#1205 | Middle | Case 2 low to moderate; the others low | A user's comment on #1205 reports case 2 in an app, through a deferred constraint (not checked). Harmful consumer: `@jrmc/adonis-attachment` deletes files in `after('commit')` | [false-commit](false-commit/README.md) |
| Y2, Y3 | kysely-org/kysely#2157; comment on PR #2161 | Middle | Low to moderate | Audit: laclemen92/warden#148, "returned 200, ran `afterCommit` and reported success, but nothing was saved" | [false-commit](false-commit/README.md) |
| T2 | typeorm/typeorm#12978 | Middle | Low to moderate | Audit: OneUptime#4650 reproduced TypeORM's dropped `ROLLBACK` behind PgBouncer, and the next request committing the write | [control-failures](control-failures/README.md) |
| Y1 | Comment on kysely-org/kysely#1990 | Middle | Low | Acknowledged: kysely#2148 by a maintainer; fixed on `master` by #2155, in no release | [control-failures](control-failures/README.md) |
| T3 | typeorm/typeorm#12992 | Middle (lower edge) | Low | Harmful consumer: Vendure's EventBus publishes a transaction's events on `afterTransactionCommit` | [false-commit](false-commit/README.md) |
| J1 | pgjdbc/pgjdbc#4494 | Middle | Low | Exposed code, 2020: pgjdbc#1697 and #1739 (ShedLock). pgjdbc's 42.2.11 exception was reverted in 42.2.12 | [false-commit](false-commit/README.md) |
| CI1 | codeigniter4/CodeIgniter4#10648, PR #10650 | Lower | Low | None with the filed shape | [codeigniter](codeigniter/README.md) |
| L1 | adonisjs/lucid#1202, PR #1203 | Lower | Low | Exposed code: NIAEFEUP/enei opens a manual SERIALIZABLE transaction | [lucid-uvicorn](lucid-uvicorn/README.md) |
| L5 | adonisjs/lucid#1204 | Lower | Low | Other ecosystem: a Laravel contributor describes the same behaviour (laravel/framework#57429) | [lucid-uvicorn](lucid-uvicorn/README.md) |
| L3 | Comment on adonisjs/lucid PR #1168 | Lower | Low; none in released versions | None for the regression. AdonisJS's deployment guide documents concurrent runners | [lucid-uvicorn](lucid-uvicorn/README.md) |
| K1 | knex/knex#6547 | Lower | Low | None; one latent hit | [false-commit](false-commit/README.md) |
| D1 | drizzle-team/drizzle-orm#6572 | Lower | Low | Only the loud form, in production reports | [false-commit](false-commit/README.md) |
| PI1 | Comment on prisma/orm#20496 | Lower | Low | The host issue, a 2023 reproduction made for a library feature | [false-commit](false-commit/README.md) |
| M3 | mikro-orm/mikro-orm#8476 | Lower | Low; fixed, unreleased | None | [false-commit](false-commit/README.md) |
| K2 | knex/knex#6546, PR #6548 | Lower | Low | The same mechanism in other libraries; none on knex | [control-failures](control-failures/README.md) |
| T1 | typeorm/typeorm#12976, #12977, PR #12979 | Lower | Low | The trigger occurs (typeorm#11543, #12308); a maintainer calls concurrent nested transactions invalid | [control-failures](control-failures/README.md) |
| M4 | Comment on mikro-orm/mikro-orm PR #8448 | Lower | Low | None. A downstream audit, open-mercato#7333, scoped the case out | [control-failures](control-failures/README.md) |
| M2 | Comment on mikro-orm/mikro-orm PR #8462 | Lower | Low; fixed, unreleased | None. #8458's reporter injected the failure | [control-failures](control-failures/README.md) |

## What the evidence shows across the groups

- **The false commit is common in reports and rare in the inspected code.** 0 of 84 inspected code hits on the eight Node.js and Java findings have the silent shape: most catch outside the transaction, rethrow, or use a savepoint or `ON CONFLICT`. The silent form appears instead in projects' own reports: warden and Wagonwise on Kysely, Medplum (a maintainer, not reproduced), Windmill on Rust and sqlx, and awcms, which counts about 45 such sites on Bun's SQL client.
- **Raising has a cost.** Bun 1.4.3 now throws `ERR_POSTGRES_COMMIT_ROLLED_BACK` (checked at tag `bun-v1.4.3`); awcms reports that this turned its 45 sites into 500s. pgjdbc reverted its 2020 exception for the same reason.
- **The silent reuse findings need pg's client-side `query_timeout` without a shorter server-side timeout.** That setup is a minority in the inspected configurations (12 of 35 hits), but it includes Twenty, and PgBouncer pushes projects toward it by dropping a `statement_timeout` set at connect.
- **Several fixes are merged and unreleased.** M2 and M3 are on MikroORM's default branch; Y1's fix (#2155) is on Kysely's `master`. In the meantime, MikroORM's development builds since 2026-10-19 pin Kysely 0.29.7, which turns M4's held slot into Y1's silent reuse (source reading).

## Notes on what was filed

None of these contradicts a filed claim. Each narrows one, or corrects our own records:

- **M4.** The posted sentence "the slot is held for the life of the process" holds for MikroORM 7.2.5. With Kysely 0.29.7, which MikroORM's development builds pin, the slot is released with its transaction open instead (source reading).
- **U1.** The posted `ConnectionError` came from the test's own pool. asyncpg's `Pool.close()`, SQLAlchemy's `dispose()` and psycopg_pool's `close()` spare connections in use (source reading), so the harm is cleanup that needs a new connection, or clients such as redis-py that disconnect connections in use.
- **CI1.** #10648 says "4.7.0 (measured)". PPCS records runs on 4.7.5 only; 4.7.0 has the same `reconnect()` by source reading.
- **K3.** The research draft's note says the #4709 reporter used `query_timeout`. Their reproduction forced the timeout by editing pg's client. The posted comment does not repeat the note.
- **Records corrected in the same change as this page:** T2's filing date (2026-10-17, not 2026-10-18); PI1, which `research/production-reachability/` listed as an unfiled draft; and the list of submitted reports in `docs/caught-unique-violation.md`.
- **Links into `nest-adonis-spike`.**
  - That repository is private, so PPCS's links into it do not open for other readers.
  - Three of the files `docs/upstream-submissions.md` links are not committed on any branch: `docs/mikroorm-pr-8462-validation.md`, `docs/typeorm-savepoint-depth-fix/HANDOFF.md` and `docs/typeorm-savepoint-depth-fix/design-review.md`.

## Method

Four read-only desk assessments on 2026-10-26, between about 15:40 and 16:35 UTC:

- **Searches.** 279 GitHub searches (issues and code) through [`paced_search.py`](paced_search.py), which spaces searches across processes. Each group's `searches/` folder holds its query files and `searches.txt`, which lists each query with its total and the hits it showed. Two code queries failed with HTTP 503 and were replaced.
- **Reading.** Code was read at the commits cited, through the contents API, and never run. Each "k of n" count rests on hits read at their commits.
- **Checking.** The coordinator re-checked the strongest claims of each group against the sources before this page was written. That covers the quoted reports, the cited source lines, release contents, npm pins and compare results.
- **Not committed.** The raw search results and the fetched third-party files are not committed.
- **Not searched.** The CodeIgniter forum returned HTTP 403, and GitHub Discussions are not covered by the search API.

A search that finds nothing is a result with a scope, not proof of absence.
