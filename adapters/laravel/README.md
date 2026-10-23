# Laravel adapter

illuminate/database v13.38.0 through `Illuminate\Database\Capsule\Manager`. PHP 8.5.6, pdo_pgsql 8.5.6, libpq 18.3. Writes are Eloquent `Item::query()->create` and `Uniq::query()->create`. There is no Laravel application.

`managed` calls `Connection::transaction(Closure)`. `explicit` calls `beginTransaction()`, `commit()`, and `rollBack()`. A nested call is a savepoint (`SAVEPOINT transN`, `ROLLBACK TO SAVEPOINT transN`). A nested `commit()` decrements Laravel's counter and does not send `RELEASE SAVEPOINT`. `persistent` is the managed API with `PDO::ATTR_PERSISTENT` true, and it runs TX-03 only.

Install and the call path are in [`../php/README.md`](../php/README.md). The per-case report is [`FINDINGS.md`](FINDINGS.md). The recording is [`reports/examples/2026-10-21T16-24-17Z-231161`](../../reports/examples/2026-10-21T16-24-17Z-231161/summary.md).

```sh
cd adapters/php && composer install --no-interaction --no-scripts
node harness/run.mjs --adapter=laravel --repeat=3
```

`TX-04.independent-inner` is unsupported, not applicable by design. `TX-01B.commit-reply-discarded` is not implemented. MG-02 and MG-03 call `Migrator::run()` and `Migrator::rollback()` on the managed mode. The recording is [`reports/examples/2026-10-23T13-03-36Z-03a5b5`](../../reports/examples/2026-10-23T13-03-36Z-03a5b5/summary.md), on PHP 8.5.12.
