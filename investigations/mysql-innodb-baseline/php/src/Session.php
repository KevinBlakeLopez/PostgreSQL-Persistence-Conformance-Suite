<?php

declare(strict_types=1);

use CodeIgniter\Database\MySQLi\Connection;

/**
 * One connection, driven by JSON commands on stdin. Each command writes one JSON line.
 * The caller holds the other session and reads the database itself.
 */

/** @var mysqli|PDO|Connection|null */
$mpcsSession = null;
$mpcsSessionDriver = '';
$mpcsSessionOpen = false;

function mpcs_session_reply(array $payload): void
{
    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    fflush(STDOUT);
}

function mpcs_session_sql_allowed(string $sql): bool
{
    return in_array($sql, [
        "INSERT INTO marker (name) VALUES ('victim')",
        "INSERT INTO marker (name) VALUES ('after-deadlock')",
        "INSERT INTO marker (name) VALUES ('before')",
        "INSERT INTO marker (name) VALUES ('after')",
        'UPDATE dl SET v = v + 1 WHERE id = 1',
        'UPDATE dl SET v = v + 1 WHERE id = 2',
        'UPDATE lk SET v = 2 WHERE id = 1',
        'SET SESSION innodb_lock_wait_timeout = 2',
    ], true);
}

/**
 * @param array<string, mixed> $command
 * @return array<string, mixed>
 */
function mpcs_session_handle(array $command): array
{
    $op = $command['op'] ?? '';

    return match ($op) {
        'open' => mpcs_session_open((string) ($command['driver'] ?? ''), (bool) ($command['debug'] ?? true)),
        'begin' => mpcs_session_begin((string) ($command['api'] ?? '')),
        'query' => mpcs_session_query((string) ($command['sql'] ?? '')),
        'complete' => mpcs_session_complete((string) ($command['api'] ?? '')),
        'status' => mpcs_session_status(),
        'close' => mpcs_session_close(),
        default => throw new InvalidArgumentException('Unknown op'),
    };
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_open(string $driver, bool $debug): array
{
    global $mpcsSession, $mpcsSessionDriver, $mpcsSessionOpen;

    if ($mpcsSessionOpen) {
        throw new RuntimeException('session already open');
    }

    if ($driver === 'mysqli') {
        mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
        $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
        $db->set_charset('utf8mb4');
        $connectionId = (int) $db->query('SELECT CONNECTION_ID() AS connection_id')->fetch_assoc()['connection_id'];
        $mpcsSession = $db;
    } elseif ($driver === 'pdo') {
        $db = new PDO(
            'mysql:host=' . mpcs_env('MPCS_HOST') . ';port=' . mpcs_env('MPCS_PORT') . ';dbname=' . mpcs_database() . ';charset=utf8mb4',
            mpcs_env('MPCS_USER'),
            mpcs_env('MPCS_PASSWORD'),
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
        );
        $connectionId = (int) $db->query('SELECT CONNECTION_ID() AS connection_id')->fetch(PDO::FETCH_ASSOC)['connection_id'];
        $mpcsSession = $db;
    } elseif ($driver === 'ci4') {
        $db = mpcs_open_ci4($debug);
        $connectionId = mpcs_ci4_connection_id($db);
        $mpcsSession = $db;
    } else {
        throw new InvalidArgumentException('Unknown driver');
    }

    $mpcsSessionDriver = $driver;
    $mpcsSessionOpen = true;

    return [
        'op' => 'open',
        'driver' => $driver,
        'connection_id' => $connectionId,
        'flags' => $driver === 'ci4' ? mpcs_ci4_flags($db) : null,
        'versions' => mpcs_versions(),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_begin(string $api): array
{
    global $mpcsSession, $mpcsSessionDriver;

    mpcs_session_require();

    if ($mpcsSessionDriver === 'mysqli' && $api === 'driver') {
        $returned = $mpcsSession->begin_transaction();
    } elseif ($mpcsSessionDriver === 'pdo' && $api === 'driver') {
        $returned = $mpcsSession->beginTransaction();
    } elseif ($mpcsSessionDriver === 'ci4' && $api === 'managed') {
        $returned = $mpcsSession->transStart();
    } elseif ($mpcsSessionDriver === 'ci4' && $api === 'manual') {
        $returned = $mpcsSession->transBegin();
    } else {
        throw new InvalidArgumentException('begin api does not match the driver');
    }

    return [
        'op' => 'begin',
        'api' => $api,
        'returned' => $returned === true,
        'status' => mpcs_session_status(),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_query(string $sql): array
{
    global $mpcsSession, $mpcsSessionDriver;

    mpcs_session_require();

    if (! mpcs_session_sql_allowed($sql)) {
        throw new InvalidArgumentException('sql is not in the session allowlist');
    }

    $started = microtime(true);

    if ($mpcsSessionDriver === 'ci4') {
        $result = mpcs_ci4_query($mpcsSession, $sql);
        $result['elapsed_ms'] = (int) round((microtime(true) - $started) * 1000);
        $result['op'] = 'query';

        return $result;
    }

    try {
        if ($mpcsSessionDriver === 'mysqli') {
            $returned = $mpcsSession->query($sql);
            if ($returned instanceof mysqli_result) {
                $returned->free();
            }
        } else {
            $mpcsSession->exec($sql);
        }

        return [
            'op' => 'query',
            'threw' => false,
            'returned' => true,
            'error_code' => 0,
            'sqlstate' => null,
            'error_message' => null,
            'elapsed_ms' => (int) round((microtime(true) - $started) * 1000),
        ];
    } catch (mysqli_sql_exception $error) {
        return mpcs_session_driver_error($error->getCode(), $error->getSqlState(), $error->getMessage(), $started);
    } catch (PDOException $error) {
        $info = $error->errorInfo ?? [];

        return mpcs_session_driver_error($info[1] ?? $error->getCode(), isset($info[0]) ? (string) $info[0] : null, $error->getMessage(), $started);
    }
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_driver_error(int|string $code, ?string $sqlstate, string $message, float $started): array
{
    return [
        'op' => 'query',
        'threw' => true,
        'returned' => false,
        'error_code' => is_int($code) ? $code : (int) $code,
        'sqlstate' => $sqlstate,
        'error_message' => $message,
        'elapsed_ms' => (int) round((microtime(true) - $started) * 1000),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_complete(string $api): array
{
    global $mpcsSession, $mpcsSessionDriver;

    mpcs_session_require();

    $threw = false;
    $message = null;
    $sqlstate = null;

    if ($mpcsSessionDriver === 'ci4' && $api === 'managed') {
        $choice = 'trans_complete';
        $returned = $mpcsSession->transComplete();
    } elseif ($mpcsSessionDriver === 'ci4' && $api === 'manual') {
        $choice = 'trans_commit';
        $returned = $mpcsSession->transCommit();
    } elseif ($mpcsSessionDriver === 'ci4' && $api === 'documented') {
        if ($mpcsSession->transStatus() === false) {
            $choice = 'rollback';
            $returned = $mpcsSession->transRollback();
        } else {
            $choice = 'commit';
            $returned = $mpcsSession->transCommit();
        }
    } elseif ($api === 'driver' && $mpcsSessionDriver === 'mysqli') {
        $choice = 'commit';
        $returned = $mpcsSession->commit();
    } elseif ($api === 'driver' && $mpcsSessionDriver === 'pdo') {
        $choice = 'commit';

        try {
            $returned = $mpcsSession->commit();
        } catch (PDOException $error) {
            $info = $error->errorInfo ?? [];
            $returned = false;
            $threw = true;
            $message = $error->getMessage();
            $sqlstate = isset($info[0]) ? (string) $info[0] : null;
        }
    } else {
        throw new InvalidArgumentException('complete api does not match the driver');
    }

    return [
        'op' => 'complete',
        'api' => $api,
        'choice' => $choice,
        'returned' => $returned === true,
        'threw' => $threw,
        'message' => $message,
        'sqlstate' => $sqlstate,
        'status' => mpcs_session_status(),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_status(): array
{
    global $mpcsSession, $mpcsSessionDriver;

    mpcs_session_require();

    if ($mpcsSessionDriver === 'ci4') {
        return [
            'driver' => 'ci4',
            'trans_status' => $mpcsSession->transStatus(),
            'trans_depth' => $mpcsSession->transDepth,
            'trans_failure' => $mpcsSession->transFailure,
            'trans_strict' => $mpcsSession->transStrict,
            'trans_exception' => $mpcsSession->transException,
        ];
    }

    if ($mpcsSessionDriver === 'pdo') {
        return [
            'driver' => 'pdo',
            'in_transaction' => $mpcsSession->inTransaction(),
        ];
    }

    return ['driver' => 'mysqli'];
}

/**
 * @return array<string, mixed>
 */
function mpcs_session_close(): array
{
    global $mpcsSession, $mpcsSessionDriver, $mpcsSessionOpen;

    $cleaned = false;

    if ($mpcsSession instanceof Connection && $mpcsSession->transDepth !== 0) {
        $cleaned = true;

        while ($mpcsSession->transDepth !== 0) {
            $before = $mpcsSession->transDepth;
            if ($mpcsSession->transRollback() !== true || $mpcsSession->transDepth === $before) {
                break;
            }
        }
    } elseif ($mpcsSession instanceof PDO && $mpcsSession->inTransaction()) {
        $cleaned = true;
        $mpcsSession->rollBack();
    } elseif ($mpcsSession instanceof mysqli) {
        $mpcsSession->close();
    }

    if ($mpcsSession instanceof Connection) {
        $mpcsSession->close();
    }

    $mpcsSession = null;
    $mpcsSessionDriver = '';
    $mpcsSessionOpen = false;

    return [
        'op' => 'close',
        'left_transaction_open' => $cleaned,
        'logs' => mpcs_logs(),
    ];
}

function mpcs_session_require(): void
{
    global $mpcsSessionOpen;

    if (! $mpcsSessionOpen) {
        throw new RuntimeException('session is not open');
    }
}

function mpcs_session_loop(): void
{
    while (($line = fgets(STDIN)) !== false) {
        $line = trim($line);
        if ($line === '') {
            continue;
        }

        try {
            $command = json_decode($line, true, 8, JSON_THROW_ON_ERROR);
            if (! is_array($command)) {
                throw new InvalidArgumentException('command is not an object');
            }
            $result = mpcs_session_handle($command);
            $result['ok'] = true;
            mpcs_session_reply($result);
            if (($command['op'] ?? '') === 'close') {
                return;
            }
        } catch (Throwable $error) {
            mpcs_session_reply([
                'ok' => false,
                'class' => $error::class,
                'message' => $error->getMessage(),
                'file' => basename($error->getFile()),
                'line' => $error->getLine(),
            ]);
        }
    }
}
