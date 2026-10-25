<?php

declare(strict_types=1);

/**
 * What PHP's native pgsql extension, and PDO's pgsql driver, let an application see when PostgreSQL
 * answers COMMIT with ROLLBACK. Two transactions on each API: one healthy, one aborted by a unique
 * violation before COMMIT. A second connection checks whether each transaction's row is visible.
 *
 *   PGHOST=127.0.0.1 PGPORT=55491 PGDATABASE=postgres PGUSER=postgres PGPASSWORD=... php commit-tag.php
 *
 * Connection settings come from libpq's environment variables. Creates and drops the table
 * cb_commit_tag. Needs the pgsql and pdo_pgsql extensions.
 */

const TRANSACTION_STATUS = [
    PGSQL_TRANSACTION_IDLE => 'IDLE',
    PGSQL_TRANSACTION_ACTIVE => 'ACTIVE',
    PGSQL_TRANSACTION_INTRANS => 'INTRANS',
    PGSQL_TRANSACTION_INERROR => 'INERROR',
    PGSQL_TRANSACTION_UNKNOWN => 'UNKNOWN',
];

/** One statement through pg_send_query(), so an error is returned rather than raised as a warning. */
function send(PgSql\Connection $c, string $sql): array
{
    pg_send_query($c, $sql);
    $result = pg_get_result($c);
    // Drain to the end of the results; until then libpq reports the connection as ACTIVE.
    while (pg_get_result($c) !== false) {
    }

    return [
        'status' => pg_result_status($result) === PGSQL_COMMAND_OK ? 'PGSQL_COMMAND_OK' : (string) pg_result_status($result),
        'tag' => pg_result_status($result, PGSQL_STATUS_STRING),
        'sqlstate' => pg_result_error_field($result, PGSQL_DIAG_SQLSTATE) ?: null,
    ];
}

$native = pg_connect('', PGSQL_CONNECT_FORCE_NEW);
$observer = pg_connect('', PGSQL_CONNECT_FORCE_NEW);
pg_query($native, 'DROP TABLE IF EXISTS cb_commit_tag');
pg_query($native, 'CREATE TABLE cb_commit_tag (id int PRIMARY KEY)');
pg_query($native, 'INSERT INTO cb_commit_tag VALUES (1)');
$visible = fn (int $id): int => (int) pg_fetch_result(pg_query($observer, "SELECT count(*) FROM cb_commit_tag WHERE id = $id"), 0, 0);

echo "pgsql extension, PHP ", PHP_VERSION, ", libpq ", pg_version($native)['client'], ", server ", pg_version($native)['server'], "\n";
foreach (['healthy' => 2, 'aborted' => 3] as $label => $id) {
    send($native, 'BEGIN');
    send($native, "INSERT INTO cb_commit_tag VALUES ($id)");
    $error = $label === 'aborted' ? send($native, 'INSERT INTO cb_commit_tag VALUES (1)')['sqlstate'] : null;
    $before = TRANSACTION_STATUS[pg_transaction_status($native)];
    $commit = send($native, 'COMMIT');
    printf(
        "  %-7s  statement error %-5s  status before COMMIT %-7s  COMMIT result %s, tag %s  status after %s  row visible %d\n",
        $label, $error ?? '-', $before, $commit['status'], $commit['tag'], TRANSACTION_STATUS[pg_transaction_status($native)], $visible($id)
    );
}

// The same aborted transaction through pg_query(), the API most applications call: does COMMIT return false?
pg_query($native, 'BEGIN');
pg_query($native, 'INSERT INTO cb_commit_tag VALUES (4)');
@pg_query($native, 'INSERT INTO cb_commit_tag VALUES (1)');
$result = pg_query($native, 'COMMIT');
printf("  pg_query('COMMIT') on the aborted transaction returned %s, tag %s, row visible %d\n",
    $result === false ? 'false' : get_class($result), pg_result_status($result, PGSQL_STATUS_STRING), $visible(4));

// PDO on the same server: what is visible between the caught error and COMMIT, and from commit().
// PDO::connect() returns the driver subclass, Pdo\Pgsql, so its driver-specific methods are listed too.
$pdo = PDO::connect('pgsql:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$methods = array_values(array_filter(
    get_class_methods($pdo),
    fn (string $m): bool => (bool) preg_match('/status|tag|transaction|cmd|result/i', $m)
));
echo "PDO (", $pdo::class, ", ", count(get_class_methods($pdo)), " methods), pdo_pgsql ", phpversion('pdo_pgsql'), "\n";
echo "  methods matching status|tag|transaction|cmd|result: ", implode(', ', $methods), "\n";
foreach (['healthy' => 5, 'aborted' => 6] as $label => $id) {
    $pdo->beginTransaction();
    $pdo->exec("INSERT INTO cb_commit_tag VALUES ($id)");
    if ($label === 'aborted') {
        try {
            $pdo->exec('INSERT INTO cb_commit_tag VALUES (1)');
        } catch (PDOException) {
        }
    }
    $inTransaction = $pdo->inTransaction();
    $connectionStatus = $pdo->getAttribute(PDO::ATTR_CONNECTION_STATUS);
    $commit = $pdo->commit();
    printf("  %-7s  inTransaction() %s  ATTR_CONNECTION_STATUS \"%s\"  commit() %s  row visible %d\n",
        $label, var_export($inTransaction, true), $connectionStatus, var_export($commit, true), $visible($id));
}

pg_query($native, 'DROP TABLE cb_commit_tag');
