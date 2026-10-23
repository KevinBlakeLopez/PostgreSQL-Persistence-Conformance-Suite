# Draft: Prisma, comment on prisma/orm#20496

Posted 2026-10-23 as `KevinBlakeLopez`: https://github.com/prisma/orm/issues/20496#issuecomment-6372520392 The posted body matches the comment below.

This is tracker item PI1. It is a comment on https://github.com/prisma/orm/issues/20496, not a new issue. `prisma/prisma` redirects to `prisma/orm`.

**#20496 already reports this behaviour.**

- **Status.** Open since 2023-08-02. Labels: `bug/1-unconfirmed`, `kind/bug`, `topic: $transaction`, `topic: interactiveTransactions`. Reported on Prisma 5.1.0, with the Rust query engine.
- **What it reports.** On PostgreSQL, an interactive transaction catches a unique-constraint error from `tx.user.create()` and returns. Prisma logs `COMMIT`, `$transaction` completes, and the row created before the error is gone.
- **The thread.** A contributor answered that PostgreSQL aborts the transaction, so "this is not something `Prisma` controls". The reporter asked Prisma to throw "to avoid the illusion that the transaction succeeded". A second contributor asked "Isn't that what is happening?" The reporter answered that the transaction completes silently and the log shows `COMMIT`. There has been no reply since 2023-08-07.

**What the comment adds:**

- the same loss on Prisma 7.10.1 with `@prisma/adapter-pg`, the client without the Rust engine;
- the answer to the thread's open question: PostgreSQL answers that `COMMIT` with the command tag `ROLLBACK`, so the client can tell;
- the three places in 7.10.1 that let the tag go unread.

Everything between the two rules below is the proposed comment. The rest of this file is internal.

**Before posting:**

1. Check that #20496 is still open. Read any new comments.
2. Search `prisma/orm` again for a newer report of the same behaviour (see the 2026-10-23 search below).
3. Check the current 7.x release. On 2026-10-23 the latest stable release was 7.10.1 (2026-10-19), and the `v7` branch head was its tag commit `97ea359`. If a newer release exists, re-check the four linked lines.
4. Comment only. A callback that catches an error and returns resolves today, and reporting the rollback would make that call reject. No pull request until the maintainers agree on that change.
5. The comment is the command tag only. It leaves out a failed `ROLLBACK` returned through `client.release()` with no error, and an outer callback that catches a failed savepoint rollback and then commits.
6. Posted 2026-10-23, after checks 1 to 3. #20496 was still open with 5 comments. The `v7` head was still `97ea359`. npm `latest` was 7.10.1 for `@prisma/client` and `@prisma/adapter-pg`. A search of issues and pull requests created since 2026-10-22 found no newer report.

**Duplicate search (2026-10-23), not exhaustive.** 24 queries over issues and pull requests in `prisma/orm`, open and closed. #20496 is the same symptom. The 2026-10-21 search looked for the command tag, which #20496 never mentions. No open pull request reads `result.command` (checked #30413, #30716, #30650, #29468, #29979, #29954). Nearby and different:

- #26366: a deferred exclusion constraint does not throw inside an interactive transaction.
- #29762: a statement can commit after a timeout rollback. Its fix, #30650, is open.
- #7786 (closed): a unique-constraint error inside a transaction was not parsed.
- #30374, with fix #30413: after a database error inside an interactive transaction, later queries on the same client receive other queries' responses.
- #30580, with fix #30716: a write conflict raised at `COMMIT` surfaces as a bare `DriverAdapterError` instead of P2034.
- #28810: deferred trigger errors outside explicit transactions.
- #17303 (closed): a commit-time exception was ignored, on the Rust engine.
- #29138 (closed): `@prisma/adapter-planetscale` swallowed `COMMIT` errors.
- #30756: MySQL, a deadlock victim's transaction keeps running statements.

**Evidence.** PPCS run `2026-10-21T14-10-47Z-148b69`, case `TX-01A.caught-error-then-commit`, and [FINDINGS.md](../../../adapters/prisma/FINDINGS.md).

- **Command tag.** It is in the first repetition's record only. The other observations agreed on all three repetitions.
- **Not #20496's code.** The run used `$executeRaw`, not `tx.user.create()`. #20496's own reproduction was not re-run on 7.x, and the comment says so.
- **Source lines.** The linked lines are at tag `7.10.1` (commit `97ea359`). They match the installed 7.10.1 bundles the run loaded.

---

I see the same loss on Prisma 7.10.1 with `@prisma/adapter-pg` 7.10.1 (pg 8.23.1, Node.js 24.14.1, PostgreSQL 18.6).

On whether Prisma can tell: PostgreSQL does abort the transaction at the failed statement, as noted above, but it also reports that outcome to the client. When the transaction is already aborted, PostgreSQL answers `COMMIT` with the command tag `ROLLBACK` rather than an error. node-postgres exposes that tag as `Result.command`, and in my run it was `ROLLBACK` for this `COMMIT`.

In 7.10.1 that tag is never read:

1. When the callback returns, `_transactionWithCallback` calls `this._engine.transaction('commit', …)` ([getPrismaClient.ts#L870](https://github.com/prisma/orm/blob/97ea359250335c1a174504c9b2b7e5fe030ab937/packages/client/src/runtime/getPrismaClient.ts#L870)).
2. `@prisma/adapter-pg` sets `usePhantomQuery: false` ([pg.ts#L210](https://github.com/prisma/orm/blob/97ea359250335c1a174504c9b2b7e5fe030ab937/packages/adapter-pg/src/pg.ts#L210)). The transaction manager therefore sends `COMMIT` through the adapter's `executeRaw`, and calls `transaction.commit()` if that promise resolves ([transaction-manager.ts#L536-L543](https://github.com/prisma/orm/blob/97ea359250335c1a174504c9b2b7e5fe030ab937/packages/client-engine-runtime/src/transaction-manager/transaction-manager.ts#L536-L543)).
3. `PgQueryable.executeRaw` returns `rowCount` and does not read `result.command` ([pg.ts#L88-L94](https://github.com/prisma/orm/blob/97ea359250335c1a174504c9b2b7e5fe030ab937/packages/adapter-pg/src/pg.ts#L88-L94)).

So `$transaction()` resolves, and the write made before the error is not in the database.

<details>
<summary>Reproduction and observations</summary>

`uniq.code` is unique, and `code = 'taken'` is already committed. `prisma` is a `PrismaClient` created with `new PrismaPg(pool)` around a `pg.Pool`.

```js
await prisma.$transaction(async (tx) => {
  await tx.$executeRaw`insert into item (name) values ('kept')`
  try {
    await tx.$executeRaw`insert into uniq (code) values ('taken')`
  } catch (error) {
    // P2010 (SQLSTATE 23505), caught inside the callback
  }
})
```

This has the same shape as the code I ran, but it is not that code. Mine passed the first value as a parameter, and read `pg_current_xact_id()` with `tx.$queryRaw` before the duplicate insert. It uses `$executeRaw`, not `tx.user.create()` as in the original report. I have not re-run that exact reproduction on 7.x.

I ran it three times, each time on a fresh database. Each time `$transaction()` resolved, `pg_xact_status()` for the transaction was `aborted`, and another connection did not see the first row. On the first run, the reply to `COMMIT` was the command tag `ROLLBACK`, and after the call returned the session was idle with `COMMIT` as its last statement.

</details>

I'd expect `$transaction()` to reject when `COMMIT` is answered with `ROLLBACK`, so that the caller does not treat the write as committed. That would change the result for callbacks that catch an error and return: they resolve today and would reject. That is why I haven't opened a pull request.

---
