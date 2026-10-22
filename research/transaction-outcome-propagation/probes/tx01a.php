<?php
// TX-01A through PDO. Prints one JSON object. Does not print the password.
$dsn = sprintf('pgsql:host=%s;port=%s;dbname=%s', getenv('PPCS_HOST'), getenv('PPCS_PORT'), getenv('PPCS_DATABASE'));
$pdo = new PDO($dsn, getenv('PPCS_USER'), getenv('PPCS_PASSWORD'), [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$marker = getenv('PPCS_MARKER');
$pdo->beginTransaction();
$statement = $pdo->prepare('insert into item (name) values (?)');
$statement->execute([$marker]);
$id = $pdo->query('select pg_current_xact_id()::text as xid, pg_backend_pid() as pid')->fetch(PDO::FETCH_ASSOC);
$sqlstate = null;
try {
    $pdo->exec("insert into uniq (code) values ('taken')");
} catch (Throwable $error) {
    $sqlstate = $error->getCode();
}
$commitThrew = false;
$commitReturn = null;
$commitMessage = null;
try {
    $commitReturn = $pdo->commit();
} catch (Throwable $error) {
    $commitThrew = true;
    $commitMessage = $error->getMessage();
}
echo json_encode([
    'xid' => $id['xid'] ?? null,
    'pid' => isset($id['pid']) ? (int) $id['pid'] : null,
    'sqlstate' => $sqlstate,
    'commit_threw' => $commitThrew,
    'commit_return' => $commitReturn,
    'commit_message' => $commitMessage === null ? null : substr($commitMessage, 0, 200),
    'pdo_driver' => $pdo->getAttribute(PDO::ATTR_DRIVER_NAME),
    'php' => PHP_VERSION,
], JSON_UNESCAPED_SLASHES), "\n";
