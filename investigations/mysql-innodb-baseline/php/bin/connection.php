<?php

declare(strict_types=1);

/**
 * Connection loss before commit, and the next use of that connection.
 * argv: kill|idle|reconnect, then mysqli|pdo|ci4-managed|ci4-manual.
 * kill waits for a stdin line "go" after it has inserted and printed connection_id.
 */

require dirname(__DIR__) . '/src/Boot.php';
require dirname(__DIR__) . '/src/Subject.php';

$kind = $argv[1] ?? '';
$mode = $argv[2] ?? '';

try {
    $result = match ($kind) {
        'kill' => mpcs_kill($mode),
        'idle' => mpcs_idle($mode, false),
        'reconnect' => mpcs_idle($mode, true),
        default => throw new InvalidArgumentException('Unknown kind'),
    };
    mpcs_line($result);
} catch (Throwable $error) {
    mpcs_line([
        'event' => 'result',
        'failed' => true,
        'class' => $error::class,
        'message' => $error->getMessage(),
        'file' => basename($error->getFile()),
        'line' => $error->getLine(),
    ]);
    exit(1);
}

/**
 * @param array<string, mixed> $payload
 */
function mpcs_line(array $payload): void
{
    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    fflush(STDOUT);
}

function mpcs_wait_go(): void
{
    while (($line = fgets(STDIN)) !== false) {
        if (trim($line) === 'go') {
            return;
        }
    }

    throw new RuntimeException('stdin closed before go');
}

/**
 * @return array<string, mixed>
 */
function mpcs_kill(string $mode): array
{
    $subject = mpcs_open_subject($mode);
    $connectionId = mpcs_subject_id($subject);
    mpcs_subject_begin($subject, $mode);
    $insert = mpcs_subject_insert($subject, 'killed');
    if (($insert['returned'] ?? null) !== true || ($insert['threw'] ?? false) === true) {
        throw new RuntimeException('insert before kill did not succeed');
    }

    mpcs_line([
        'event' => 'ready',
        'connection_id' => $connectionId,
        'insert' => $insert,
    ]);
    mpcs_wait_go();

    return [
        'event' => 'result',
        'kind' => 'kill',
        'mode' => $mode,
        'connection_id' => $connectionId,
        'commit' => mpcs_subject_complete($subject, $mode),
        'status' => mpcs_subject_status($subject),
        'logs' => mpcs_logs(),
        'versions' => mpcs_versions(),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_idle(string $mode, bool $reconnect): array
{
    if ($reconnect && ! str_starts_with($mode, 'ci4')) {
        throw new InvalidArgumentException('reconnect is the CodeIgniter method');
    }

    $subject = mpcs_open_subject($mode);
    $timeout = mpcs_subject_exec($subject, 'SET SESSION wait_timeout = 1');
    $interactive = mpcs_subject_exec($subject, 'SET SESSION interactive_timeout = 1');
    $connectionId = mpcs_subject_id($subject);
    mpcs_subject_begin($subject, $mode);
    $insert = mpcs_subject_insert($subject, 'idle');
    if (($insert['returned'] ?? null) !== true || ($insert['threw'] ?? false) === true) {
        throw new RuntimeException('insert before idle did not succeed');
    }

    sleep(3);

    $next = $reconnect ? null : mpcs_subject_exec($subject, 'SELECT 1');
    $ping = null;
    $reconnectCall = null;
    $connectionIdAfter = null;
    $follow = null;
    $complete = null;

    if ($reconnect) {
        $ping = mpcs_ci4_ping($subject['db']);
        $reconnectCall = mpcs_ci4_reconnect($subject['db']);
        $statusAfter = mpcs_subject_status($subject);

        try {
            $connectionIdAfter = mpcs_subject_id($subject);
        } catch (Throwable $error) {
            $connectionIdAfter = ['threw' => true, 'class' => $error::class, 'message' => $error->getMessage()];
        }

        $follow = mpcs_subject_insert($subject, 'after-reconnect');
        $complete = mpcs_subject_complete($subject, $mode);
    }

    return [
        'event' => 'result',
        'kind' => $reconnect ? 'reconnect' : 'idle',
        'mode' => $mode,
        'mysqli_reconnect_ini' => ini_get('mysqli.reconnect'),
        'connection_id' => $connectionId,
        'timeout' => $timeout,
        'interactive_timeout' => $interactive,
        'insert' => $insert,
        'slept_seconds' => 3,
        'next' => $next,
        'ping' => $ping,
        'reconnect' => $reconnectCall,
        'status_after_reconnect' => $reconnect ? ($statusAfter ?? null) : null,
        'connection_id_after' => $connectionIdAfter,
        'follow' => $follow,
        'complete' => $complete,
        'status' => mpcs_subject_status($subject),
        'logs' => mpcs_logs(),
        'versions' => mpcs_versions(),
    ];
}

/**
 * @return array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection}
 */
function mpcs_open_subject(string $mode): array
{
    if ($mode === 'mysqli') {
        mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
        $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
        $db->set_charset('utf8mb4');

        return ['driver' => 'mysqli', 'db' => $db];
    }

    if ($mode === 'pdo') {
        return ['driver' => 'pdo', 'db' => new PDO(
            'mysql:host=' . mpcs_env('MPCS_HOST') . ';port=' . mpcs_env('MPCS_PORT') . ';dbname=' . mpcs_database() . ';charset=utf8mb4',
            mpcs_env('MPCS_USER'),
            mpcs_env('MPCS_PASSWORD'),
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
        )];
    }

    if ($mode === 'ci4-managed' || $mode === 'ci4-manual') {
        return ['driver' => 'ci4', 'db' => mpcs_open_ci4(true)];
    }

    throw new InvalidArgumentException('Unknown mode');
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 */
function mpcs_subject_id(array $subject): int
{
    if ($subject['driver'] === 'mysqli') {
        return (int) $subject['db']->query('SELECT CONNECTION_ID() AS connection_id')->fetch_assoc()['connection_id'];
    }

    if ($subject['driver'] === 'pdo') {
        return (int) $subject['db']->query('SELECT CONNECTION_ID() AS connection_id')->fetch(PDO::FETCH_ASSOC)['connection_id'];
    }

    return mpcs_ci4_connection_id($subject['db']);
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 */
function mpcs_subject_begin(array $subject, string $mode): void
{
    if ($subject['driver'] === 'mysqli') {
        $subject['db']->begin_transaction();

        return;
    }

    if ($subject['driver'] === 'pdo') {
        $subject['db']->beginTransaction();

        return;
    }

    if ($mode === 'ci4-managed') {
        $subject['db']->transStart();

        return;
    }

    $subject['db']->transBegin();
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 * @return array<string, mixed>
 */
function mpcs_subject_insert(array $subject, string $name): array
{
    if (! in_array($name, ['killed', 'idle', 'after-reconnect'], true)) {
        throw new InvalidArgumentException('marker name is not allowed');
    }

    return mpcs_subject_exec($subject, "INSERT INTO marker (name) VALUES ('{$name}')");
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 * @return array<string, mixed>
 */
function mpcs_subject_exec(array $subject, string $sql): array
{
    if (! in_array($sql, [
        'SELECT 1',
        'SELECT CONNECTION_ID() AS connection_id',
        'SET SESSION wait_timeout = 1',
        'SET SESSION interactive_timeout = 1',
        "INSERT INTO marker (name) VALUES ('killed')",
        "INSERT INTO marker (name) VALUES ('idle')",
        "INSERT INTO marker (name) VALUES ('after-reconnect')",
    ], true)) {
        throw new InvalidArgumentException('sql is not allowed');
    }

    try {
        if ($subject['driver'] === 'ci4') {
            $result = mpcs_ci4_query($subject['db'], $sql);
            $result['status'] = mpcs_ci4_state($subject['db']);

            return $result;
        }

        if ($subject['driver'] === 'mysqli') {
            $returned = $subject['db']->query($sql);
            if ($returned instanceof mysqli_result) {
                $returned->free();
            }

            return ['threw' => false, 'returned' => true, 'error_code' => 0, 'sqlstate' => null, 'message' => null];
        }

        if (str_starts_with($sql, 'SELECT')) {
            $subject['db']->query($sql)->fetchAll();
        } else {
            $subject['db']->exec($sql);
        }

        return ['threw' => false, 'returned' => true, 'error_code' => 0, 'sqlstate' => null, 'message' => null];
    } catch (mysqli_sql_exception $error) {
        return mpcs_driver_failure($error->getCode(), $error->getSqlState(), $error->getMessage());
    } catch (PDOException $error) {
        $info = $error->errorInfo ?? [];

        return mpcs_driver_failure($info[1] ?? $error->getCode(), isset($info[0]) ? (string) $info[0] : null, $error->getMessage());
    } catch (Throwable $error) {
        return [
            'threw' => true,
            'returned' => false,
            'class' => $error::class,
            'error_code' => $error->getCode(),
            'sqlstate' => null,
            'message' => $error->getMessage(),
        ];
    }
}

/**
 * @return array<string, mixed>
 */
function mpcs_driver_failure(int|string $code, ?string $sqlstate, string $message): array
{
    return [
        'threw' => true,
        'returned' => false,
        'error_code' => is_int($code) ? $code : (int) $code,
        'sqlstate' => $sqlstate,
        'message' => $message,
    ];
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 * @return array<string, mixed>
 */
function mpcs_subject_complete(array $subject, string $mode): array
{
    try {
        if ($subject['driver'] === 'mysqli') {
            $returned = $subject['db']->commit();
        } elseif ($subject['driver'] === 'pdo') {
            $returned = $subject['db']->commit();
        } elseif ($mode === 'ci4-managed') {
            $returned = $subject['db']->transComplete();
        } else {
            $returned = $subject['db']->transCommit();
        }

        return [
            'threw' => false,
            'returned' => $returned === true,
            'message' => null,
            'error_code' => null,
            'status' => mpcs_subject_status($subject),
        ];
    } catch (mysqli_sql_exception $error) {
        $failure = mpcs_driver_failure($error->getCode(), $error->getSqlState(), $error->getMessage());
        $failure['status'] = mpcs_subject_status($subject);

        return $failure;
    } catch (PDOException $error) {
        $info = $error->errorInfo ?? [];
        $failure = mpcs_driver_failure($info[1] ?? $error->getCode(), isset($info[0]) ? (string) $info[0] : null, $error->getMessage());
        $failure['status'] = mpcs_subject_status($subject);

        return $failure;
    } catch (Throwable $error) {
        return [
            'threw' => true,
            'returned' => false,
            'class' => $error::class,
            'error_code' => $error->getCode(),
            'message' => $error->getMessage(),
            'status' => mpcs_subject_status($subject),
        ];
    }
}

/**
 * @param array{driver: string, db: mysqli|PDO|CodeIgniter\Database\MySQLi\Connection} $subject
 * @return array<string, mixed>
 */
function mpcs_subject_status(array $subject): array
{
    if ($subject['driver'] === 'ci4') {
        return mpcs_ci4_state($subject['db']);
    }

    if ($subject['driver'] === 'pdo') {
        try {
            return ['in_transaction' => $subject['db']->inTransaction()];
        } catch (Throwable $error) {
            return ['in_transaction' => null, 'message' => $error->getMessage()];
        }
    }

    return ['driver' => 'mysqli'];
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_ping(CodeIgniter\Database\MySQLi\Connection $db): array
{
    try {
        return ['threw' => false, 'returned' => $db->ping()];
    } catch (Throwable $error) {
        return ['threw' => true, 'returned' => null, 'class' => $error::class, 'message' => $error->getMessage()];
    }
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_reconnect(CodeIgniter\Database\MySQLi\Connection $db): array
{
    try {
        $db->reconnect();

        return ['threw' => false];
    } catch (Throwable $error) {
        return ['threw' => true, 'class' => $error::class, 'message' => $error->getMessage()];
    }
}
