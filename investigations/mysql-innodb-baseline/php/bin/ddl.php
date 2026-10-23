<?php

declare(strict_types=1);

/**
 * DDL inside a transaction. mysqli is the control. ci4-migration runs MigrationRunner.
 * Prints one JSON object, then waits for "go" before closing the subject connection.
 */

require dirname(__DIR__) . '/src/DdlBoot.php';

use CodeIgniter\Database\MigrationRunner;

$scenario = $argv[1] ?? '';

try {
    $payload = match ($scenario) {
        'mysqli' => mpcs_mysqli_ddl(),
        'ci4-migration' => mpcs_ci4_migration(),
        default => throw new InvalidArgumentException('Unknown scenario'),
    };
    $payload['versions'] = mpcs_versions();
    $payload['logs'] = mpcs_logs();
    $close = $payload['close'] ?? null;
    unset($payload['close']);
    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    fflush(STDOUT);
    while (($line = fgets(STDIN)) !== false) {
        if (trim($line) === 'go') {
            break;
        }
    }
    if (is_callable($close)) {
        $close();
    }
} catch (Throwable $error) {
    fwrite(STDOUT, json_encode([
        'failed' => true,
        'scenario' => $scenario,
        'class' => $error::class,
        'message' => $error->getMessage(),
        'file' => basename($error->getFile()),
        'line' => $error->getLine(),
        'logs' => function_exists('mpcs_logs') ? mpcs_logs() : [],
    ], JSON_THROW_ON_ERROR) . "\n");
    exit(1);
}

/**
 * @return array<string, mixed>
 */
function mpcs_mysqli_ddl(): array
{
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $db->set_charset('utf8mb4');
    $other = mpcs_other();
    $id = $db->thread_id;

    $db->begin_transaction();
    $db->query("INSERT INTO marker (name) VALUES ('ddl-marker')");
    $before = ['names' => mpcs_ddl_names($other), 'table' => mpcs_ddl_table($other, 'ddl_side')];
    $db->query('CREATE TABLE ddl_side (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB');
    $afterDdl = ['names' => mpcs_ddl_names($other), 'table' => mpcs_ddl_table($other, 'ddl_side')];
    $duplicate = mpcs_mysqli_duplicate($db);
    $rolled = $db->rollback();
    $afterRollback = ['names' => mpcs_ddl_names($other), 'table' => mpcs_ddl_table($other, 'ddl_side')];

    return [
        'scenario' => 'mysqli',
        'connection_id' => $id,
        'before_ddl' => $before,
        'after_ddl' => $afterDdl,
        'duplicate' => $duplicate,
        'rollback_returned' => $rolled === true,
        'after_rollback' => $afterRollback,
        'close' => static function () use ($db): void {
            $db->close();
        },
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_migration(): array
{
    $db = new CodeIgniter\Database\MySQLi\Connection([
        'DSN' => '',
        'hostname' => mpcs_env('MPCS_HOST'),
        'username' => mpcs_env('MPCS_USER'),
        'password' => mpcs_env('MPCS_PASSWORD'),
        'database' => mpcs_database(),
        'DBDriver' => 'MySQLi',
        'DBPrefix' => '',
        'pConnect' => false,
        'DBDebug' => true,
        'charset' => 'utf8mb4',
        'DBCollat' => 'utf8mb4_0900_ai_ci',
        'swapPre' => '',
        'encrypt' => false,
        'compress' => false,
        'strictOn' => false,
        'failover' => [],
        'port' => (int) mpcs_env('MPCS_PORT'),
    ]);
    $db->initialize();
    $ensureFactory = new ReflectionMethod(CodeIgniter\Database\Config::class, 'ensureFactory');
    $ensureFactory->invoke(null);

    $config = new Config\Migrations();
    $config->enabled = true;
    $config->lock = false;
    $config->table = 'migrations';
    $runner = new MigrationRunner($config, $db);
    $path = dirname(__DIR__) . '/migrations/2026-10-21-120000_DdlThenFail.php';

    $runnerException = null;

    try {
        $runner->force($path, 'App');
        $runnerReturned = true;
    } catch (Throwable $error) {
        $runnerReturned = false;
        $runnerException = [
            'class' => $error::class,
            'message' => $error->getMessage(),
            'file' => basename($error->getFile()),
            'line' => $error->getLine(),
            'trace' => array_slice(array_map(
                static fn (array $frame): string => basename((string) ($frame['file'] ?? '')) . ':' . ($frame['line'] ?? '') . ' ' . ($frame['function'] ?? ''),
                $error->getTrace(),
            ), 0, 6),
        ];
    }

    $other = mpcs_other();

    return [
        'scenario' => 'ci4-migration',
        'connection_id' => $db->connID->thread_id,
        'runner_returned' => $runnerReturned,
        'runner_exception' => $runnerException,
        'notes' => class_exists(App\Database\Migrations\DdlThenFail::class, false)
            ? App\Database\Migrations\DdlThenFail::$notes
            : null,
        'history' => mpcs_migration_history($other),
        'after_runner' => [
            'names' => mpcs_ddl_names($other),
            'table' => mpcs_ddl_table($other, 'ddl_side'),
        ],
        'close' => static function () use ($db): void {
            $db->close();
        },
    ];
}

function mpcs_other(): mysqli
{
    $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $db->set_charset('utf8mb4');

    return $db;
}

/**
 * @return list<string>
 */
function mpcs_ddl_names(mysqli $db): array
{
    $result = $db->query('SELECT name FROM marker ORDER BY name');
    $names = [];
    while ($row = $result->fetch_assoc()) {
        $names[] = $row['name'];
    }
    $result->free();

    return $names;
}

function mpcs_ddl_table(mysqli $db, string $table): bool
{
    $statement = $db->prepare('SELECT 1 FROM information_schema.tables WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?');
    $statement->bind_param('s', $table);
    $statement->execute();
    $result = $statement->get_result();
    $found = $result->fetch_row() !== null;
    $result->free();
    $statement->close();

    return $found;
}

/**
 * @return array<string, mixed>
 */
function mpcs_mysqli_duplicate(mysqli $db): array
{
    try {
        $db->query("INSERT INTO uniq_row (code) VALUES ('taken')");

        return ['threw' => false, 'returned' => true];
    } catch (mysqli_sql_exception $error) {
        return [
            'threw' => true,
            'returned' => false,
            'error_code' => $error->getCode(),
            'sqlstate' => $error->getSqlState(),
            'message' => $error->getMessage(),
        ];
    }
}

/**
 * @return list<array{class: string, version: string, batch: string}>
 */
function mpcs_migration_history(mysqli $db): array
{
    if (! mpcs_ddl_table($db, 'migrations')) {
        return [];
    }
    $result = $db->query('SELECT class, version, batch FROM migrations ORDER BY id');
    $rows = [];
    while ($row = $result->fetch_assoc()) {
        $rows[] = $row;
    }
    $result->free();

    return $rows;
}
