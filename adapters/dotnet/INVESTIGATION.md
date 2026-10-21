# EF Core, Npgsql, and the commit report

The question for this adapter pair: does Entity Framework Core preserve the distinction between a successful API return and a successful PostgreSQL commit, and which part of that behavior is EF Core and which part is Npgsql?

The scored run is [`reports/examples/2026-10-21T20-00-07Z-cff349`](../../reports/examples/2026-10-21T20-00-07Z-cff349/summary.md). PostgreSQL 18.6, EF Core 10.0.13, Npgsql EF Core provider 10.0.3, Npgsql 10.0.3, .NET runtime 10.0.13. Three repetitions agreed. CTL-01 and `pg-control` held. Observations below are from that run or from the probe programs in the adapter directories. Comparisons with other frameworks are from earlier recorded runs in this repository. Those runs were not repeated in this session.

## What Npgsql does

`CommitAsync` returns after a caught unique violation. The probe printed `aborted_commit=returned`, `aborted_fate=aborted`, `aborted_marker_visible=0`. `SELECT 1` in that session fails with `25P02`. A clean `CommitAsync` returns and the fate is `committed`. There is no public property for the driver's transaction status, and the command tag is not on the return value.

On the scored `TX-01A` row, the correct control reports `rolled_back` from the `25P02` and still sends `COMMIT`. The runner recorded the session idle with last statement `COMMIT`. The unsafe control reports `committed` because `CommitAsync` returned. The marker is absent. That FAIL is the same shape as `pg-control` unsafe, which ignores a command tag the driver did expose. Npgsql does not expose the tag, so the correct control cannot read it. The probe is application policy on top of the driver.

## What EF Core adds

`IDbContextTransaction.CommitAsync` returns when Npgsql's `CommitAsync` returns. In `execute-sql`, the duplicate is an ordinary `ExecuteSql` and the transaction aborts. `CommitAsync` returns, the commit interceptor runs once, the rollback interceptor does not, and PostgreSQL aborted the transaction. The API result is `committed`. The FAIL is EF reporting the driver's return, not an extra EF commit decision. The backend was already gone at `after-end`, so this row does not record the last statement. The Npgsql control is the row that does.

`SaveChangesAsync` inside an open transaction does not take that path. The probe's savepoint callbacks fired (3 created, 2 rolled back). The session stayed queryable, the earlier marker committed, and the failed entity stayed `Added`. A following `SaveChanges` failed again with `23505`. The harness `TX-01A` native row is INCONCLUSIVE because the transaction was not aborted before the end, and the marker committed. That is the case's precondition, not a pass and not a fail of TX-01A.1.

The change tracker does not match the database after that failure. The database no longer has the failed insert. The tracker still has the entity as `Added`.

EF's supported nested operation is a savepoint. TX-04 PASS: a failed savepoint does not keep its writes, and a released savepoint's writes roll back with the outer transaction. When the savepoint rollback itself fails and the application still calls `CommitAsync`, TX-02 FAIL. The withheld rollback left the inner write in the transaction and both markers committed. The rejected rollback aborted the transaction, and `CommitAsync` still returned as success. EF did not turn that failure into an outer rollback.

`BeginTransactionAsync(IsolationLevel.Serializable)` ran at `serializable` (TX-05 PASS). There is no managed callback that takes an isolation level.

## Migrations

`Database.MigrateAsync` passed the migration cases in this run, including two runners started together (`MG-02.first-deployment`: one `applied`, one `nothing_to_do`, marker count 1, history count 1). The adapter does not take its own advisory lock. The report of who applied is EF's `Applying migration` log, not a history-count difference. An earlier count-based report made both runners look applied. That was the adapter's measurement, and it is not the result in this run.

## Where the other recorded adapters sit

These are earlier recordings, not this run.

- `pg-control` correct reads the `COMMIT` command tag. Its unsafe mode ignores the tag and FAILs TX-01A. Npgsql's unsafe mode FAILs the same way without a tag to ignore: the return value is the only signal.
- JDBC control correct uses `PgConnection.getTransactionState()` before `commit()`. Npgsql has no equivalent public read. The `25P02` probe is the substitute, and it is a statement, not driver state.
- The repository's Hibernate recording FAILs TX-01A because `commit()` returned after Hibernate had sent `ROLLBACK` and had not sent `COMMIT`. That is a different ending from EF's `ExecuteSql` row, where `CommitAsync` does return from Npgsql's commit round trip.
- Spring JDBC and SQLAlchemy Core, in the repository's matrix, FAIL TX-01A with a reported commit and an aborted transaction. EF's `execute-sql` row is that shape. EF's `SaveChanges` row is not: the savepoint kept the transaction open and the commit was a real commit of the earlier write.

## What this does not recommend

This repository does not file an upstream issue from this run. Npgsql's public `CommitAsync` completes the protocol exchange and does not document a command tag. EF's `CommitAsync` completes that call. Whether either should surface a `ROLLBACK` tag is a contract question for those projects. The observation is enough to ask it. It is not, here, a filed defect.

## Follow-ups

- A reply lost after `COMMIT` has executed. `CommitAsync` consumes the reply. Category D is NOT_RUN. A protocol-level proxy would be a different experiment.
- A public Npgsql read of the command tag or of the failed-transaction state, so a correct policy would not need `SELECT 1`.
- Whether the change-tracker result after a failed `SaveChanges` (entity left `Added`) belongs in a cross-framework case. This run leaves it as a probe.
- `NoResetOnClose` reused the same backend and did not reuse the failed transaction id. That is one pool setting, not every pooler.
