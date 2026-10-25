<?php

/**
 * What a PDO connection looks like after commit(), for four endings, under whichever pdo_pgsql build runs
 * this script:
 * - commit: a healthy transaction;
 * - savepoint-recovery: a unique violation inside a savepoint, rolled back to it, then commit();
 * - rollback-tag: a unique violation caught outside any savepoint, then commit(); PostgreSQL answers
 *   COMMIT with ROLLBACK;
 * - deferred-fk: a deferred foreign key that fails at COMMIT; PostgreSQL answers COMMIT with an error.
 *
 * After each commit() it records the result, inTransaction(), what rollBack() then does, and whether a new
 * transaction on the same connection commits. A second connection checks every row.
 *
 *   PGHOST=... PGPORT=... PGDATABASE=... PGUSER=... PGPASSWORD=... php state-after-failure.php
 *
 * Creates and drops the tables cb_state, cb_parent and cb_child.
 */

$options = [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION];
$app = new PDO('pgsql:', null, null, $options);
$observer = new PDO('pgsql:', null, null, $options);
$app->exec('DROP TABLE IF EXISTS cb_state, cb_child, cb_parent');
$app->exec('CREATE TABLE cb_state (id int PRIMARY KEY)');
$app->exec('CREATE TABLE cb_parent (id int PRIMARY KEY)');
$app->exec('CREATE TABLE cb_child (id serial PRIMARY KEY, parent_id int NOT NULL REFERENCES cb_parent (id) DEFERRABLE INITIALLY DEFERRED)');
$app->exec('INSERT INTO cb_state VALUES (1)');

$oneLine = static fn (string $s): string => str_replace("\n", ' / ', trim($s));
$attempt = static function (callable $call) use ($oneLine): string {
    try {
        return 'returned '.var_export($call(), true);
    } catch (PDOException $e) {
        // PDO's own errors, such as "There is no active transaction", carry no errorInfo.
        return 'raised '.($e->errorInfo[0] ?? 'no SQLSTATE').' ('.$oneLine($e->getMessage()).')';
    }
};
$visible = static fn (int $id): int => (int) $observer->query("SELECT count(*) FROM cb_state WHERE id = $id")->fetchColumn();

$id = 10;
foreach (['commit', 'savepoint-recovery', 'rollback-tag', 'deferred-fk'] as $case) {
    $app->beginTransaction();
    $app->exec('INSERT INTO cb_state VALUES ('.(++$id).')');
    $row = $id;
    if ($case === 'savepoint-recovery') {
        $app->exec('SAVEPOINT s');
        try {
            $app->exec('INSERT INTO cb_state VALUES (1)');
        } catch (PDOException) {
            $app->exec('ROLLBACK TO SAVEPOINT s');
        }
    }
    if ($case === 'rollback-tag') {
        try {
            $app->exec('INSERT INTO cb_state VALUES (1)');
        } catch (PDOException) {
        }
    }
    if ($case === 'deferred-fk') {
        $app->exec('INSERT INTO cb_child (parent_id) VALUES (1)');
    }
    $commit = $attempt(fn () => $app->commit());
    $errorInfo = implode(' | ', array_map(fn ($v) => $oneLine((string) $v), $app->errorInfo()));
    $inTransaction = var_export($app->inTransaction(), true);
    $rollBack = $attempt(fn () => $app->rollBack());
    $next = $attempt(function () use ($app, &$id): bool {
        $app->beginTransaction();
        $app->exec('INSERT INTO cb_state VALUES ('.(++$id).')');

        return $app->commit();
    });
    printf(
        "%-18s commit() %s\n%-18s   errorInfo [%s]; inTransaction() %s; rollBack() %s\n%-18s   row visible %d; next transaction: %s, its row visible %d\n",
        $case, $commit, '', $errorInfo, $inTransaction, $rollBack, '', $visible($row), $next, $visible($id)
    );
}

$app->exec('DROP TABLE cb_state, cb_child, cb_parent');
echo 'PHP ', PHP_VERSION, ', pdo_pgsql ', phpversion('pdo_pgsql'), ', libpq ', $app->getAttribute(PDO::ATTR_CLIENT_VERSION), "\n";
