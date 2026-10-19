# MySQL / InnoDB case list

This list is the measured transaction outcomes from the phase 0 runs. It is the expectation a later MySQL adapter would be scored against.

It is not a PPCS catalog. `harness/lib/catalog.mjs` loads every `specifications/*.json` file and refuses a file whose `catalog` field is not `ppcs-specifications/1`. This file lives here, and its catalog field is `mysql-innodb-transactions/0`, so the PostgreSQL runner does not load it. `specifications/transactions.v1.json` is unchanged.

The structured list is [`transactions.v1.json`](transactions.v1.json). Each case cites the evidence file. Knex 3.3.0 and Lucid 22.4.2 were measured only where the evidence column says so.

A lost `COMMIT` reply is not in the list. That run was not done, so the list does not say what the client knew.

| Case | Expectation |
| --- | --- |
| `MX-01.duplicate-key-then-commit` | The duplicate key is `1062` / `23000`. The transaction stays open. `COMMIT` keeps the earlier marker. |
| `MX-02.deadlock-victim` | The victim's `1213` / `40001` means that transaction is already rolled back. A later `COMMIT` OK packet is not that commit. The subject has to be the lighter transaction. |
| `MX-03.lock-wait-statement-rollback` | Default `innodb_rollback_on_timeout=OFF`. Error `1205` / `HY000`. The earlier marker survives a later commit. |
| `MX-03.lock-wait-transaction-rollback` | Same error, with the server started `ON`. The earlier marker does not survive. |
| `MX-04.savepoint-rollback` | Rollback-to undoes the inner marker. Commit keeps the outer marker and writes made after the rollback. |
| `MX-04.savepoint-release` | Release does not commit. The outer commit keeps the inner marker. |
| `MX-04.released-then-outer-rollback` | The outer rollback removes a released savepoint's writes. |
| `MX-04.missing-savepoint` | `1305` / `42000`. The transaction stays usable. |
| `MX-05.commit-and-rollback-packet` | `COMMIT` and `ROLLBACK` are both OK packets, `serverStatus` `16386`, with no command tag. |
| `MX-05.connection-closed-before-commit` | `COMMIT` was not sent. The API must not report a commit. The marker is absent. |
| `MX-06.second-transaction-implicit-commit` | The next `BEGIN` or `START TRANSACTION` commits the open unit. The second unit's rollback does not remove it. |
| `MX-07.ddl-implicit-commit` | `CREATE TABLE` commits the preceding insert. `ROLLBACK` removes neither. |
| `MX-08.isolation-report` | The open transaction's performance schema isolation level is the level applied. `@@transaction_isolation` follows `SET SESSION`, not `SET TRANSACTION`. |
