# PHP adapters

Shared Composer project for the PDO control and the Laravel adapter. It is not itself an adapter: there is no `adapter.json` here. `pnpm run setup` does not install it.

## Versions

Recorded on PostgreSQL 18.6 (`postgres:18.6`, Debian 18.6-1.pgdg13+2) with:

| Piece | Version |
| --- | --- |
| PHP | 8.5.6 |
| pdo_pgsql | 8.5.6, bundled with that PHP |
| libpq | 18.3, the library this PHP was built against |
| illuminate/database | v13.38.0 |
| Composer | 2.8.11 when the lockfile was written |

`composer.lock` pins illuminate/database and the packages it requires. `laravel/framework` is not installed. There is no HTTP kernel, service provider boot, queue, or migration run in the scored adapters.

Capsule uses `Illuminate\Database\Connection` and `ManagesTransactions`, the same classes a Laravel application uses for these calls. It does not register `DatabaseServiceProvider`. That provider binds `db.transactions`. `DatabaseManager::configure` sets the transaction manager only when that binding exists. The scored runs leave it unset. `adapters/php/probe.php` sets `DatabaseTransactionsManager` itself. That probe is not a PPCS case.

## Install

From this directory, with PHP 8.5.6 and Composer:

```sh
composer install --no-interaction --no-scripts
```

The PDO control can run without that install. The Laravel adapter cannot: `adapters/laravel/main.php` loads `vendor/autoload.php`.

## Run

From the repository root, with the disposable server up:

```sh
node harness/run.mjs --adapter=pdo-control --repeat=3
node harness/run.mjs --adapter=laravel --repeat=3
node harness/run.mjs --adapter=pdo-control,laravel --case=TX-01A --repeat=3
node harness/run.mjs --adapter=laravel --case=TX-01A --mode=managed --repeat=3
```

`pg-control` runs beside the scenario cases. One case:

```sh
node harness/run.mjs --adapter=laravel --case=TX-01A.caught-error-then-commit --mode=explicit --repeat=1
```

The callback probe, against the disposable server only:

```sh
php adapters/php/probe.php .ppcs-instance.json
```

It checks `cluster_name`, creates `ppcs_php_probe`, and drops it.

## Call path

```text
application code
        |
        v
Eloquent Model::create          query builder insert
        |                               |
        +---------------+---------------+
                        v
        Illuminate\Database\Connection
        transaction()  or  beginTransaction/commit/rollBack
                        |
                        v
        Ppcs\FaultingPdo extends Pdo\Pgsql
        commit(), rollBack(), exec(), prepare()
                        |
                        v
        pdo_pgsql (C): PQexec. PQcmdStatus is discarded
                        |
                        v
        PostgreSQL
```

The PDO control starts at `FaultingPdo`. It does not load Eloquent or Illuminate.

PPCS reads directly: the checkpoint pid and xid, the isolation string on TX-05, the adapter's `reported` value, and the diagnostics (`PDO::commit()` return, `errorInfo()` SQLSTATE, `inTransaction()` before and after, fault trace). The runner's own connection reads fate (`pg_xact_status`), marker visibility, session state, and the backend's last query. The command tag is inferred only when that last query and the session state say `COMMIT` or `ROLLBACK`. The adapter does not receive the tag.

Category C faults are withheld or rewritten inside `FaultingPdo`, once, before Laravel or the PDO policy sees the error. Category B is the runner's `pg_terminate_backend`. Category D is not implemented: `pdo_pgsql` finishes `commit()` only after it has consumed the reply.

## Layout

| Path | Role |
| --- | --- |
| `src/FaultingPdo.php` | PDO subclass. Records `commit()`. Injects category C faults |
| `src/PdoControl.php` | Positive and negative PDO policies |
| `src/LaravelAdapter.php` | Capsule, Eloquent writes, managed and explicit transactions |
| `src/FaultingConnector.php` | Laravel's `PostgresConnector` with `FaultingPdo` |
| `probe.php` | Command-tag and callback observations. Not a case |
| `../pdo-control/` | Adapter manifest and entry point |
| `../laravel/` | Adapter manifest and entry point |
