# Transaction-success callbacks after a false commit

Started 2026-10-24. Written by: Claude Opus 5.5 (max).

When PostgreSQL has aborted a transaction, it answers the later `COMMIT` with the command tag `ROLLBACK`. Several frameworks report that ending as a commit (`TX-01A`). This study asks the next question. Does a callback that a framework documents as running after a successful commit run anyway, and so trigger an external side effect for data that was never committed?

This directory is outside `specifications/` and `harness/`. It adds no PPCS case and changes no classification. Nothing in it has been filed upstream.

## Already established before this study

Existing records already show success hooks running after PostgreSQL answered `COMMIT` with `ROLLBACK`. This study does not re-run them.

| Framework | Hook | Where | Upstream |
| --- | --- | --- | --- |
| Spring 7.0.9 | `afterCommit`, `afterCompletion(STATUS_COMMITTED)` | `research/production-reachability/`, run `2026-10-19T18-15-49Z-b2c174` | Draft S1, not filed |
| TypeORM 1.1.2 | `afterTransactionCommit` | the same run | typeorm#12992 |
| Lucid 22.4.2 | `after('commit')` | the same run | lucid#1205 |
| SQLAlchemy 2.1.5 ORM | `after_commit`, when `Session.execute()` raised, not when flush raised | `research/python-production-failure-gap-analysis.md`, P1 | The driver side is psycopg#1453 and asyncpg#1400 |
| Active Record 8.1.4 | model `after_commit` | `adapters/activerecord/FINDINGS.md`, a probe | Not filed. The Rails guide warns against rescuing `StatementInvalid` inside the block |

Weaker or ruled out, from the same records and source reading:

- **Django:** `atomic()` rolls back itself.
- **Hibernate:** it marks the transaction rollback-only and rolls it back.
- **jOOQ:** `commitEnd` runs in a `finally`.
- **EF Core:** the native path recovers through its own savepoints.

## In this study

| Subject | Status | Where |
| --- | --- | --- |
| Laravel 13.38.0 on pdo_pgsql 8.5.12 | Recorded. `afterCommit` ran for a transaction PostgreSQL rolled back, in both `DB::transaction()` and `DB::beginTransaction()`/`DB::commit()`. Three runs, three repetitions each, with controls. A deferred foreign key violated at `COMMIT` reproduces laravel/framework#61964 | [`laravel/`](laravel/README.md) |
| Stage 4 review | Done. pdo_pgsql's `PDO::commit()` returns `true` for a `COMMIT` answered with `ROLLBACK`: confirmed defect against its documented return value, by this study's reading. No independently actionable Laravel defect has been established for that path. The separate callback-retention defect (laravel/framework#61964) is confirmed and already reported. Recommendations: no Option B for now; a php-src issue is drafted, not filed; no php-src pull request yet | [`stage-4-review.md`](stage-4-review.md) |
| Patched driver | Recorded. With a pdo_pgsql patched to report the `ROLLBACK` tag as a failure, Laravel's `DB::transaction()` raises, but keeps the failed transaction's callbacks, and the next commit runs its `afterCommit`. A driver fix alone moves the wrong side effect; correct callbacks need #61964's fix too | [`patched-driver/`](patched-driver/README.md) |
| php-src issue | Drafted, not filed | [`upstream-drafts/php-src-pdo-pgsql-commit-rollback.md`](upstream-drafts/php-src-pdo-pgsql-commit-rollback.md) |

## Layout

- **`tools/`**
  - `container.sh`: this study's own PostgreSQL 18.6 container, on port 55491, with a random `cluster_name` token. It writes `.instance.json`, which is gitignored.
  - `pg-tag-recorder.mjs`: a pass-through wire recorder for `CommandComplete` tags, errors and `ReadyForQuery` status.
  - `recorder-check.mjs`: checks the recorder against node-postgres's own `Result.command`.
- **`laravel/`:** the Laravel and PDO scenarios, the runner, `check-run.mjs`, and the recorded output.
- **`repro/`:** two standalone reproductions and their outputs.
  - `pdo-commit-rollback.php` needs pdo_pgsql only.
  - `laravel-aftercommit/` needs `illuminate/database` 13.38.0; its `vendor/` is gitignored.
- **`pgsql-extension/`:** what the native pgsql extension and PDO each expose about the `COMMIT` reply.
- **`patched-driver/`:** the A/B experiment. Its `build.sh` builds PHP 8.5.12 and pdo_pgsql twice: stock, and with `pdo_pgsql-reject-rollback-tag.patch`. It also has `state-after-failure.php` and that script's outputs.
- **`upstream-drafts/`:** the php-src issue draft. Not filed.
- **`duplicate-search/`:** the queries and the label listings behind the review's duplicate assessment.
- **`stage-4-review.md`:** each check, with its contract, evidence, strongest counterargument and verdict.
