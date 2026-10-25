<?php

/**
 * Laravel runs an afterCommit callback for a transaction that PostgreSQL rolled back.
 *
 * Inside DB::transaction(), a unique violation aborts the PostgreSQL transaction, and the closure
 * catches the exception and returns. Laravel commits. PostgreSQL rolls the transaction back and answers
 * COMMIT with the command tag ROLLBACK, PDO::commit() returns true (see ../pdo-commit-rollback.php), and
 * Laravel runs the afterCommit callback. A second connection shows the row was not committed.
 *
 *   composer install
 *   PGHOST=127.0.0.1 PGPORT=5432 PGDATABASE=postgres PGUSER=postgres PGPASSWORD=secret php repro.php
 *
 * Uses illuminate/database through Capsule. A Laravel application's DatabaseServiceProvider binds
 * db.transactions, the manager that keeps afterCommit callbacks. Capsule does not, so the binding is
 * made here. Creates and drops the table laravel_after_commit.
 */

require __DIR__.'/vendor/autoload.php';

use Illuminate\Container\Container;
use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseTransactionsManager;
use Illuminate\Database\UniqueConstraintViolationException;

$capsule = new Capsule(new Container());
$capsule->getContainer()->singleton('db.transactions', fn () => new DatabaseTransactionsManager());
$capsule->addConnection([
    'driver' => 'pgsql',
    'host' => getenv('PGHOST'),
    'port' => getenv('PGPORT') ?: 5432,
    'database' => getenv('PGDATABASE'),
    'username' => getenv('PGUSER'),
    'password' => getenv('PGPASSWORD'),
]);
$db = $capsule->getConnection();
$observer = new PDO('pgsql:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);

$db->statement('DROP TABLE IF EXISTS laravel_after_commit');
$db->statement('CREATE TABLE laravel_after_commit (id int PRIMARY KEY)');
$db->table('laravel_after_commit')->insert(['id' => 1]);

foreach (['healthy' => 2, 'aborted' => 3] as $label => $id) {
    $db->transaction(function (Connection $db) use ($label, $id): void {
        $db->afterCommit(fn () => print "$label: afterCommit ran\n");
        $db->afterRollBack(fn () => print "$label: afterRollBack ran\n");
        $db->table('laravel_after_commit')->insert(['id' => $id]);
        if ($label === 'aborted') {
            try {
                $db->table('laravel_after_commit')->insert(['id' => 1]);
            } catch (UniqueConstraintViolationException $e) {
                print "$label: caught SQLSTATE {$e->errorInfo[0]}\n";
            }
        }
    });
    $visible = $observer->query("SELECT count(*) FROM laravel_after_commit WHERE id = $id")->fetchColumn();
    print "$label: DB::transaction() returned, row $id visible to another connection: $visible\n";
}

$db->statement('DROP TABLE laravel_after_commit');
print 'PHP '.PHP_VERSION.', pdo_pgsql '.phpversion('pdo_pgsql').', illuminate/database '
    .Composer\InstalledVersions::getPrettyVersion('illuminate/database')."\n";
