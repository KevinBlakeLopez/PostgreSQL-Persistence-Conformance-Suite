# Standalone reproduction

`repro.php` shows the finding F1 in [../../findings.md](../../findings.md) with nothing but `illuminate/database` 13.38.0 and two PDO connections. It is not part of the study's runner and has no instrumentation.

## Run

```sh
composer install
DB_HOST=127.0.0.1 DB_PORT=3306 DB_DATABASE=test DB_USERNAME=root DB_PASSWORD=secret php repro.php
```

- **Server.** Use a MySQL 8 server with the default `innodb_rollback_on_timeout=OFF`.
- **Port.** `DB_PORT` has no default on purpose.
- **Tables.** The script drops and creates two tables, `repro_items` and `repro_locked`, in `DB_DATABASE`.
- **Lock holder.** A second PDO connection holds a row lock, and the subject sets `innodb_lock_wait_timeout = 1`, so the run takes about two seconds.

## What it does

The same outer and nested `DB::transaction()` code runs twice. The outer closure inserts `outer`. It calls a nested `DB::transaction()` that registers `afterCommit` and `afterRollBack` callbacks, inserts `inner`, and then fails. The outer closure catches the exception and inserts `after`. The failure in the two cases:

1. an update of the row the other connection has locked, which ends in errno 1205;
2. a duplicate key (1062).

A new connection then lists the committed rows.

## Recorded output

`output/off-r1.txt`, `off-r2.txt` and `off-r3.txt` are three runs against MySQL 8.4.11 with `innodb_rollback_on_timeout=OFF`. They are byte-identical. On 2026-10-25 their SHA-256 was `191715f6cf008eb2a995c66db6ce0230201ec6a175df11d69318b693d79f70ff`.

```text
1. inner statement waits for a row lock and fails with 1205
   inner DB::transaction() threw: Illuminate\Database\DeadlockException
   outer DB::transaction():       returned
   callbacks that ran:            inner afterRollBack
   rows committed:                outer, inner, after

2. inner statement fails with a duplicate key (1062)
   inner DB::transaction() threw: Illuminate\Database\UniqueConstraintViolationException
   outer DB::transaction():       returned
   callbacks that ran:            inner afterRollBack
   rows committed:                outer, after
```

`output/on-r1.txt` is one run against a server started with `--innodb-rollback-on-timeout=ON`. There the 1205 has already ended the whole transaction: `after` autocommits, the outer `commit()` throws "There is no active transaction", and the only row is `after`. Case 2 is unchanged.

The runs used the study's servers (`../../repro/scripts/mysql-up.sh`) and a schema created for them as root: `CREATE DATABASE mysd_upstream_repro; GRANT ALL PRIVILEGES ON mysd_upstream_repro.* TO 'mysd'@'%'`. The commands were:

```sh
DB_HOST=127.0.0.1 DB_PORT=13316 DB_DATABASE=mysd_upstream_repro DB_USERNAME=mysd DB_PASSWORD=<password from ../../repro/.mysd-instance.json> php repro.php > output/off-r1.txt
DB_HOST=127.0.0.1 DB_PORT=13317 DB_DATABASE=mysd_upstream_repro DB_USERNAME=mysd DB_PASSWORD=<same> php repro.php > output/on-r1.txt
```

`off-r2.txt` and `off-r3.txt` repeat the first command.
