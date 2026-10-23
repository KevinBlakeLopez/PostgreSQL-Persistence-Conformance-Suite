<?php

declare(strict_types=1);

use CodeIgniter\Database\MySQLi\Connection;

/**
 * One process runs one scenario. The caller reads the database from another connection.
 *
 * Marker names and the duplicate code are fixed. They are not taken from the environment.
 */

function mpcs_run_scenario(string $scenario): array
{
    return match ($scenario) {
        'mysqli-commit-after-1062' => mpcs_mysqli_commit_after_duplicate(),
        'pdo-commit-after-1062' => mpcs_pdo_commit_after_duplicate(),
        'ci4-managed-default' => mpcs_ci4_managed_default(),
        'ci4-managed-exception' => mpcs_ci4_managed_exception(),
        'ci4-managed-strict-second' => mpcs_ci4_managed_strict_second(),
        'ci4-managed-reset' => mpcs_ci4_managed_reset(),
        'ci4-managed-nonstrict' => mpcs_ci4_managed_nonstrict(),
        'ci4-manual-documented' => mpcs_ci4_manual_documented(true),
        'ci4-manual-documented-debug-off' => mpcs_ci4_manual_documented(false),
        'ci4-manual-documented-then-managed' => mpcs_ci4_manual_then_managed(),
        'ci4-manual-unchecked-then-managed' => mpcs_ci4_manual_unchecked_then_managed(),
        default => throw new InvalidArgumentException('Unknown scenario: ' . $scenario),
    };
}

function mpcs_mysqli_commit_after_duplicate(): array
{
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $db->set_charset('utf8mb4');
    $open = false;

    try {
        $connectionId = (int) $db->query('SELECT CONNECTION_ID() AS id')->fetch_assoc()['id'];
        $began = $db->begin_transaction();
        $open = true;
        $db->query("INSERT INTO marker (name) VALUES ('before-error')");
        $duplicate = null;

        try {
            $db->query("INSERT INTO uniq_row (code) VALUES ('taken')");
            $duplicate = ['threw' => false];
        } catch (mysqli_sql_exception $error) {
            $duplicate = [
                'threw' => true,
                'class' => $error::class,
                'errno' => $error->getCode(),
                'sqlstate' => $error->getSqlState(),
                'message' => $error->getMessage(),
            ];
        }

        $after = $db->query("INSERT INTO marker (name) VALUES ('after-error')");
        $committed = $db->commit();
        $open = false;

        return [
            'scenario' => 'mysqli-commit-after-1062',
            'driver' => 'mysqli',
            'mysqli_report' => 'MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT',
            'connection_id' => $connectionId,
            'begin' => $began,
            'duplicate' => $duplicate,
            'after_error_insert' => $after === true,
            'commit' => $committed,
        ];
    } finally {
        if ($open) {
            $db->rollback();
        }
        $db->close();
    }
}

function mpcs_pdo_commit_after_duplicate(): array
{
    $pdo = new PDO(
        'mysql:host=' . mpcs_env('MPCS_HOST') . ';port=' . mpcs_env('MPCS_PORT') . ';dbname=' . mpcs_database() . ';charset=utf8mb4',
        mpcs_env('MPCS_USER'),
        mpcs_env('MPCS_PASSWORD'),
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
    );
    $open = false;

    try {
        $connectionId = (int) $pdo->query('SELECT CONNECTION_ID() AS id')->fetch(PDO::FETCH_ASSOC)['id'];
        $began = $pdo->beginTransaction();
        $open = true;
        $pdo->exec("INSERT INTO marker (name) VALUES ('before-error')");
        $duplicate = null;

        try {
            $pdo->exec("INSERT INTO uniq_row (code) VALUES ('taken')");
            $duplicate = ['threw' => false];
        } catch (PDOException $error) {
            $info = $error->errorInfo ?? [];
            $duplicate = [
                'threw' => true,
                'class' => $error::class,
                'errno' => $info[1] ?? null,
                'sqlstate' => $info[0] ?? null,
                'code' => $error->getCode(),
                'message' => $error->getMessage(),
            ];
        }

        $after = $pdo->exec("INSERT INTO marker (name) VALUES ('after-error')");
        $committed = $pdo->commit();
        $open = false;

        return [
            'scenario' => 'pdo-commit-after-1062',
            'driver' => 'pdo_mysql',
            'errmode' => 'ERRMODE_EXCEPTION',
            'pdo_client' => (string) $pdo->getAttribute(PDO::ATTR_CLIENT_VERSION),
            'connection_id' => $connectionId,
            'begin' => $began,
            'duplicate' => $duplicate,
            'after_error_insert' => $after !== false,
            'commit' => $committed,
        ];
    } finally {
        if ($open && $pdo->inTransaction()) {
            $pdo->rollBack();
        }
    }
}

function mpcs_open_ci4(bool $debug): Connection
{
    $db = new Connection([
        'DSN' => '',
        'hostname' => mpcs_env('MPCS_HOST'),
        'username' => mpcs_env('MPCS_USER'),
        'password' => mpcs_env('MPCS_PASSWORD'),
        'database' => mpcs_database(),
        'DBDriver' => 'MySQLi',
        'DBPrefix' => '',
        'pConnect' => false,
        'DBDebug' => $debug,
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

    return $db;
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_flags(Connection $db): array
{
    return [
        'DBDriver' => $db->DBDriver,
        'DBDebug' => $db->DBDebug,
        'pConnect' => $db->pConnect,
        'strictOn' => $db->strictOn,
        'transStrict' => $db->transStrict,
        'transException' => $db->transException,
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_state(Connection $db): array
{
    return [
        'trans_status' => $db->transStatus(),
        'trans_depth' => $db->transDepth,
        'trans_failure' => $db->transFailure,
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_query(Connection $db, string $sql): array
{
    try {
        $returned = $db->query($sql);
        $error = $db->error();
        $code = $error['code'] ?? null;

        return [
            'threw' => false,
            'returned' => $returned === true ? true : ($returned === false ? false : 'result'),
            'error_code' => $code,
            'error_message' => (int) $code === 0 ? null : ($error['message'] ?? null),
            'state' => mpcs_ci4_state($db),
        ];
    } catch (Throwable $error) {
        $sqlstate = null;
        $current = $error;

        while ($current !== null) {
            if ($current instanceof mysqli_sql_exception) {
                $sqlstate = $current->getSqlState();
                break;
            }
            $current = $current->getPrevious();
        }

        return [
            'threw' => true,
            'class' => $error::class,
            'code' => $error->getCode(),
            'sqlstate' => $sqlstate,
            'message' => $error->getMessage(),
            'state' => mpcs_ci4_state($db),
        ];
    }
}

function mpcs_ci4_connection_id(Connection $db): int
{
    $row = $db->query('SELECT CONNECTION_ID() AS connection_id')->getRowArray();

    return (int) $row['connection_id'];
}

/**
 * @param array<string, mixed> $body
 * @return array<string, mixed>
 */
function mpcs_ci4_finish(Connection $db, string $scenario, array $body): array
{
    $depth = $db->transDepth;
    $cleaned = false;

    if ($depth !== 0) {
        $cleaned = true;

        while ($db->transDepth !== 0) {
            $before = $db->transDepth;
            if ($db->transRollback() !== true || $db->transDepth === $before) {
                break;
            }
        }
    }

    $db->close();

    return [
        'scenario' => $scenario,
        'driver' => 'ci4-mysqli',
        'flags' => $body['flags'] ?? mpcs_ci4_flags($db),
        'connection_id' => $body['connection_id'] ?? null,
        'left_transaction_open' => $cleaned,
        'steps' => $body['steps'],
    ];
}

function mpcs_ci4_managed_default(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $started = $db->transStart();
    $before = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $statusAfterDuplicate = $db->transStatus();
    $after = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('after-error')");
    $statusBeforeComplete = $db->transStatus();
    $complete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-managed-default', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'trans_start' => $started,
            'before_error' => $before,
            'duplicate' => $duplicate,
            'trans_status_after_duplicate' => $statusAfterDuplicate,
            'after_error' => $after,
            'trans_status_before_complete' => $statusBeforeComplete,
            'trans_complete' => $complete,
            'state_after_complete' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_managed_exception(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transException(true);
    $started = $db->transStart();
    $before = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $complete = null;

    if ($duplicate['threw'] !== true) {
        $complete = $db->transComplete();
    }

    return mpcs_ci4_finish($db, 'ci4-managed-exception', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'trans_start' => $started,
            'before_error' => $before,
            'duplicate' => $duplicate,
            'trans_complete_reached' => $complete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_managed_strict_second(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transStart();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $firstComplete = $db->transComplete();
    $statusBetween = $db->transStatus();
    $secondStart = $db->transStart();
    $second = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('second-group')");
    $secondComplete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-managed-strict-second', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'duplicate' => $duplicate,
            'first_complete' => $firstComplete,
            'trans_status_between' => $statusBetween,
            'second_start' => $secondStart,
            'second_insert' => $second,
            'second_complete' => $secondComplete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_managed_reset(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transStart();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $firstComplete = $db->transComplete();
    $reset = $db->resetTransStatus();
    $statusAfterReset = $db->transStatus();
    $db->transStart();
    $second = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('second-group')");
    $secondComplete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-managed-reset', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'first_complete' => $firstComplete,
            'reset_returned_connection' => $reset instanceof Connection,
            'trans_status_after_reset' => $statusAfterReset,
            'second_insert' => $second,
            'second_complete' => $secondComplete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_managed_nonstrict(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transStrict(false);
    $db->transStart();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $firstComplete = $db->transComplete();
    $statusBetween = $db->transStatus();
    $db->transStart();
    $second = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('second-group')");
    $secondComplete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-managed-nonstrict', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'first_complete' => $firstComplete,
            'trans_status_between' => $statusBetween,
            'second_insert' => $second,
            'second_complete' => $secondComplete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_manual_documented(bool $debug): array
{
    $scenario = $debug ? 'ci4-manual-documented' : 'ci4-manual-documented-debug-off';
    $db = mpcs_open_ci4($debug);
    $connectionId = mpcs_ci4_connection_id($db);
    $began = $db->transBegin();
    $before = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $status = $db->transStatus();
    $choice = null;
    $ended = null;

    if ($status === false) {
        $choice = 'rollback';
        $ended = $db->transRollback();
    } else {
        $choice = 'commit';
        $ended = $db->transCommit();
    }

    return mpcs_ci4_finish($db, $scenario, [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'trans_begin' => $began,
            'before_error' => $before,
            'duplicate' => $duplicate,
            'trans_status' => $status,
            'choice' => $choice,
            'end_call' => $ended,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_manual_then_managed(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transBegin();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $status = $db->transStatus();
    $rolled = $status === false ? $db->transRollback() : null;
    $statusAfterRollback = $db->transStatus();
    $db->transStart();
    $second = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('second-group')");
    $secondComplete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-manual-documented-then-managed', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'duplicate' => $duplicate,
            'manual_rollback' => $rolled,
            'trans_status_after_rollback' => $statusAfterRollback,
            'second_insert' => $second,
            'second_complete' => $secondComplete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}

function mpcs_ci4_manual_unchecked_then_managed(): array
{
    $db = mpcs_open_ci4(true);
    $connectionId = mpcs_ci4_connection_id($db);
    $db->transBegin();
    $before = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('before-error')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $statusBeforeCommit = $db->transStatus();
    $commit = $db->transCommit();
    $statusAfterCommit = $db->transStatus();
    $db->transStart();
    $second = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('second-group')");
    $secondComplete = $db->transComplete();

    return mpcs_ci4_finish($db, 'ci4-manual-unchecked-then-managed', [
        'flags' => mpcs_ci4_flags($db),
        'connection_id' => $connectionId,
        'steps' => [
            'before_error' => $before,
            'duplicate' => $duplicate,
            'trans_status_before_commit' => $statusBeforeCommit,
            'trans_commit' => $commit,
            'trans_status_after_commit' => $statusAfterCommit,
            'second_insert' => $second,
            'second_complete' => $secondComplete,
            'state_after' => mpcs_ci4_state($db),
        ],
    ]);
}
