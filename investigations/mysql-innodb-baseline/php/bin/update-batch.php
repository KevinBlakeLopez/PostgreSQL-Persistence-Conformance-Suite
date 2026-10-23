<?php

declare(strict_types=1);

/**
 * CodeIgniter 4.7.5 updateBatch() when where() was already called.
 * The caller creates `item` and reads it again after this process exits.
 */

use CodeIgniter\Database\Exceptions\DatabaseException;

require dirname(__DIR__) . '/src/Boot.php';
require dirname(__DIR__) . '/src/Subject.php';

const EXPECTED_MESSAGE = 'updateBatch() cannot be safely combined with existing Query Builder WHERE conditions. '
    . 'Use updateBatch($data, $constraints), onConstraint(), or include all required constraint fields in the batch data.';

try {
    $observer = new mysqli(
        mpcs_env('MPCS_HOST'),
        mpcs_env('MPCS_USER'),
        mpcs_env('MPCS_PASSWORD'),
        mpcs_database(),
        (int) mpcs_env('MPCS_PORT'),
    );
    $observer->set_charset('utf8mb4');
    $debugOn = mpcs_open_ci4(true);
    $debugOff = mpcs_open_ci4(false);

    $result = [
        'versions' => mpcs_versions(),
        'chained_where_debug_on' => mpcs_batch_where($debugOn, $observer),
        'chained_where_debug_off' => mpcs_batch_where($debugOff, $observer),
        'reused_builder' => mpcs_batch_reuse($debugOn, $observer),
        'constraint_only' => mpcs_batch_constraint_only($debugOn, $observer),
        'composite_constraint' => mpcs_batch_composite($debugOn, $observer),
    ];
    echo json_encode($result, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), "\n";
} catch (Throwable $error) {
    fwrite(STDOUT, json_encode([
        'failed' => true,
        'class' => $error::class,
        'message' => $error->getMessage(),
        'file' => basename($error->getFile()),
        'line' => $error->getLine(),
    ], JSON_THROW_ON_ERROR) . "\n");
    exit(1);
}

/**
 * @return list<array{scope_id: string, code: string, label: string}>
 */
function mpcs_item_rows(mysqli $observer): array
{
    $result = $observer->query('SELECT scope_id, code, label FROM item ORDER BY scope_id, code');
    $rows = $result->fetch_all(MYSQLI_ASSOC);
    $result->free();

    return $rows;
}

function mpcs_reset_items(mysqli $observer): void
{
    $observer->query("UPDATE item SET label = CASE
        WHEN scope_id = 1 AND code = 'a' THEN 'alpha'
        WHEN scope_id = 2 AND code = 'a' THEN 'beta'
        WHEN scope_id = 1 AND code = 'b' THEN 'gamma'
    END");
}

/**
 * @return array<string, mixed>
 */
function mpcs_batch_where(CodeIgniter\Database\MySQLi\Connection $db, mysqli $observer): array
{
    mpcs_reset_items($observer);
    $beforeSql = mpcs_last_sql($db);
    $before = mpcs_item_rows($observer);
    $call = mpcs_call_batch($db->table('item')->where('scope_id', 1), [['code' => 'a', 'label' => 'changed']], 'code');

    return [
        'call' => $call,
        'sql_before' => $beforeSql,
        'sql_after' => mpcs_last_sql($db),
        'sql_unchanged' => $beforeSql === mpcs_last_sql($db),
        'rows_before' => $before,
        'rows_after' => mpcs_item_rows($observer),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_batch_reuse(CodeIgniter\Database\MySQLi\Connection $db, mysqli $observer): array
{
    mpcs_reset_items($observer);
    $builder = $db->table('item')->where('scope_id', 1);
    $first = mpcs_call_batch($builder, [['code' => 'a', 'label' => 'changed']], 'code');
    $second = mpcs_call_batch($builder, [['code' => 'a', 'label' => 'changed-again']], 'code');

    return [
        'first' => $first,
        'second_without_a_new_where' => $second,
        'rows_after' => mpcs_item_rows($observer),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_batch_constraint_only(CodeIgniter\Database\MySQLi\Connection $db, mysqli $observer): array
{
    mpcs_reset_items($observer);
    $call = mpcs_call_batch($db->table('item'), [['code' => 'a', 'label' => 'changed']], 'code');

    return [
        'call' => $call,
        'sql' => mpcs_last_sql($db),
        'rows_after' => mpcs_item_rows($observer),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_batch_composite(CodeIgniter\Database\MySQLi\Connection $db, mysqli $observer): array
{
    mpcs_reset_items($observer);
    $call = mpcs_call_batch(
        $db->table('item'),
        [['scope_id' => 1, 'code' => 'a', 'label' => 'only-scope-1']],
        ['scope_id', 'code'],
    );

    return [
        'call' => $call,
        'sql' => mpcs_last_sql($db),
        'rows_after' => mpcs_item_rows($observer),
    ];
}

/**
 * @param array<int, array<string, int|string>> $rows
 * @param array<int, string>|string             $constraint
 * @return array<string, mixed>
 */
function mpcs_call_batch(CodeIgniter\Database\BaseBuilder $builder, array $rows, array|string $constraint): array
{
    try {
        $returned = $builder->updateBatch($rows, $constraint);

        return ['threw' => false, 'returned' => $returned, 'class' => null, 'message' => null];
    } catch (DatabaseException $error) {
        return ['threw' => true, 'returned' => null, 'class' => $error::class, 'message' => $error->getMessage()];
    }
}

function mpcs_last_sql(CodeIgniter\Database\MySQLi\Connection $db): ?string
{
    $query = $db->getLastQuery();

    return $query === null ? null : (string) $query;
}
