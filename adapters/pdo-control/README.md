# PDO PostgreSQL control

PHP 8.5.12 `Pdo\Pgsql`. No Laravel, no pool. `correct` is the positive control. `unsafe` is the negative control. `persistent` is the correct policy with `PDO::ATTR_PERSISTENT` true, for TX-03 only. The kinds are `native` and `configured`, not `control`, so this adapter is not a second case-control gate.

`correct` calls `PDO::rollBack()` after a caught statement error and does not call `PDO::commit()`. PDO exposes no transaction status and no command tag, so this is not the JDBC control's `getTransactionState()` check. `unsafe` reports committed when `PDO::commit()` returns true.

Install notes are in [`../php/README.md`](../php/README.md). The per-case report is [`FINDINGS.md`](FINDINGS.md). The recording is [`reports/examples/2026-10-21T16-24-17Z-231161`](../../reports/examples/2026-10-21T16-24-17Z-231161/summary.md), on PHP 8.5.6. [`reports/examples/2026-10-23T14-18-35Z-5a6ff7`](../../reports/examples/2026-10-23T14-18-35Z-5a6ff7/summary.md) re-ran every case on PHP 8.5.12, and every classification matched.

```sh
node harness/run.mjs --adapter=pdo-control --repeat=3
```

The PDO control's entry point does not load Illuminate. `composer install` in `adapters/php` is required for the Laravel adapter, not for this one.

TX-02, TX-04, and TX-05 are unsupported. PDO has no savepoint API and no isolation argument. `PDO::beginTransaction()` is the transaction API. `TX-01B.commit-reply-discarded` is not implemented. MG-02 and MG-03 are capability-absent.
