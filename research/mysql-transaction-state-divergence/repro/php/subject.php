<?php

declare(strict_types=1);

/**
 * The subject of one run. ../run.mjs creates a fresh schema, prepares the other session, then starts
 *
 *   php subject.php <scenario>
 *
 * and talks to it over stdin and stdout, one JSON object per line:
 * - {"type":"checkpoint",...}: the subject stops and waits for the line "resume". In between, Node reads the
 *   server from its own connections: the subject thread's transaction state, the visible markers and the sink;
 * - {"type":"notice","name":"blocking"}: sent just before a statement that should wait for a row lock.
 *   Node does not answer it, and polls for that lock wait while the subject is blocked;
 * - {"type":"result",...}: the last line.
 *
 * Two connections live in this process. The subject is Laravel's connection, or plain PDO for the pdo.*
 * scenarios. The sink is a separate autocommit PDO connection that only the callbacks use: a sink row stays
 * committed whatever happens to the subject's transaction, as a sent email or a queued job would.
 *
 * Nothing is injected. Every error is a real InnoDB lock-wait timeout (errno 1205), deadlock (1213) or
 * duplicate key (1062), produced by the other session that Node holds.
 */

require __DIR__.'/vendor/autoload.php';

use Composer\InstalledVersions;
use Illuminate\Container\Container;
use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseTransactionsManager;

const ALLOWED_HOST = '127.0.0.1';
const ALLOWED_PORTS = [13316, 13317];

const SCENARIOS = [
    'pdo.savepoint-1205.rollback-to',
    'pdo.savepoint-1205.skip',
    'pdo.savepoint-1213',
    'pdo.caught-1213.commit',
    'pdo.caught-1205.commit',
    'laravel.commit',
    'laravel.nested-1205-caught',
    'laravel.nested-1205-caught.server-timeout',
    'laravel.nested-1205-caught.outer-rollback',
    'laravel.nested-1205-escapes',
    'laravel.nested-explicit-1205',
    'laravel.nested-duplicate-caught',
    'laravel.caught-1213',
    'laravel.caught-1213-return',
    'laravel.nested-1213-caught',
    'laravel.explicit-caught-1213',
    'laravel.caught-1205-return',
    'laravel.escaped-1213',
    'laravel.escaped-1213-retry',
];

function env(string $name): string
{
    $value = getenv($name);
    if ($value === false || $value === '') {
        fwrite(STDERR, "missing environment variable $name\n");
        exit(2);
    }

    return $value;
}

function emit(array $message): void
{
    fwrite(STDOUT, json_encode($message, JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE | JSON_THROW_ON_ERROR)."\n");
    fflush(STDOUT);
}

/** @return array<string, mixed> class, code, SQLSTATE and errno where the driver gave them, and the cause chain */
function describe(Throwable $e): array
{
    $out = ['class' => $e::class, 'code' => $e->getCode(), 'message' => strtok($e->getMessage(), "\n")];
    if ($e instanceof PDOException && is_array($e->errorInfo)) {
        $out['sqlstate'] = $e->errorInfo[0] ?? null;
        $out['errno'] = $e->errorInfo[1] ?? null;
    }
    $chain = [];
    for ($cause = $e->getPrevious(); $cause !== null; $cause = $cause->getPrevious()) {
        $chain[] = [
            'class' => $cause::class,
            'code' => $cause->getCode(),
            'errno' => $cause instanceof PDOException && is_array($cause->errorInfo) ? ($cause->errorInfo[1] ?? null) : null,
        ];
    }
    $out['previous'] = $chain;

    return $out;
}

function pdoTo(string $database): PDO
{
    return new PDO(
        sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', env('MYSD_HOST'), (int) env('MYSD_PORT'), $database),
        env('MYSD_USER'),
        env('MYSD_PASSWORD'),
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
    );
}

final class Run
{
    /** @var list<array<string, mixed>> every call the scenario made, in order */
    public array $steps = [];

    /** @var list<string> the callbacks that ran, in order, as this process saw them */
    public array $fired = [];

    public ?Connection $db = null;

    public ?DatabaseTransactionsManager $manager = null;

    public ?PDO $pdo = null;

    private int $seq = 0;

    public function __construct(public readonly string $scenario, private readonly PDO $sink)
    {
    }

    /** A callback's side effect: a row that the sink's own connection writes and commits. */
    public function record(string $callback): void
    {
        $this->fired[] = $callback;
        $this->seq++;
        $this->sink->prepare('INSERT INTO callback_sink (seq, callback) VALUES (?, ?)')->execute([$this->seq, $callback]);
    }

    public function subjectPdo(): PDO
    {
        return $this->db?->getPdo() ?? $this->pdo;
    }

    /**
     * What this process knows without sending a statement. PDO::inTransaction() reads the server-status bit
     * that mysqlnd kept from the last OK packet; it is reported as such, not as the server's state.
     */
    public function state(): array
    {
        $state = ['pdo_in_transaction' => $this->subjectPdo()->inTransaction()];
        if ($this->db !== null) {
            $state['laravel_transaction_level'] = $this->db->transactionLevel();
            $state['manager'] = [
                'pending_levels' => $this->manager->getPendingTransactions()->map(fn ($t) => $t->level)->values()->all(),
                'committed_levels' => $this->manager->getCommittedTransactions()->map(fn ($t) => $t->level)->values()->all(),
            ];
        }

        return $state;
    }

    /**
     * Runs one call and records how it ended. Returns true when it returned and false when it raised. With
     * $rethrow the exception continues to the caller, which is how a statement error reaches Laravel's own
     * transaction handling; without it, this is the application's catch block.
     */
    public function call(string $step, callable $fn, bool $rethrow = false): bool
    {
        $levelBefore = $this->db?->transactionLevel();
        $started = hrtime(true);
        try {
            $value = $fn();
            $this->steps[] = [
                'step' => $step,
                'outcome' => 'returned',
                'value' => is_scalar($value) || $value === null ? $value : get_debug_type($value),
                'level_before' => $levelBefore,
                'level_after' => $this->db?->transactionLevel(),
                'pdo_in_transaction_after' => $this->subjectPdo()->inTransaction(),
                'elapsed_ms' => intdiv(hrtime(true) - $started, 1_000_000),
            ];

            return true;
        } catch (Throwable $e) {
            $this->steps[] = [
                'step' => $step,
                'outcome' => 'raised',
                'error' => describe($e),
                'level_before' => $levelBefore,
                'level_after' => $this->db?->transactionLevel(),
                'pdo_in_transaction_after' => $this->subjectPdo()->inTransaction(),
                'elapsed_ms' => intdiv(hrtime(true) - $started, 1_000_000),
            ];
            if ($rethrow) {
                throw $e;
            }

            return false;
        }
    }

    public function pause(string $name): void
    {
        emit(['type' => 'checkpoint', 'name' => $name, 'state' => $this->state(), 'fired' => $this->fired]);
        $line = fgets(STDIN);
        if ($line === false || trim($line) !== 'resume') {
            fwrite(STDERR, "the runner did not resume after $name\n");
            exit(3);
        }
    }

    public function notice(string $name, string $statement): void
    {
        emit(['type' => 'notice', 'name' => $name, 'statement' => $statement]);
    }
}

/**
 * A Laravel connection wired the way an application wires it. DatabaseServiceProvider binds db.transactions,
 * and DatabaseManager::configure then gives each connection that manager, which keeps the afterCommit and
 * afterRollBack callbacks. Capsule does not register the provider, so the binding is made here, on
 * Capsule's container, before the connection is created. The same wiring as the PostgreSQL study in
 * research/transaction-callbacks/laravel/scenario.php.
 */
function laravel(Run $run): void
{
    $capsule = new Capsule(new Container());
    $capsule->getContainer()->singleton('db.transactions', fn () => new DatabaseTransactionsManager());
    $capsule->addConnection([
        'driver' => 'mysql',
        'host' => env('MYSD_HOST'),
        'port' => (int) env('MYSD_PORT'),
        'database' => env('MYSD_DATABASE'),
        'username' => env('MYSD_USER'),
        'password' => env('MYSD_PASSWORD'),
        'charset' => 'utf8mb4',
        'collation' => 'utf8mb4_0900_ai_ci',
        'prefix' => '',
        'strict' => true,
        'engine' => null,
    ]);
    $run->db = $capsule->getConnection();
    $run->manager = $capsule->getContainer()->make('db.transactions');
}

function insertMarker(Connection $db, string $name): void
{
    $db->table('marker')->insert(['name' => $name]);
}

/** Waits on the row lock Node holds on lk, so the statement ends in errno 1205 after the 2 second wait. */
function waitOnHeldRow(Run $run, Connection $db): void
{
    $run->notice('blocking', 'update lk');
    $db->update('update lk set v = v + 1 where id = 1');
}

/**
 * The subject locks dl row 2, then waits on row 1, which Node's session already holds. At the checkpoint,
 * Node's session asks for row 2 and waits. The subject's request then closes the cycle. Node's session wrote
 * eight more rows first, so InnoDB picks the subject as the victim.
 */
function deadlockOn(Run $run, Connection $db, bool $rethrow): void
{
    $run->call('take row 2', fn () => $db->update('update dl set v = v + 1 where id = 2'), true);
    $run->pause('holding-row-2');
    $run->call('trigger', fn () => $db->update('update dl set v = v + 1 where id = 1'), $rethrow);
}

function callbacks(Run $run, Connection $db, string $label): void
{
    $db->afterCommit(fn () => $run->record("afterCommit:$label"));
    $db->afterRollBack(fn () => $run->record("afterRollBack:$label"));
}

/** Every Laravel scenario ends the same way: one more transaction on the same connection and manager. */
function nextTransaction(Run $run): void
{
    $run->pause('after-end');
    $run->call('next transaction', fn () => $run->db->transaction(function (Connection $tx) use ($run): void {
        callbacks($run, $tx, 'next');
        insertMarker($tx, 'next');
    }));
}

/** DB::transaction() writes one marker and returns. The control. */
function laravelCommit(Run $run): void
{
    $run->call('main', fn () => $run->db->transaction(function (Connection $tx) use ($run): string {
        callbacks($run, $tx, 'tx');
        insertMarker($tx, 'tx');

        return 'closure returned';
    }));
    nextTransaction($run);
}

/**
 * An outer DB::transaction() runs an inner DB::transaction(), a savepoint, whose last statement fails. By
 * variant:
 * - 1205-caught: the inner statement waits on the held row until errno 1205. The outer closure catches the
 *   exception from the inner transaction, writes one more marker and returns;
 * - 1205-escapes: the same, but the outer closure does not catch, so the exception leaves both closures;
 * - duplicate-caught: the inner statement is a duplicate key (1062) instead, caught the same way;
 * - 1213-caught: the inner statement is the deadlock victim (1213), caught the same way.
 */
function laravelNested(Run $run, string $variant): void
{
    $run->call('main', fn () => $run->db->transaction(function (Connection $tx) use ($run, $variant): string {
        callbacks($run, $tx, 'outer');
        $run->call('insert outer', fn () => insertMarker($tx, 'outer'), true);
        $inner = fn () => $tx->transaction(function (Connection $tx2) use ($run, $variant): void {
            callbacks($run, $tx2, 'inner');
            $run->call('insert inner', fn () => insertMarker($tx2, 'inner'), true);
            match ($variant) {
                '1205-caught', '1205-escapes' => $run->call('trigger', fn () => waitOnHeldRow($run, $tx2), true),
                'duplicate-caught' => $run->call('trigger', fn () => $tx2->table('uniq_row')->insert(['code' => 'taken']), true),
                '1213-caught' => deadlockOn($run, $tx2, true),
            };
        });
        if ($variant === '1205-escapes') {
            $run->call('inner transaction', $inner, true);

            return 'not reached';
        }
        $run->call('inner transaction', $inner);
        $run->pause('after-error');
        $run->call('insert after', fn () => insertMarker($tx, 'after'), true);
        $run->pause('after-continue');

        return 'closure returned';
    }));
    nextTransaction($run);
}

/**
 * The outer transaction rolls back explicitly after catching the inner timeout: DB::beginTransaction(), an inner
 * DB::transaction() whose statement waits on the held row until 1205, the application's catch, then
 * DB::rollBack().
 */
function laravelNestedOuterRollback(Run $run): void
{
    $db = $run->db;
    $run->call('begin', fn () => $db->beginTransaction(), true);
    callbacks($run, $db, 'outer');
    $run->call('insert outer', fn () => insertMarker($db, 'outer'), true);
    $run->call('inner transaction', fn () => $db->transaction(function (Connection $tx2) use ($run): void {
        callbacks($run, $tx2, 'inner');
        $run->call('insert inner', fn () => insertMarker($tx2, 'inner'), true);
        $run->call('trigger', fn () => waitOnHeldRow($run, $tx2), true);
    }));
    $run->pause('after-error');
    $run->call('main', fn () => $db->rollBack());
    nextTransaction($run);
}

/**
 * The same savepoint through the explicit API inside an outer DB::transaction(): beginTransaction() at level 2,
 * then, when the statement fails with 1205, the application's catch calls rollBack() to level 1.
 */
function laravelNestedExplicit(Run $run): void
{
    $run->call('main', fn () => $run->db->transaction(function (Connection $tx) use ($run): string {
        callbacks($run, $tx, 'outer');
        $run->call('insert outer', fn () => insertMarker($tx, 'outer'), true);
        $run->call('begin inner', fn () => $tx->beginTransaction(), true);
        callbacks($run, $tx, 'inner');
        $run->call('insert inner', fn () => insertMarker($tx, 'inner'), true);
        if ($run->call('trigger', fn () => waitOnHeldRow($run, $tx))) {
            $run->call('commit inner', fn () => $tx->commit(), true);
        } else {
            $run->call('roll back inner', fn () => $tx->rollBack(), true);
        }
        $run->pause('after-error');
        $run->call('insert after', fn () => insertMarker($tx, 'after'), true);
        $run->pause('after-continue');

        return 'closure returned';
    }));
    nextTransaction($run);
}

/**
 * One DB::transaction() whose statement fails, caught inside the closure. By variant:
 * - caught-1213: deadlock victim, then one more marker, then return;
 * - caught-1213-return: deadlock victim, then return with no further statement;
 * - caught-1205-return: lock-wait timeout, then return with no further statement.
 */
function laravelCaught(Run $run, string $variant): void
{
    $run->call('main', fn () => $run->db->transaction(function (Connection $tx) use ($run, $variant): string {
        callbacks($run, $tx, 'tx');
        $run->call('insert tx', fn () => insertMarker($tx, 'tx'), true);
        if ($variant === 'caught-1205-return') {
            $run->call('trigger', fn () => waitOnHeldRow($run, $tx));
        } else {
            deadlockOn($run, $tx, false);
        }
        $run->pause('after-error');
        if ($variant === 'caught-1213') {
            $run->call('insert after', fn () => insertMarker($tx, 'after'), true);
            $run->pause('after-continue');
        }

        return 'closure returned';
    }));
    nextTransaction($run);
}

/**
 * DB::beginTransaction() and DB::commit() in the shape the Laravel documentation gives for manual
 * transactions: a failure of commit() reaches a catch block that calls DB::rollBack(). Inside, the application
 * catches the deadlock error and writes one more marker.
 */
function laravelExplicitCaught(Run $run): void
{
    $db = $run->db;
    $run->call('begin', fn () => $db->beginTransaction(), true);
    callbacks($run, $db, 'tx');
    $run->call('insert tx', fn () => insertMarker($db, 'tx'), true);
    deadlockOn($run, $db, false);
    $run->pause('after-error');
    $run->call('insert after', fn () => insertMarker($db, 'after'), true);
    $run->pause('after-continue');
    if (!$run->call('main', fn () => $db->commit())) {
        $run->call('roll back', fn () => $db->rollBack());
    }
    nextTransaction($run);
}

/**
 * The deadlock error leaves the closure. With one attempt it reaches the caller. With two, the closure runs
 * again; the second attempt only writes its marker.
 */
function laravelEscaped(Run $run, int $attempts): void
{
    $attempt = 0;
    $run->call('main', fn () => $run->db->transaction(function (Connection $tx) use ($run, &$attempt): string {
        $attempt++;
        $label = "attempt-$attempt";
        callbacks($run, $tx, $label);
        $run->call("insert $label", fn () => insertMarker($tx, $label), true);
        if ($attempt === 1) {
            deadlockOn($run, $tx, true);
        }

        return "closure returned on attempt $attempt";
    }, $attempts));
    nextTransaction($run);
}

/**
 * Plain PDO with the statements Laravel's MySQL grammar would send for a savepoint: START TRANSACTION,
 * SAVEPOINT trans2, and, by mode, ROLLBACK TO SAVEPOINT trans2 after the failure or nothing.
 */
function pdoSavepoint(Run $run, string $trigger, bool $rollbackTo): void
{
    $pdo = $run->pdo;
    $run->call('begin', fn () => $pdo->beginTransaction(), true);
    $run->call('insert outer', fn () => $pdo->exec("INSERT INTO marker (name) VALUES ('outer')"), true);
    $run->call('savepoint', fn () => $pdo->exec('SAVEPOINT trans2'), true);
    $run->call('insert inner', fn () => $pdo->exec("INSERT INTO marker (name) VALUES ('inner')"), true);
    pdoTrigger($run, $trigger);
    $run->pause('after-error');
    if ($rollbackTo) {
        $run->call('rollback to savepoint', fn () => $pdo->exec('ROLLBACK TO SAVEPOINT trans2'));
    }
    $run->call('insert after', fn () => $pdo->exec("INSERT INTO marker (name) VALUES ('after')"));
    $run->pause('after-continue');
    $run->call('main', fn () => $pdo->commit());
}

/** Plain PDO: one marker, the failing statement caught, then commit() with no statement in between. */
function pdoCaughtCommit(Run $run, string $trigger): void
{
    $pdo = $run->pdo;
    $run->call('begin', fn () => $pdo->beginTransaction(), true);
    $run->call('insert tx', fn () => $pdo->exec("INSERT INTO marker (name) VALUES ('tx')"), true);
    pdoTrigger($run, $trigger);
    $run->pause('after-error');
    $run->call('main', fn () => $pdo->commit());
}

function pdoTrigger(Run $run, string $trigger): void
{
    $pdo = $run->pdo;
    if ($trigger === '1205') {
        $run->call('trigger', function () use ($run, $pdo) {
            $run->notice('blocking', 'update lk');

            return $pdo->exec('UPDATE lk SET v = v + 1 WHERE id = 1');
        });

        return;
    }
    $run->call('take row 2', fn () => $pdo->exec('UPDATE dl SET v = v + 1 WHERE id = 2'), true);
    $run->pause('holding-row-2');
    $run->call('trigger', fn () => $pdo->exec('UPDATE dl SET v = v + 1 WHERE id = 1'));
}

[, $scenario] = $argv + [null, null];
if (!in_array($scenario, SCENARIOS, true)) {
    fwrite(STDERR, "usage: php subject.php <scenario>\n");
    exit(2);
}
// Another project's MySQL listens on 3306 on this machine. Refuse anything but this study's two servers.
if (env('MYSD_HOST') !== ALLOWED_HOST || !in_array((int) env('MYSD_PORT'), ALLOWED_PORTS, true)) {
    fwrite(STDERR, "refusing to connect outside this study's servers\n");
    exit(2);
}

// The lock wait is shortened to 2 seconds per session unless MYSD_LOCK_WAIT is server-default (50 seconds).
$lockWait = env('MYSD_LOCK_WAIT');
if ($lockWait !== 'server-default' && $lockWait !== '2') {
    fwrite(STDERR, "MYSD_LOCK_WAIT must be 2 or server-default\n");
    exit(2);
}
$sink = pdoTo(env('MYSD_DATABASE'));
$run = new Run($scenario, $sink);
if (str_starts_with($scenario, 'laravel.')) {
    laravel($run);
    $subjectId = (int) $run->db->selectOne('select connection_id() as id')->id;
    if ($lockWait === '2') {
        $run->db->unprepared('set session innodb_lock_wait_timeout = 2');
    }
} else {
    $run->pdo = pdoTo(env('MYSD_DATABASE'));
    $subjectId = (int) $run->pdo->query('SELECT CONNECTION_ID()')->fetchColumn();
    if ($lockWait === '2') {
        $run->pdo->exec('SET SESSION innodb_lock_wait_timeout = 2');
    }
}
$sinkId = (int) $sink->query('SELECT CONNECTION_ID()')->fetchColumn();
emit(['type' => 'hello', 'subject_connection_id' => $subjectId, 'sink_connection_id' => $sinkId]);
if (trim((string) fgets(STDIN)) !== 'resume') {
    exit(3);
}

match ($scenario) {
    'pdo.savepoint-1205.rollback-to' => pdoSavepoint($run, '1205', true),
    'pdo.savepoint-1205.skip' => pdoSavepoint($run, '1205', false),
    'pdo.savepoint-1213' => pdoSavepoint($run, '1213', true),
    'pdo.caught-1213.commit' => pdoCaughtCommit($run, '1213'),
    'pdo.caught-1205.commit' => pdoCaughtCommit($run, '1205'),
    'laravel.commit' => laravelCommit($run),
    'laravel.nested-1205-caught', 'laravel.nested-1205-caught.server-timeout' => laravelNested($run, '1205-caught'),
    'laravel.nested-1205-caught.outer-rollback' => laravelNestedOuterRollback($run),
    'laravel.nested-1205-escapes' => laravelNested($run, '1205-escapes'),
    'laravel.nested-explicit-1205' => laravelNestedExplicit($run),
    'laravel.nested-duplicate-caught' => laravelNested($run, 'duplicate-caught'),
    'laravel.caught-1213' => laravelCaught($run, 'caught-1213'),
    'laravel.caught-1213-return' => laravelCaught($run, 'caught-1213-return'),
    'laravel.nested-1213-caught' => laravelNested($run, '1213-caught'),
    'laravel.explicit-caught-1213' => laravelExplicitCaught($run),
    'laravel.caught-1205-return' => laravelCaught($run, 'caught-1205-return'),
    'laravel.escaped-1213' => laravelEscaped($run, 1),
    'laravel.escaped-1213-retry' => laravelEscaped($run, 2),
};
$run->pause('final');

$subjectPdo = $run->subjectPdo();
emit([
    'type' => 'result',
    'scenario' => $scenario,
    'steps' => $run->steps,
    'fired' => $run->fired,
    'state' => $run->state(),
    'versions' => [
        'php' => PHP_VERSION,
        'pdo_mysql_client' => $subjectPdo->getAttribute(PDO::ATTR_CLIENT_VERSION),
        'server' => $subjectPdo->getAttribute(PDO::ATTR_SERVER_VERSION),
        'illuminate/database' => InstalledVersions::getPrettyVersion('illuminate/database'),
        'illuminate/database_reference' => InstalledVersions::getReference('illuminate/database'),
    ],
]);
