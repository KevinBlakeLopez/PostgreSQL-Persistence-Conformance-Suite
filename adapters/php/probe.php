<?php

declare(strict_types=1);

/**
 * Observations that are not PPCS cases.
 *
 * Usage: php probe.php path-to-ppcs-instance.json
 *
 * Refuses a server whose cluster_name is not that file's token.
 * Creates ppcs_php_probe and drops it. Prints key=value lines.
 * Does not print the password.
 */

require __DIR__.'/vendor/autoload.php';

use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\DatabaseTransactionsManager;
use Ppcs\Item;
use Ppcs\Uniq;

if (PHP_VERSION !== '8.5.6') {
    fwrite(STDERR, 'probe requires PHP 8.5.6; this runtime is '.PHP_VERSION."\n");
    exit(2);
}
if ($argc !== 2) {
    fwrite(STDERR, "usage: php probe.php path-to-ppcs-instance.json\n");
    exit(2);
}

$instance = json_decode((string) file_get_contents($argv[1]), true);
if (!is_array($instance)) {
    fwrite(STDERR, "instance file is not JSON\n");
    exit(2);
}

$dsnAdmin = sprintf('pgsql:host=%s;port=%d;dbname=postgres', $instance['host'], (int) $instance['port']);
$admin = new PDO($dsnAdmin, $instance['user'], $instance['password'], [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
]);
$token = (string) $admin->query('show cluster_name')->fetchColumn();
if ($token !== (string) $instance['token']) {
    fwrite(STDERR, "cluster_name does not match the instance token\n");
    exit(2);
}

$admin->exec('drop database if exists ppcs_php_probe');
$admin->exec('create database ppcs_php_probe');

$out = static function (string $key, mixed $value): void {
    if (is_bool($value)) {
        $value = $value ? 'true' : 'false';
    } elseif ($value === null) {
        $value = 'null';
    }
    echo $key.'='.$value."\n";
};

try {
    $out('php', PHP_VERSION);
    $out('pdo_pgsql', phpversion('pdo_pgsql'));
    $out('illuminate_database', \Composer\InstalledVersions::getPrettyVersion('illuminate/database'));

    $pdo = new PDO(sprintf('pgsql:host=%s;port=%d;dbname=ppcs_php_probe', $instance['host'], (int) $instance['port']), $instance['user'], $instance['password'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    ]);
    $out('libpq', (string) $pdo->getAttribute(PDO::ATTR_CLIENT_VERSION));
    $out('server', (string) $pdo->getAttribute(PDO::ATTR_SERVER_VERSION));
    $pdo->exec('create table item (id serial primary key, name text not null, qty int not null default 0)');
    $pdo->exec('create table uniq (id serial primary key, code text not null unique)');
    $pdo->exec("insert into uniq (code) values ('taken')");

    $pdo->beginTransaction();
    $pdo->exec("insert into item (name, qty) values ('pdo-marker', 0)");
    $caught = false;
    try {
        $pdo->exec("insert into uniq (code) values ('taken')");
    } catch (PDOException $e) {
        $caught = true;
        $out('pdo_violation_sqlstate', (string) ($e->errorInfo[0] ?? ''));
    }
    $out('pdo_violation_caught', $caught);
    $out('pdo_in_transaction_before_commit', $pdo->inTransaction());
    $commit = $pdo->commit();
    $info = $pdo->errorInfo();
    $out('pdo_commit_return', $commit);
    $out('pdo_commit_sqlstate', (string) ($info[0] ?? ''));
    $out('pdo_in_transaction_after_commit', $pdo->inTransaction());
    $visible = (int) $pdo->query("select count(*) from item where name = 'pdo-marker'")->fetchColumn();
    $out('pdo_marker_visible_after_commit_true', $visible);

    $pdo->beginTransaction();
    $stmt = $pdo->prepare('insert into item (name, qty) values (?, 0)');
    $stmt->execute(['pdo-prepared-marker']);
    try {
        $bad = $pdo->prepare('insert into uniq (code) values (?)');
        $bad->execute(['taken']);
    } catch (PDOException $e) {
        $out('pdo_prepared_violation_sqlstate', (string) ($e->errorInfo[0] ?? ''));
    }
    $preparedCommit = $pdo->commit();
    $preparedInfo = $pdo->errorInfo();
    $out('pdo_prepared_commit_return', $preparedCommit);
    $out('pdo_prepared_commit_sqlstate', (string) ($preparedInfo[0] ?? ''));
    $preparedVisible = (int) $pdo->query("select count(*) from item where name = 'pdo-prepared-marker'")->fetchColumn();
    $out('pdo_prepared_marker_visible', $preparedVisible);

    $methods = get_class_methods(Pdo\Pgsql::class);
    $tagMethods = array_values(array_filter($methods, static fn (string $m): bool => stripos($m, 'cmd') !== false || stripos($m, 'tag') !== false || stripos($m, 'status') !== false));
    $out('pdo_pgsql_methods_matching_cmd_tag_or_status', $tagMethods === [] ? 'none' : implode(',', $tagMethods));

    probeLaravel($instance, 'eloquent', static function (): void {
        Item::query()->create(['name' => 'eloquent-marker', 'qty' => 0]);
        try {
            Uniq::query()->create(['code' => 'taken']);
        } catch (Throwable $e) {
            echo 'eloquent_violation_class='.$e::class."\n";
            echo 'eloquent_violation_sqlstate='.($e->getCode() === 0 ? '' : $e->getCode())."\n";
        }
    });
    probeLaravel($instance, 'query_builder', static function ($connection): void {
        $connection->table('item')->insert(['name' => 'builder-marker', 'qty' => 0]);
        try {
            $connection->table('uniq')->insert(['code' => 'taken']);
        } catch (Throwable $e) {
            echo 'query_builder_violation_class='.$e::class."\n";
        }
    });
} finally {
    $admin->exec("select pg_terminate_backend(pid) from pg_stat_activity where datname = 'ppcs_php_probe' and pid <> pg_backend_pid()");
    $admin->exec('drop database if exists ppcs_php_probe');
}

/**
 * @param callable(Illuminate\Database\Connection): void $write
 */
function probeLaravel(array $instance, string $label, callable $write): void
{
    $capsule = new Capsule();
    $capsule->addConnection([
        'driver' => 'pgsql',
        'host' => (string) $instance['host'],
        'port' => (int) $instance['port'],
        'database' => 'ppcs_php_probe',
        'username' => (string) $instance['user'],
        'password' => (string) $instance['password'],
        'charset' => 'utf8',
        'prefix' => '',
        'schema' => 'public',
        'application_name' => 'ppcs-php-probe',
    ]);
    $capsule->setAsGlobal();
    $capsule->bootEloquent();
    $connection = $capsule->getConnection();
    $connection->setTransactionManager(new DatabaseTransactionsManager());
    $afterCommit = 0;
    $afterRollback = 0;
    $returned = false;
    $escaped = null;
    try {
        $connection->transaction(function ($tx) use ($write, &$afterCommit, &$afterRollback, $label): void {
            $tx->afterCommit(static function () use (&$afterCommit): void {
                $afterCommit++;
            });
            $tx->afterRollBack(static function () use (&$afterRollback): void {
                $afterRollback++;
            });
            $write($tx);
        });
        $returned = true;
    } catch (Throwable $e) {
        $escaped = $e::class;
    }
    $marker = $label === 'eloquent' ? 'eloquent-marker' : 'builder-marker';
    $visible = (int) $connection->table('item')->where('name', $marker)->count();
    echo $label.'_transaction_returned='.($returned ? 'true' : 'false')."\n";
    echo $label.'_escaped='.($escaped ?? 'null')."\n";
    echo $label.'_after_commit='.$afterCommit."\n";
    echo $label.'_after_rollback='.$afterRollback."\n";
    echo $label.'_marker_visible='.$visible."\n";
    $connection->disconnect();
}
