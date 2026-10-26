# Draft: Procrastinate issue, ignoring `AlreadyEnqueued` inside a transaction

**Not posted.** Prepared 2026-10-26. Written by: Claude Opus 5.5 (max).

This is the proposed upstream action for tracker item PY-25 in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). It reports [CHK-16](../chk-16-procrastinate-queueing-lock/README.md) to procrastinate-org/procrastinate as a new issue, and offers a docs PR.

The title and everything between the two rules below are the proposed issue. The rest of this file is internal.

**Destination.** A new issue, not a PR: the repository's PR template begins with `Closes #<ticket number>`.

**Before posting:**

1. Get approval of the exact text and of the destination (`AGENTS.md` rule 9).
2. Re-run the duplicate search below, and re-read #1446 and #1512.
3. Check that the CHK-16 link resolves on `main` (it needs the push).
4. Re-check that Procrastinate 3.10.0 is still the latest release, and that the two docs pages still read as quoted.
5. Run the content guard on the final text.

**Checks done 2026-10-26 (UTC):**

- **Duplicates.** No issue reports this. Searched for: `savepoint`, `AlreadyEnqueued transaction`, `queueing lock transaction aborted`, `current transaction is aborted`, `atomic queueing_lock`.
- **Related, and cited in the body:**
  - #1446 (open), the loud form in `retry_stalled_jobs`;
  - #1508 (merged), which added the external-connection page and its savepoint caveat.
- **Related, not cited:** #1512 (an open PR), whose Django admin retry already uses `with suppress(AlreadyEnqueued), transaction.atomic():`.
- **Contribution rules.** `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `.github/` have no AI policy. The code of conduct is standard.
- **The docs, as quoted:** `docs/howto/advanced/queueing_locks.md`, line 18, and `docs/howto/production/external_connection.md`, line 110, both at 3.10.0.

**Deliberately left out:**

- **The real-world code search** (in CHK-16's README). The projects in it already guard against this.
- **Django's ORM path (CHK-12)**, and the psycopg details beyond one sentence: the abort is what Procrastinate's docs can prevent.
- **A change to the library:** an ignore mode using `ON CONFLICT DO NOTHING`, or a savepoint inside `defer()`. That's for the maintainers to raise if they want it.

**Length.** The title plus 12 non-blank lines of body, the code block included: 218 words.

---

**Title:** Ignoring `AlreadyEnqueued` inside a transaction loses the transaction

The queueing-lock page says `AlreadyEnqueued` is an exception "which you can choose to ignore". If the job is deferred inside the caller's transaction, ignoring it loses that transaction, and nothing reports it. With the Django integration this is the default, since `defer()` runs on Django's connection inside the current `atomic()` block. It also happens with `configure(connection=...)`.

```python
with transaction.atomic():
    order = Order.objects.create(customer_id=customer_id)
    try:
        recompute_stats.configure(queueing_lock=f"stats-{customer_id}").defer(customer_id=customer_id)
    except AlreadyEnqueued:
        pass
```

On a repeat order, the job insert fails on `procrastinate_jobs_queueing_lock_idx_v1`, and PostgreSQL aborts the transaction. Django still sends `COMMIT`, and PostgreSQL answers it with `ROLLBACK`. psycopg's `commit()` returns normally (psycopg#1453), and Django runs the `on_commit` callbacks. The order is gone, with no error. The same happens with `configure(connection=conn)` followed by `conn.commit()`. If anything runs after the ignored exception, it fails with "current transaction is aborted" instead, as in #1446. A savepoint around the `defer()` (a nested `transaction.atomic()`, or `conn.transaction()`) keeps the order.

Procrastinate 3.10.0, Django 6.1.2, psycopg 3.3.6, PostgreSQL 18.6, three runs, all the same: https://github.com/KevinBlakeLopez/PostgreSQL-Persistence-Conformance-Suite/tree/main/research/python-upstream-contribution/chk-16-procrastinate-queueing-lock

The external-connection page (#1508) already says that insert errors "may abort your transaction. Use savepoints if you need to isolate the defer". Would you take a docs PR that adds the same caveat, with the savepoint example, to the queueing-lock page and the Django page?

---
