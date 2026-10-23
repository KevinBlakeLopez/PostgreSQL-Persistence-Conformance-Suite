<?php

declare(strict_types=1);

/**
 * CodeIgniter Model allowedFields, then the same update inside a failed transaction.
 * Prints one JSON object and waits for "go" before closing the connection.
 */

require dirname(__DIR__) . '/src/DdlBoot.php';
require dirname(__DIR__) . '/src/ItemModel.php';

use App\Models\ItemModel;
use CodeIgniter\Database\Exceptions\DataException;

$scenario = $argv[1] ?? '';

try {
    $db = mpcs_model_connection();
    $other = mpcs_model_other();
    $model = new ItemModel($db);
    $model->skipValidation(true);
    $payload = match ($scenario) {
        'update-mixed' => mpcs_model_mixed($db, $other, $model, false),
        'save-mixed' => mpcs_model_mixed($db, $other, $model, true),
        'update-omitted-only' => mpcs_model_omitted($db, $other, $model),
        'update-then-rollback' => mpcs_model_rollback($db, $other, $model),
        default => throw new InvalidArgumentException('Unknown scenario'),
    };
    $payload['scenario'] = $scenario;
    $payload['allowed_fields'] = ['label'];
    $payload['skip_validation'] = true;
    $payload['connection_id'] = $db->connID->thread_id;
    $payload['versions'] = mpcs_versions();
    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    fflush(STDOUT);
    while (($line = fgets(STDIN)) !== false) {
        if (trim($line) === 'go') {
            break;
        }
    }
    $db->close();
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

function mpcs_model_connection(): CodeIgniter\Database\MySQLi\Connection
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

    return $db;
}

function mpcs_model_other(): mysqli
{
    $db = new mysqli(mpcs_env('MPCS_HOST'), mpcs_env('MPCS_USER'), mpcs_env('MPCS_PASSWORD'), mpcs_database(), (int) mpcs_env('MPCS_PORT'));
    $db->set_charset('utf8mb4');

    return $db;
}

/**
 * @return array{id: string, label: string, secret: string}
 */
function mpcs_model_row(mysqli $db): array
{
    $row = $db->query('SELECT id, label, secret FROM item WHERE id = 1')->fetch_assoc();

    return $row;
}

/**
 * @return array<string, mixed>
 */
function mpcs_model_mixed(CodeIgniter\Database\MySQLi\Connection $db, mysqli $other, ItemModel $model, bool $save): array
{
    $before = mpcs_model_row($other);
    $call = mpcs_model_call($model, $save, ['id' => 1, 'label' => 'beta', 'secret' => 'changed']);

    return [
        'call' => $call,
        'sql' => mpcs_model_last_sql($db),
        'row_before' => $before,
        'row_after' => mpcs_model_row($other),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_model_omitted(CodeIgniter\Database\MySQLi\Connection $db, mysqli $other, ItemModel $model): array
{
    $before = mpcs_model_row($other);
    $sqlBefore = mpcs_model_last_sql($db);
    $call = mpcs_model_call($model, false, ['secret' => 'changed']);

    return [
        'call' => $call,
        'sql_before' => $sqlBefore,
        'sql_after' => mpcs_model_last_sql($db),
        'row_before' => $before,
        'row_after' => mpcs_model_row($other),
    ];
}

/**
 * @return array<string, mixed>
 */
function mpcs_model_rollback(CodeIgniter\Database\MySQLi\Connection $db, mysqli $other, ItemModel $model): array
{
    $db->transStart();
    $call = mpcs_model_call($model, false, ['id' => 1, 'label' => 'gamma', 'secret' => 'changed']);
    $otherBefore = mpcs_model_row($other);
    $duplicate = $db->query("INSERT INTO uniq_row (code) VALUES ('taken')");
    $duplicateError = $db->error();
    $complete = $db->transComplete();

    return [
        'call' => $call,
        'sql' => mpcs_model_last_sql($db),
        'other_before_complete' => $otherBefore,
        'duplicate_returned' => $duplicate,
        'duplicate_error_code' => $duplicateError['code'] ?? null,
        'complete' => $complete,
        'row_after' => mpcs_model_row($other),
    ];
}

/**
 * @param array<string, int|string> $data
 * @return array<string, mixed>
 */
function mpcs_model_call(ItemModel $model, bool $save, array $data): array
{
    try {
        $returned = $save ? $model->save($data) : $model->update($data['id'] ?? 1, $data);

        return ['threw' => false, 'returned' => $returned === true, 'class' => null, 'message' => null];
    } catch (DataException $error) {
        return ['threw' => true, 'returned' => false, 'class' => $error::class, 'message' => $error->getMessage()];
    }
}

function mpcs_model_last_sql(CodeIgniter\Database\MySQLi\Connection $db): ?string
{
    $query = $db->getLastQuery();

    return $query === null ? null : (string) $query;
}
