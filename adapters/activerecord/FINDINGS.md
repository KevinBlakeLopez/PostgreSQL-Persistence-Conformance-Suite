# Active Record findings

Recording: [`reports/examples/2026-10-23T21-46-47Z-b3b7bd`](../../reports/examples/2026-10-23T21-46-47Z-b3b7bd/summary.md). It re-records [`reports/examples/2026-10-21T19-39-32Z-b559f2`](../../reports/examples/2026-10-21T19-39-32Z-b559f2/summary.md), from which these findings were written, with `form` reported as a string. Every cell the two runs share has the same classification. The later catalog case `TX-01B.commit-reply-unseen` is NOT_RUN. Ruby 4.0.7 (`ruby 4.0.7 (2026-09-15 revision 229531a6cf)`), Active Record 8.1.4, pg 1.7.0, `PG.library_version` 180006, PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2). Three repetitions agreed on every row. CTL-01 passed. `pg-control` held its gate. The ruby-pg control in the same run matched its expectations. No row is a repetition disagreement.

Rails 8.1.4 is the latest stable release (24 September 2026). Rails 8.2 is `8.2.0.alpha` on `main` and is not on RubyGems. The [maintenance policy](https://rubyonrails.org/maintenance) lists 8.1.x bugfix support through 10 October 2026 and security support through 10 October 2027. This run is after the bugfix date and inside the security window.

A FAIL is a counterexample to a PPCS invariant under these versions and this fault category. It is not, by itself, a defect report. Nothing was filed upstream.

The scored path is `ActiveRecord::Base.transaction` and `create!`. Nested cases use `transaction(requires_new: true)`, which the [transaction API](https://api.rubyonrails.org/v8.1.4/classes/ActiveRecord/Transactions/ClassMethods.html) documents as a savepoint. There is no Rails application and no `database.yml`. Category C and D faults are injected on `PG::Connection` before Active Record sees the error. The command tag in the diagnostics is not the reported outcome.

## Results

| Case | Fault | native |
| --- | --- | --- |
| `CTL-01.commit` | none | PASS |
| `CTL-01.rollback` | none | PASS |
| `TX-01A.caught-error-then-commit` | A | FAIL, mechanism exercised |
| `TX-01B.conn-lost-before-commit` | B | PASS |
| `TX-01B.commit-reply-discarded` | D | PASS, TX-01B.2 not exercised |
| `TX-01B.commit-reply-unseen` | E | NOT_RUN |
| `TX-02.savepoint-rollback-not-sent` | C | FAIL |
| `TX-02.savepoint-rollback-rejected` | C | FAIL |
| `TX-02.conn-lost-before-savepoint-rollback` | B | PASS |
| `TX-03.rollback-not-sent` | C | PASS |
| `TX-03.statement-error-rollback-not-sent` | C | PASS |
| `TX-03.conn-lost-in-transaction` | B | PASS |
| `TX-04.nested-failure-contained` | none | PASS |
| `TX-04.nested-released-outer-rollback` | none | PASS |
| `TX-04.independent-inner` | none | UNSUPPORTED, not applicable by design |
| `TX-05.managed-serializable` | none | PASS |
| `TX-05.explicit-serializable` | none | UNSUPPORTED, capability absent |
| `MG-02.held` | none | PASS |
| `MG-02.first-deployment` | none | PASS |
| `MG-02.session-loss` | B | PASS |
| `MG-02.idle-session-timeout` | none | INCONCLUSIVE |
| `MG-03.valid-reversal` | none | PASS |
| `MG-03.no-reversal` | none | PASS |
| `MG-03.failing-reversal` | none | PASS |

## Documented contract

The transaction guide says four things that this run uses as the contract, not as a score:

1. The block commits when it returns. A raised exception rolls back and is re-raised. `ActiveRecord::Rollback` rolls back and is not re-raised.
2. Rescuing `ActiveRecord::StatementInvalid` inside the block does not roll the transaction back. On PostgreSQL a statement error aborts the transaction until it is restarted. The guide's example is a rescued unique violation, then another statement in the same block.
3. A nested `transaction` joins the parent. `requires_new: true` is a savepoint (`SAVEPOINT active_record_N`), not a second database transaction.
4. `after_commit` is described as running when the database is in a permanent state. `after_rollback` runs when the transaction or savepoint is rolled back.

`ActiveRecord::RecordNotUnique` is a subclass of `StatementInvalid`. Rescuing it is the warned pattern. The scored TX-01A case rescues `StatementInvalid` because that is the case's step, not because the guide recommends it.

`commit_db_transaction` in Active Record 8.1.4 calls `internal_execute("COMMIT", ...)`. `perform_query` keeps `cmd_tuples` and `ntuples`. This reading of `postgresql/database_statements.rb` at 8.1.4 does not show a check of `cmd_status`. The run is what shows the tag.

## TX-01A

Observed, three times. `Uniq.create!(code: "taken")` raised `ActiveRecord::RecordNotUnique` with SQLSTATE `23505`. The rescue returned. `ActiveRecord::Base.transaction` then returned. The adapter reported `committed` because the call returned. The trace on that backend is `COMMIT` answered with command tag `ROLLBACK`. The runner's mechanism check is true: after the call returned, the session was idle and its last statement was `COMMIT`. The marker was absent. `pg_xact_status` was aborted.

Between the unique-violation error and `COMMIT`, the trace records a statement whose text is `;`. That statement did not finish the aborted transaction. The following `COMMIT` still received `ROLLBACK`.

This is the PPCS failure. It is also the usage the transaction guide says not to write. The guide does not say the block will raise when `COMMIT` comes back as `ROLLBACK`. It says the transaction is unusable and should be restarted. The block returning is consistent with "a rescued exception does not roll back" and inconsistent with a reader who treats a normal return as a committed PostgreSQL transaction. Those are different claims. The PPCS result is the second one, under the suite's rule that a normal return is `committed`.

### Documented restart

`adapters/activerecord/probes/tx01a_followups.rb` is not a PPCS case. On one database, letting `RecordNotUnique` leave the block produced `ROLLBACK` with command tag `ROLLBACK`, no row for that insert, then a new `transaction` that inserted `safe-restart` and got command tag `COMMIT`. The independent connection saw only `safe-restart`. `after_rollback` ran for the failed record. `after_commit` did not.

## TX-01B

Connection loss before `COMMIT` (`pg_terminate_backend`) raised `ActiveRecord::ConnectionFailed` (`PQconsumeInput() FATAL: terminating connection due to administrator command`). The adapter reported `failed`. The marker was absent. PASS for TX-01B.1.

The discarded-reply case is a client-side simulation: `COMMIT` is sent, the connection is closed, and Active Record sees `PG::ConnectionBad: connection is closed`. The adapter reported `failed`. The marker was present and the captured transaction was committed. The API did not report a commit and did not report a rollback. TX-01B.2 is not exercised: the manifest lists no rollback-claim channel, and the scored path does not register `after_rollback`. A failed report is not a confirmed rollback.

## TX-02

Category C is an injection in this process, once, before Active Record sees the error. It is not a production network failure.

Both client-side savepoint failures: the inner `transaction(requires_new: true)` raised, the outer block rescued that error, and the outer `transaction` returned. The adapter reported `committed`. The original backend was gone at `after-outer`. The captured transaction was aborted. Neither marker remained. A different backend then sent `COMMIT` and received command tag `COMMIT`. That second `COMMIT` is not the captured transaction.

The trace fits `TransactionManager#within_new_transaction` in 8.1.4: when the transaction state is not completed, the ensure calls `throw_away!`, which removes the connection and disconnects it. The outer block has already rescued the inner error, so the outer `transaction` still tries to commit, on a connection that was not in the original transaction. TX-02.1 fails because the API reported a commit of a transaction PostgreSQL aborted. TX-02.2 holds: the original session was not left inside a transaction.

Connection loss inside the savepoint raised out of the outer `transaction` as an error the block did not raise. The adapter reported `failed`. The captured transaction was aborted. PASS.

When the savepoint rollback is not injected, both TX-04 cases pass. A nested failure with `requires_new: true` keeps the outer row and drops the inner row. A released savepoint is removed when the outer transaction raises. `TX-04.independent-inner` is not applicable by design: `requires_new: true` is a savepoint on the same connection.

## TX-03

All three cases pass. After a withheld `ROLLBACK`, or a lost backend, the next `transaction` on the pool committed a new transaction id. The failed transaction was not committed. The next marker was visible.

The observation is a new backend and a new xid, not a reused aborted session. `throw_away!` is the 8.1.4 path that discards a connection whose transaction did not complete. The pass says the next unit did not run inside the failed transaction. It does not say a withheld `ROLLBACK` is a supported application technique.

## TX-05

`transaction(isolation: :serializable)` ran at `serializable`. `current_setting('transaction_isolation')` was read in the same statement as `pg_current_xact_id()` and `pg_backend_pid()`. The runner saw an `SIReadLock` on `item`. PASS.

There is no documented call that returns a handle for a later `commit`. `TransactionManager` is `:nodoc:`. `TX-05.explicit-serializable` is capability-absent.

## Migrations

`ActiveRecord::MigrationContext` on files under a temporary directory. PostgreSQL runs the migration and the `schema_migrations` write in one transaction. `Migrator#with_advisory_lock` calls `PostgreSQLAdapter#get_advisory_lock`, which is `pg_try_advisory_lock`, not a blocking `pg_advisory_lock`. A process that does not get the lock raises `ActiveRecord::ConcurrentMigrationError`.

On `MG-02.held`, three times: A reported `applied` and waited on the runner's gate; B reported `failed` with `ConcurrentMigrationError` and did not reach the gate; C reported `nothing_to_do` because `schema_migrations` already had the version. Marker count 1, history count 1, only A inside the migration. PASS. The lock prevents a second process from applying the migration. It does not wait. The second process fails, which the case allows.

`MG-02.session-loss`, and version 1.0 of `MG-02.first-deployment`, pass on the same shape: one apply, and a loser that either fails the try-lock or finds the version already recorded. Session loss aborts A's open transaction because the gate wait is inside it. The marker is not left behind for a second apply to duplicate.

Version 1.1 of `MG-02.first-deployment` holds an uncommitted creation of `schema_migrations` until both runners wait on it. In [`reports/examples/2026-10-24T14-38-34Z-142777`](../../reports/examples/2026-10-24T14-38-34Z-142777/summary.md), in each repetition one runner applied and the other failed. In the repetition the case file records in full, both runners were waiting on a lock at the release, and the error is `ActiveRecord::RecordNotUnique` (`23505` on `pg_type_typname_nsp_index`), not `ConcurrentMigrationError`. Marker count 1. PASS.

`MG-02.idle-session-timeout` is INCONCLUSIVE on MG-02.4. No session of A ended. The migration session was inside a transaction waiting on the gate, so `idle_session_timeout` did not end it, and the pool had not opened an idle extra connection. Marker count stayed 1. The same inconclusive shape is recorded for Lucid when the session inside the migration is not idle.

`MG-03.valid-reversal` deletes the marker and the history row in the reversal's transaction. `MG-03.no-reversal` raises `ActiveRecord::IrreversibleMigration` and reports `refused`; the marker and the history row remain. `MG-03.failing-reversal` raises after the delete, the transaction rolls back, and both the marker and the history row remain. All three pass. A successful `migrate` return is not treated as proof of a schema change: the adapter reads `schema_migrations` and reports `nothing_to_do` when the version is already there, and the runner counts rows itself.

## Callbacks and in-memory state

The probe is `adapters/activerecord/probes/tx01a-followups.json`. It is one database, not three harness repetitions. It uses the same Ruby, Active Record, pg, and PostgreSQL versions.

Caught `RecordNotUnique` inside `transaction`, then a normal return:

- `transaction` returned.
- `COMMIT` was answered with command tag `ROLLBACK`.
- The independent connection did not see the row.
- `after_commit` ran for that record (`name` `caught`, `id` 3). `after_rollback` did not.
- The in-memory object had `persisted?` true, `id` 3, `previously_new_record?` true, `destroyed?` false.
- `reload` raised `ActiveRecord::RecordNotFound`.
- A later `save!` issued `UPDATE "item" SET "name" = $1 WHERE "item"."id" = $2`, then `COMMIT` with command tag `COMMIT`, and returned. The independent connection still did not see the row. The update matched zero rows. `save!` does not require a row count.

The documented restart did the opposite: `ROLLBACK` with command tag `ROLLBACK`, `after_rollback` for the failed record, `after_commit` only for the restarted insert, and that row was visible.

`transaction(requires_new: true)` plus `ActiveRecord::Rollback` in the inner block: `after_rollback` for the inner name, `after_commit` for the outer name, inner row absent, outer row present. That matches the savepoint contract. Callback execution is not wrong merely because a nested block raised `ActiveRecord::Rollback`.

The callback page says `after_commit` runs when the database is in a permanent state. The transaction page says not to rescue `StatementInvalid` inside the block. This probe is that rescue. The callback ran for a record PostgreSQL did not commit. The pages do not say, in the callback section, that the warning withdraws the permanence sentence. A reader can treat that as a documentation gap. It is not, by itself, a reason to file a defect against the rescue the guide already forbids. The supported restart and the supported savepoint rollback both matched the database.

This stays out of the scored cases. The catalog already lists after-commit callbacks as planned and not included. A useful future case is the one this probe ran: a valid write, a rescued unique violation, a normal return, then `after_commit` against an independent read. It should stay separate from TX-01A so a framework that documents the rescue as misuse is not scored as if the rescue were the supported contract.

## Comparison

The other frameworks were not re-run in this session. The sentences below are the recorded runs cited in the root README.

| Question | Active Record 8.1.4 | What the cited runs show |
| --- | --- | --- |
| Caught statement error, then the block returns | `transaction` returns. `COMMIT` is sent and answered `ROLLBACK`. PPCS FAIL, mechanism exercised. The guide says not to rescue `StatementInvalid` here. | Django's `atomic()` rolls back, so `COMMIT` is not the ending statement, and TX-01A passes with the mechanism not exercised. SQLAlchemy Core fails with the mechanism exercised. The SQLAlchemy ORM run is INCONCLUSIVE because flush rolls back before `before-end`. Hibernate's `commit()` returns after Hibernate has sent `ROLLBACK` rather than `COMMIT`. Laravel's `transaction()` returns and `PDO::commit()` is true; pdo_pgsql does not expose the command tag. Prisma and Drizzle fail with the mechanism exercised. |
| The driver can show the tag | pg 1.7.0 `cmd_status` is `ROLLBACK` while `result_status` is `PGRES_COMMAND_OK` and `transaction_status` is idle. Active Record's commit path, as read in 8.1.4, does not consult `cmd_status`. | PDO, as recorded for Laravel, does not expose `PQcmdStatus`. node-postgres exposes the command tag, and several Node adapters still report success. |
| Aborted transaction recognized | Not on this return path. The block returns. A later statement on a new transaction can `COMMIT` an `UPDATE` of the phantom id and affect no row. | Django's recorded TX-01A ending is a rollback, so the application does not see a successful return of the failed `atomic()` block. |
| Connection after a failed rollback | The next pooled unit runs on a new xid and commits. TX-03 passes. The trace's new backend fits `throw_away!`. | Laravel fails the client-side TX-03 cases: the next unit can join the failed transaction, or fail with `25P02`. Prisma fails them too. Hibernate's pooled TX-03 passes because the pool closes the connection. |
| Nested transactions | `requires_new: true` is a savepoint. Both scored savepoint cases pass. There is no independent inner transaction. | Lucid, MikroORM, TypeORM, Prisma, Drizzle, and Laravel also implement nesting as savepoints. Spring's declarative `REQUIRES_NEW` is a separate transaction and is a different API. |
| Unsafe pattern documented | Yes. The transaction guide warns against rescuing `StatementInvalid` inside the block and tells the caller to restart. | Django documents that a database error inside `atomic()` requires the block to exit. A framework that documents the limitation is not, on that point, in worse standing than one that returns success with no warning. |
| Callbacks match the commit | On the warned path, `after_commit` ran for a row that was not committed. On the documented restart, `after_rollback` ran and `after_commit` did not. On `ActiveRecord::Rollback` inside `requires_new: true`, the callbacks matched the savepoint. | TypeORM's recorded TX-01A runs `after_commit` on the `ROLLBACK` tag. That comparison is the scored hook in those runs. Active Record's hook result is the separate probe, not a PPCS row. |

## Follow-ups, not filings

Do not file a Rails issue that says `transaction` committed an aborted transaction. The scored path is the rescue the guide rejects, and the restart outside the block works.

A documentation question is narrower and still not filed: the callback page's permanence sentence does not mention the statement-error warning, and this probe's `after_commit` ran when PostgreSQL had not committed. That would be a docs clarification, reproduced with the probe, not with a category C fault. Category C is why TX-02 fails here, and it is the wrong basis for an upstream report.

No second pgjdbc issue, and no repeat of the Knex issue. This repository's upstream tracker is unchanged.
