<?php

declare(strict_types=1);

/**
 * Nested CodeIgniter transactions beside a mysqli SAVEPOINT.
 * argv is the scenario name. The caller creates marker and uniq_row.
 */

require dirname(__DIR__) . '/src/Boot.php';
require dirname(__DIR__) . '/src/Subject.php';

$scenario = $argv[1] ?? '';

try {
    $other = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $other->set_charset('utf8mb4');
    match ($scenario) {
        'mysqli-savepoint-rollback' => mpcs_mysqli_savepoint($other),
        'ci4-managed-nested-success' => mpcs_ci4_managed_success($other),
        'ci4-managed-nested-failure' => mpcs_ci4_managed_failure($other),
        'ci4-manual-inner-rollback' => mpcs_ci4_manual_rollback($other),
        'ci4-manual-inner-commit' => mpcs_ci4_manual_commit($other),
        default => throw new InvalidArgumentException('Unknown scenario'),
    };
} catch (Throwable $error) {
    fwrite(STDOUT, json_encode([
        'failed' => true,
        'scenario' => $scenario,
        'class' => $error::class,
        'message' => $error->getMessage(),
        'file' => basename($error->getFile()),
        'line' => $error->getLine(),
    ], JSON_THROW_ON_ERROR) . "\n");
    exit(1);
}

/**
 * @return array<string, mixed>
 */
function mpcs_mysqli_savepoint(mysqli $other): array
{
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $db->set_charset('utf8mb4');
    $id = $db->thread_id;
    $db->begin_transaction();
    $db->query("INSERT INTO marker (name) VALUES ('outer')");
    $db->query('SAVEPOINT sp1');
    $db->query("INSERT INTO marker (name) VALUES ('inside')");
    $db->query('ROLLBACK TO SAVEPOINT sp1');
    $afterRollback = mpcs_mysqli_names($db);
    $db->query("INSERT INTO marker (name) VALUES ('after')");
    $beforeEnd = mpcs_other_names($other);
    $db->commit();
    $afterEnd = mpcs_other_names($other);
    mpcs_finish($db, $id, [
        'scenario' => 'mysqli-savepoint-rollback',
        'subject_after_rollback_to' => $afterRollback,
        'other_before_outer_end' => $beforeEnd,
        'other_after_outer_end' => $afterEnd,
    ]);
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_managed_success(mysqli $other): array
{
    $db = mpcs_open_ci4(true);
    $id = $db->connID->thread_id;
    $outerStart = $db->transStart();
    $outerInsert = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('outer')");
    $innerStart = $db->transStart();
    $innerInsert = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('inside')");
    $innerComplete = $db->transComplete();
    $afterInner = [
        'state' => mpcs_ci4_state($db),
        'subject' => mpcs_ci4_names($db),
    ];
    $afterInsert = mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('after')");
    $beforeEnd = mpcs_other_names($other);
    $outerComplete = $db->transComplete();
    $afterEnd = mpcs_other_names($other);
    $stateAfter = mpcs_ci4_state($db);
    mpcs_finish($db, $id, [
        'scenario' => 'ci4-managed-nested-success',
        'outer_start' => $outerStart,
        'outer_insert' => $outerInsert,
        'inner_start' => $innerStart,
        'inner_insert' => $innerInsert,
        'inner_complete' => $innerComplete,
        'after_inner' => $afterInner,
        'after_insert' => $afterInsert,
        'other_before_outer_end' => $beforeEnd,
        'outer_complete' => $outerComplete,
        'state_after' => $stateAfter,
        'other_after_outer_end' => $afterEnd,
    ]);
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_managed_failure(mysqli $other): array
{
    $db = mpcs_open_ci4(true);
    $id = $db->connID->thread_id;
    $db->transStart();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('outer')");
    $innerStart = $db->transStart();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('inside')");
    $duplicate = mpcs_ci4_query($db, "INSERT INTO uniq_row (code) VALUES ('taken')");
    $innerComplete = $db->transComplete();
    $afterInner = [
        'state' => mpcs_ci4_state($db),
        'subject' => mpcs_ci4_names($db),
        'other' => mpcs_other_names($other),
    ];
    $outerComplete = $db->transComplete();
    $afterEnd = mpcs_other_names($other);
    $stateAfter = mpcs_ci4_state($db);
    mpcs_finish($db, $id, [
        'scenario' => 'ci4-managed-nested-failure',
        'inner_start' => $innerStart,
        'duplicate' => $duplicate,
        'inner_complete' => $innerComplete,
        'after_inner' => $afterInner,
        'outer_complete' => $outerComplete,
        'state_after' => $stateAfter,
        'other_after_outer_end' => $afterEnd,
    ]);
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_manual_rollback(mysqli $other): array
{
    $db = mpcs_open_ci4(true);
    $id = $db->connID->thread_id;
    $db->transBegin();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('outer')");
    $innerBegin = $db->transBegin();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('inside')");
    $innerRollback = $db->transRollback();
    $afterInner = [
        'state' => mpcs_ci4_state($db),
        'subject' => mpcs_ci4_names($db),
        'other' => mpcs_other_names($other),
    ];
    $outerCommit = $db->transCommit();
    $afterEnd = mpcs_other_names($other);
    mpcs_finish($db, $id, [
        'scenario' => 'ci4-manual-inner-rollback',
        'inner_begin' => $innerBegin,
        'inner_rollback' => $innerRollback,
        'after_inner' => $afterInner,
        'outer_commit' => $outerCommit,
        'other_after_outer_end' => $afterEnd,
    ]);
}

/**
 * @return array<string, mixed>
 */
function mpcs_ci4_manual_commit(mysqli $other): array
{
    $db = mpcs_open_ci4(true);
    $id = $db->connID->thread_id;
    $db->transBegin();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('outer')");
    $innerBegin = $db->transBegin();
    mpcs_ci4_query($db, "INSERT INTO marker (name) VALUES ('inside')");
    $innerCommit = $db->transCommit();
    $afterInner = [
        'state' => mpcs_ci4_state($db),
        'subject' => mpcs_ci4_names($db),
        'other' => mpcs_other_names($other),
    ];
    $outerCommit = $db->transCommit();
    $afterEnd = mpcs_other_names($other);
    mpcs_finish($db, $id, [
        'scenario' => 'ci4-manual-inner-commit',
        'inner_begin' => $innerBegin,
        'inner_commit' => $innerCommit,
        'after_inner' => $afterInner,
        'outer_commit' => $outerCommit,
        'other_after_outer_end' => $afterEnd,
    ]);
}

/**
 * @return list<string>
 */
function mpcs_mysqli_names(mysqli $db): array
{
    $result = $db->query('SELECT name FROM marker ORDER BY name');
    $names = [];
    while ($row = $result->fetch_assoc()) {
        $names[] = $row['name'];
    }
    $result->free();

    return $names;
}

/**
 * @return list<string>
 */
function mpcs_ci4_names(CodeIgniter\Database\MySQLi\Connection $db): array
{
    $result = $db->query('SELECT name FROM marker ORDER BY name');
    if ($result === false || $result === true) {
        return [];
    }
    $names = [];
    foreach ($result->getResultArray() as $row) {
        $names[] = $row['name'];
    }

    return $names;
}

/**
 * @return list<string>
 */
function mpcs_other_names(mysqli $other): array
{
    return mpcs_mysqli_names($other);
}

/**
 * @param mysqli|CodeIgniter\Database\MySQLi\Connection $db
 * @param array<string, mixed>                          $payload
 */
function mpcs_finish(mysqli|CodeIgniter\Database\MySQLi\Connection $db, int $connectionId, array $payload): void
{
    $payload['connection_id'] = $connectionId;
    $payload['versions'] = mpcs_versions();
    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    fflush(STDOUT);

    while (($line = fgets(STDIN)) !== false) {
        if (trim($line) === 'go') {
            break;
        }
    }

    $db->close();
}

