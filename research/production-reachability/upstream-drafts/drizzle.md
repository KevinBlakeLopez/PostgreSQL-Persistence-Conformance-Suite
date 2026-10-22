# Draft: Drizzle

**Filed 2026-10-22** as https://github.com/drizzle-team/drizzle-orm/issues/6572 Posted as `KevinBlakeLopez`. No pull request.

Suggested title: `db.transaction()` resolves when PostgreSQL answers `COMMIT` with `ROLLBACK`

Suggested repo: [drizzle-team/drizzle-orm](https://github.com/drizzle-team/drizzle-orm/issues/new)

**Before posting:**

- Issue only. A callback that catches an error and returns resolves today, and reporting the rollback would make that call reject. Do not open a pull request until the maintainers agree.
- This draft is the command tag only. It does not include a failed `ROLLBACK` returned to the pool, a `BEGIN` that throws before `release()`, or the process exit on a checked-out client's `'error'` event. Those are separate.
- **Duplicate search (2026-10-22).** `ROLLBACK commit` and `unique violation transaction` returned nothing. Nearby and different: #6083 (a transaction handle still accepts queries after the transaction has ended), #1723 (open; rollback on drizzle-orm 0.29.2), #1450 (closed; whether an exception rolls the callback back), and #6341 / #6241 / #6114 (closed; `BEGIN` fails and the pool client leaks). Search again in the minutes before posting.
- Versions below are the ones that were run. On 2026-10-22, npm `latest` was still 0.45.4, published 2026-10-08. The `rc` tag was 1.0.0-rc.5, published 2026-10-21. The caught-commit case was run on 1.0.0-rc.5 the same day: `reports/examples/2026-10-22T13-28-31Z-671f3e`.

## Body

### What happened

On PostgreSQL, a statement error aborts the current transaction. If the application catches that error and the Drizzle callback then returns, `COMMIT` completes without an error. The earlier writes are gone.

Drizzle treats that `COMMIT` as success. `db.transaction()` resolves with the callback's value.

`NodePgSession.transaction` sends `COMMIT` and returns that value. It does not read the `pg` `Result`, including `command`. In 0.45.4 that function is `node-postgres/session.js` lines 180–194. In 1.0.0-rc.5 it is lines 52–86. Both await `commit` and return the callback value. In 1.0.0-rc.5 a failed `BEGIN` releases the client before the callback runs. That is not this case. In 0.45.4 `session.execute` returns the full `pg` `Result` when the statement has no fields and no custom result mapper. In 1.0.0-rc.5 `session.execute` asks for mode `"raw"` (`pg-core/async/session.js` line 106), and that mode returns the full result (`node-postgres/session.js` line 48). `transaction()` still ignores it.

On the first of the three runs of each version, instrumentation around node-postgres logged `Result.command` `ROLLBACK` for that `COMMIT`. Drizzle did not read that field.

### Versions

- Drizzle ORM 0.45.4 and 1.0.0-rc.5, `drizzle-orm/node-postgres`
- pg 8.23.1, pg-pool 3.14.0
- Node.js 24.14.1
- PostgreSQL 18.6

The two versions did the same thing on this case. 1.0.0-rc.5 is called as `drizzle({ client: pool })`. 0.45.4 is called as `drizzle(pool)`.

### Reproduction

`uniq.code` is unique, and the row `code = 'taken'` is already committed.

```js
await db.transaction(async (tx) => {
  await tx.insert(item).values({ name: 'kept' })
  try {
    await tx.insert(uniq).values({ code: 'taken' })
  } catch (error) {
    // 23505. Caught inside the callback.
  }
})
```

The sequence was run three times on 0.45.4 and three times on 1.0.0-rc.5. Each time `db.transaction()` resolved, `pg_xact_status()` was `aborted`, and another connection did not see the `kept` row. Each time, before the call returned, the session was aborted, and afterward it was out of a transaction with `commit` as the last statement. The saved session text `idle`, and the reply to `commit`, are from the first of those three runs on each version. That reply was command tag `ROLLBACK`.

### Expected

`db.transaction()` should reject when the reply to `COMMIT` is command tag `ROLLBACK`, which the first of the three runs logged on each version. The insert should not be reported as committed.

A callback that catches the error and returns resolves today. Reporting this rollback would make that call reject. I have not opened a pull request.

### Actual

The call resolves, and the insert is not visible. The connection is not left aborted.
