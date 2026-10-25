<?php

/**
 * PDO::commit() returns true when PostgreSQL answers COMMIT with ROLLBACK.
 *
 * A unique violation aborts the transaction. The application catches the exception and calls commit().
 * PostgreSQL rolls the transaction back and answers COMMIT with the command tag ROLLBACK. PDO::commit()
 * returns true, as it does for the healthy transaction, and the transaction's row is not committed.
 *
 *   PGHOST=127.0.0.1 PGPORT=5432 PGDATABASE=postgres PGUSER=postgres PGPASSWORD=secret php pdo-commit-rollback.php
 *
 * Needs only pdo_pgsql. Connection settings come from libpq's environment variables. Creates and drops
 * the table pdo_commit_rollback. A second connection checks whether each transaction's row is visible.
 */

$options = [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION];
$app = new PDO('pgsql:', null, null, $options);
$observer = new PDO('pgsql:', null, null, $options);

$app->exec('DROP TABLE IF EXISTS pdo_commit_rollback');
$app->exec('CREATE TABLE pdo_commit_rollback (id int PRIMARY KEY)');
$app->exec('INSERT INTO pdo_commit_rollback VALUES (1)');

foreach (['healthy' => 2, 'aborted' => 3] as $label => $id) {
    $app->beginTransaction();
    $app->exec("INSERT INTO pdo_commit_rollback VALUES ($id)");
    if ($label === 'aborted') {
        try {
            $app->exec('INSERT INTO pdo_commit_rollback VALUES (1)');
        } catch (PDOException $e) {
            echo "$label: caught SQLSTATE {$e->errorInfo[0]}\n";
        }
    }
    $returned = $app->commit();
    $visible = $observer->query("SELECT count(*) FROM pdo_commit_rollback WHERE id = $id")->fetchColumn();
    echo "$label: commit() returned ", var_export($returned, true), ", row $id visible to another connection: $visible\n";
}

$app->exec('DROP TABLE pdo_commit_rollback');
echo 'PHP ', PHP_VERSION, ', pdo_pgsql ', phpversion('pdo_pgsql'), ', libpq ', $app->getAttribute(PDO::ATTR_CLIENT_VERSION),
    ', server ', $app->getAttribute(PDO::ATTR_SERVER_VERSION), "\n";
