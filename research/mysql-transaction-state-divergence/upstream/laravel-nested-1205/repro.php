<?php

declare(strict_types=1);

/**
 * A nested DB::transaction() that fails with MySQL errno 1205 (lock wait timeout) is not rolled back to its
 * savepoint. When the caller of the inner transaction catches the exception, the inner writes commit with
 * the outer transaction, after the inner afterRollBack callbacks have already run.
 *
 * Run against a MySQL 8 server with the default innodb_rollback_on_timeout=OFF:
 *
 *   composer install
 *   DB_HOST=127.0.0.1 DB_PORT=3306 DB_DATABASE=test DB_USERNAME=root DB_PASSWORD=secret php repro.php
 *
 * It drops and creates two tables, repro_items and repro_locked, in DB_DATABASE.
 * Case 1 is the lock wait timeout. Case 2 is the same code with a duplicate key as the inner failure.
 */

require __DIR__.'/vendor/autoload.php';

use Composer\InstalledVersions;
use Illuminate\Container\Container;
use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseTransactionsManager;

foreach (['DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_USERNAME'] as $name) {
    if ((string) getenv($name) === '') {
        fwrite(STDERR, "Set $name (DB_PORT has no default on purpose).\n");
        exit(2);
    }
}

$config = [
    'driver' => 'mysql',
    'host' => getenv('DB_HOST'),
    'port' => (int) getenv('DB_PORT'),
    'database' => getenv('DB_DATABASE'),
    'username' => getenv('DB_USERNAME'),
    'password' => (string) getenv('DB_PASSWORD'),
    'charset' => 'utf8mb4',
    'collation' => 'utf8mb4_unicode_ci',
];

function pdo(array $config): PDO
{
    return new PDO(
        "mysql:host={$config['host']};port={$config['port']};dbname={$config['database']};charset=utf8mb4",
        $config['username'],
        $config['password'],
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
    );
}

// The transactions manager is bound the way DatabaseServiceProvider binds it in an application, so
// afterCommit() and afterRollBack() work as they do there.
$capsule = new Capsule(new Container());
$capsule->getContainer()->singleton('db.transactions', fn () => new DatabaseTransactionsManager());
$capsule->addConnection($config);
$db = $capsule->getConnection();

$setup = pdo($config);
$setup->exec('DROP TABLE IF EXISTS repro_items, repro_locked');
$setup->exec('CREATE TABLE repro_items (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(32) NOT NULL UNIQUE) ENGINE=InnoDB');
$setup->exec('CREATE TABLE repro_locked (id INT PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB');
$setup->exec('INSERT INTO repro_locked (id, v) VALUES (1, 0)');

printf(
    "MySQL %s, innodb_rollback_on_timeout=%s, illuminate/database %s, PHP %s\n\n",
    $setup->query('SELECT VERSION()')->fetchColumn(),
    $setup->query('SELECT @@innodb_rollback_on_timeout')->fetchColumn(),
    InstalledVersions::getPrettyVersion('illuminate/database'),
    PHP_VERSION,
);

$db->unprepared('SET SESSION innodb_lock_wait_timeout = 1');

$cases = [
    '1. inner statement waits for a row lock and fails with 1205' => function (Connection $db): void {
        $db->update('UPDATE repro_locked SET v = v + 1 WHERE id = 1');
    },
    '2. inner statement fails with a duplicate key (1062)' => function (Connection $db): void {
        $db->table('repro_items')->insert(['name' => 'outer']);
    },
];

foreach ($cases as $title => $failingStatement) {
    $setup->exec('DELETE FROM repro_items');

    // Another session holds the row lock that case 1 waits for.
    $holder = pdo($config);
    $holder->beginTransaction();
    $holder->exec('UPDATE repro_locked SET v = v + 1 WHERE id = 1');

    $callbacks = [];
    $caught = null;
    try {
        $db->transaction(function (Connection $db) use ($failingStatement, &$callbacks, &$caught): void {
            $db->table('repro_items')->insert(['name' => 'outer']);

            try {
                $db->transaction(function (Connection $db) use ($failingStatement, &$callbacks): void {
                    $db->afterCommit(function () use (&$callbacks) { $callbacks[] = 'inner afterCommit'; });
                    $db->afterRollBack(function () use (&$callbacks) { $callbacks[] = 'inner afterRollBack'; });
                    $db->table('repro_items')->insert(['name' => 'inner']);
                    $failingStatement($db);
                });
            } catch (Throwable $e) {
                $caught = $e;
            }

            $db->table('repro_items')->insert(['name' => 'after']);
        });
        $outer = 'returned';
    } catch (Throwable $e) {
        // With innodb_rollback_on_timeout=ON the 1205 has already ended the whole transaction.
        $outer = 'threw '.$e::class.': '.strtok($e->getMessage(), "\n");
    } finally {
        $holder->rollBack();
    }

    // A new connection, opened after the outer transaction ended.
    $rows = pdo($config)->query('SELECT name FROM repro_items ORDER BY id')->fetchAll(PDO::FETCH_COLUMN);

    echo $title, "\n";
    echo '   inner DB::transaction() threw: ', $caught ? $caught::class : 'nothing', "\n";
    echo '   outer DB::transaction():       ', $outer, "\n";
    echo '   callbacks that ran:            ', $callbacks ? implode(', ', $callbacks) : 'none', "\n";
    echo '   rows committed:                ', $rows ? implode(', ', $rows) : 'none', "\n";
    echo '   transaction level afterwards:  ', $db->transactionLevel(), "\n\n";
}
