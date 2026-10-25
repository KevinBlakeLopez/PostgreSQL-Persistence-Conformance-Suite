<?php

declare(strict_types=1);

/**
 * One repetition of one scenario. run.mjs creates a fresh database, then runs:
 *
 *   php scenario.php <scenario> <repetition>
 *
 * Three connections:
 * - the subject: Laravel's connection, or plain PDO for the pdo.* scenarios. It connects through the wire
 *   recorder (CB_SUBJECT_PORT), which reports the server's CommandComplete tags;
 * - the observer, straight to PostgreSQL (CB_DIRECT_PORT): the transaction's fate from pg_xact_status(),
 *   the marker's visibility, and the subject's session state;
 * - the sink, straight to PostgreSQL: the callbacks' only side effect, an autocommit INSERT into
 *   callback_log. A row there stays committed whatever happens to the subject's transaction, as a sent
 *   email or a queued job would.
 *
 * Neither the observer nor the sink takes part in the subject's transaction. No fault is injected: the
 * error is a real unique violation. Prints one JSON object.
 */

require dirname(__DIR__, 3).'/adapters/php/vendor/autoload.php';

use Composer\InstalledVersions;
use Illuminate\Container\Container;
use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseTransactionsManager;
use Illuminate\Database\UniqueConstraintViolationException;

const SCENARIOS = [
    'laravel.commit',
    'laravel.error-escapes',
    'laravel.caught-error',
    'laravel.explicit-caught-error',
    'laravel.savepoint-recovery',
    'laravel.deferred-fk',
    'laravel.explicit-deferred-fk',
    'pdo.commit',
    'pdo.caught-error',
    'pdo.deferred-fk',
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

function dsn(int $port, string $applicationName): string
{
    return sprintf(
        'pgsql:host=%s;port=%d;dbname=%s;application_name=%s;sslmode=disable',
        env('CB_HOST'), $port, env('CB_DATABASE'), $applicationName
    );
}

function directPdo(string $applicationName): PDO
{
    return new PDO(dsn((int) env('CB_DIRECT_PORT'), $applicationName), env('CB_USER'), env('CB_PASSWORD'), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    ]);
}

/** @return array{class: string, sqlstate: ?string, message: string} */
function describe(Throwable $e): array
{
    return [
        'class' => $e::class,
        'sqlstate' => $e instanceof PDOException ? ($e->errorInfo[0] ?? null) : null,
        'message' => explode("\n", $e->getMessage())[0],
    ];
}

final class Run
{
    /** @var list<string> the callbacks that ran, in order, as this process saw them */
    public array $fired = [];

    /** @var array<string, array<string, mixed>> */
    public array $checkpoints = [];

    /** @var array<string, string> transaction IDs, each captured inside its transaction */
    public array $xids = [];

    public ?int $pid = null;

    public readonly int $observerPid;

    public readonly int $sinkPid;

    public function __construct(
        public readonly string $scenario,
        public readonly int $rep,
        private readonly PDO $observer,
        private readonly PDO $sink,
    ) {
        $this->observerPid = (int) $observer->query('select pg_backend_pid()')->fetchColumn();
        $this->sinkPid = (int) $sink->query('select pg_backend_pid()')->fetchColumn();
    }

    public function name(string $suffix): string
    {
        return "cb-{$this->scenario}-r{$this->rep}-{$suffix}";
    }

    /** A callback's side effect: a row that the sink's own connection writes and commits. */
    public function record(string $event): void
    {
        $this->fired[] = $event;
        $this->sink->prepare('insert into callback_log (scenario, rep, event) values (?, ?, ?)')
            ->execute([$this->scenario, $this->rep, $event]);
    }

    /** What the independent observer sees at this moment. */
    public function checkpoint(string $name, array $markers): void
    {
        $seen = [];
        $session = $this->observer->prepare('select application_name, state, backend_xid::text as backend_xid, query from pg_stat_activity where pid = ?');
        $session->execute([$this->pid]);
        $seen['session'] = $session->fetch(PDO::FETCH_ASSOC) ?: null;
        foreach ($this->xids as $label => $xid) {
            $fate = $this->observer->prepare('select pg_xact_status(?::xid8)');
            $fate->execute([$xid]);
            $seen['xact_status'][$label] = $fate->fetchColumn();
        }
        foreach ($markers as $marker) {
            $count = $this->observer->prepare('select count(*) as n, min(xmin::text) as xmin from item where name = ?');
            $count->execute([$marker]);
            $row = $count->fetch(PDO::FETCH_ASSOC);
            $seen['markers'][$marker] = (int) $row['n'];
            if ((int) $row['n'] > 0) {
                $seen['marker_xmin'][$marker] = $row['xmin'];
            }
        }
        $log = $this->observer->prepare('select event from callback_log where scenario = ? and rep = ? order by id');
        $log->execute([$this->scenario, $this->rep]);
        $seen['callback_log'] = $log->fetchAll(PDO::FETCH_COLUMN);
        $this->checkpoints[$name] = $seen;
    }
}

/**
 * A Laravel connection wired the way an application wires it. DatabaseServiceProvider binds
 * db.transactions, and DatabaseManager::configure then gives each connection that manager, which keeps
 * the afterCommit and afterRollBack callbacks. Capsule does not register the provider, so the binding is
 * made here, on Capsule's container, before the connection is created.
 *
 * @return array{Connection, DatabaseTransactionsManager}
 */
function laravel(Run $run): array
{
    $capsule = new Capsule(new Container());
    $capsule->getContainer()->singleton('db.transactions', fn () => new DatabaseTransactionsManager());
    $capsule->addConnection([
        'driver' => 'pgsql',
        'host' => env('CB_HOST'),
        'port' => (int) env('CB_SUBJECT_PORT'),
        'database' => env('CB_DATABASE'),
        'username' => env('CB_USER'),
        'password' => env('CB_PASSWORD'),
        'charset' => 'utf8',
        'prefix' => '',
        'sslmode' => 'disable',
        'application_name' => $run->name('subject'),
    ]);
    $db = $capsule->getConnection();
    $run->pid = (int) $db->selectOne('select pg_backend_pid() as pid')->pid;

    return [$db, $capsule->getContainer()->make('db.transactions')];
}

function currentXid(Connection|PDO $subject): string
{
    if ($subject instanceof PDO) {
        return (string) $subject->query('select pg_current_xact_id()::text')->fetchColumn();
    }

    return (string) $subject->selectOne('select pg_current_xact_id()::text as xid')->xid;
}

/** @return array{pending: int, committed: int} the manager's records left after the scenario */
function managerState(DatabaseTransactionsManager $manager): array
{
    return [
        'pending' => $manager->getPendingTransactions()->count(),
        'committed' => $manager->getCommittedTransactions()->count(),
    ];
}

/**
 * DB::transaction(). The closure registers both callbacks, writes the marker, then, by variant:
 * - commit: returns;
 * - error-escapes: inserts the duplicate and lets the unique violation leave the closure;
 * - caught-error: inserts the duplicate, catches the unique violation, and returns;
 * - savepoint-recovery: inserts the duplicate inside a nested DB::transaction() (a savepoint) that has its
 *   own callbacks, catches the violation outside it, and returns;
 * - deferred-fk: inserts a child row whose parent does not exist, under a DEFERRABLE INITIALLY DEFERRED
 *   foreign key, and returns. Nothing fails until PostgreSQL checks the key at COMMIT.
 * caught-error and deferred-fk are followed by a second transaction on the same connection and manager.
 */
function managed(Run $run, string $variant): array
{
    [$db, $manager] = laravel($run);
    $marker = $run->name('tx');
    $caught = null;
    try {
        $value = $db->transaction(function (Connection $tx) use ($run, $variant, $marker, &$caught): string {
            $tx->afterCommit(fn () => $run->record('afterCommit'));
            $tx->afterRollBack(fn () => $run->record('afterRollBack'));
            $tx->table('item')->insert(['name' => $marker, 'qty' => 0]);
            $run->xids['tx'] = currentXid($tx);
            switch ($variant) {
                case 'commit':
                    break;
                case 'error-escapes':
                    $run->checkpoint('before-end', [$marker]);
                    $tx->table('uniq')->insert(['code' => 'taken']);
                    break;
                case 'caught-error':
                    try {
                        $tx->table('uniq')->insert(['code' => 'taken']);
                    } catch (UniqueConstraintViolationException $e) {
                        $caught = describe($e);
                    }
                    break;
                case 'savepoint-recovery':
                    try {
                        $tx->transaction(function (Connection $inner) use ($run): void {
                            $inner->afterCommit(fn () => $run->record('afterCommit:inner'));
                            $inner->afterRollBack(fn () => $run->record('afterRollBack:inner'));
                            $inner->table('uniq')->insert(['code' => 'taken']);
                        });
                    } catch (UniqueConstraintViolationException $e) {
                        $caught = describe($e);
                    }
                    break;
                case 'deferred-fk':
                    $tx->table('child')->insert(['parent_id' => 1]);
                    break;
            }
            $run->checkpoint('before-end', [$marker]);

            return 'closure returned';
        });
        $api = ['outcome' => 'returned', 'value' => $value];
    } catch (Throwable $e) {
        $api = ['outcome' => 'raised'] + describe($e);
    }
    $run->checkpoint('after-end', [$marker]);
    $result = ['caught' => $caught, 'api' => $api, 'manager_after_end' => managerState($manager)];

    // Recovery control: the same connection and manager run one more transaction.
    if ($variant === 'caught-error' || $variant === 'deferred-fk') {
        $reuse = $run->name('reuse');
        $db->transaction(function (Connection $tx) use ($run, $reuse): void {
            $tx->afterCommit(fn () => $run->record('afterCommit:reuse'));
            $tx->table('item')->insert(['name' => $reuse, 'qty' => 0]);
            $run->xids['reuse'] = currentXid($tx);
        });
        $run->checkpoint('after-reuse', [$marker, $reuse]);
    }
    $result['manager_after'] = managerState($manager);

    return $result;
}

/**
 * DB::beginTransaction() and DB::commit(). By variant:
 * - caught-error: the duplicate is inserted and its exception caught between them;
 * - deferred-fk: a child row with a missing parent is inserted, and COMMIT fails. The application then
 *   calls DB::rollBack(), as a manual transaction's catch block usually does, and a second transaction
 *   runs on the same connection and manager.
 */
function explicit(Run $run, string $variant): array
{
    [$db, $manager] = laravel($run);
    $marker = $run->name('tx');
    $caught = null;
    $db->beginTransaction();
    $db->afterCommit(fn () => $run->record('afterCommit'));
    $db->afterRollBack(fn () => $run->record('afterRollBack'));
    $db->table('item')->insert(['name' => $marker, 'qty' => 0]);
    $run->xids['tx'] = currentXid($db);
    if ($variant === 'caught-error') {
        try {
            $db->table('uniq')->insert(['code' => 'taken']);
        } catch (UniqueConstraintViolationException $e) {
            $caught = describe($e);
        }
    } else {
        $db->table('child')->insert(['parent_id' => 1]);
    }
    $run->checkpoint('before-end', [$marker]);
    $rollBack = null;
    try {
        $db->commit();
        $api = ['outcome' => 'returned'];
    } catch (Throwable $e) {
        $api = ['outcome' => 'raised'] + describe($e);
        if ($variant === 'deferred-fk') {
            $levelBefore = $db->transactionLevel();
            $db->rollBack();
            $rollBack = ['level_before' => $levelBefore, 'level_after' => $db->transactionLevel()];
        }
    }
    $run->checkpoint('after-end', [$marker]);
    $result = ['caught' => $caught, 'api' => $api, 'roll_back_after_failed_commit' => $rollBack, 'manager_after_end' => managerState($manager)];

    if ($variant === 'deferred-fk') {
        $reuse = $run->name('reuse');
        $db->transaction(function (Connection $tx) use ($run, $reuse): void {
            $tx->afterCommit(fn () => $run->record('afterCommit:reuse'));
            $tx->table('item')->insert(['name' => $reuse, 'qty' => 0]);
            $run->xids['reuse'] = currentXid($tx);
        });
        $run->checkpoint('after-reuse', [$marker, $reuse]);
    }
    $result['manager_after'] = managerState($manager);

    return $result;
}

/**
 * Plain PDO, no Laravel: the driver half. commit is the control. caught-error inserts the duplicate and
 * catches its exception before commit(). deferred-fk inserts a child row with a missing parent, so COMMIT
 * itself fails.
 */
function pdo(Run $run, string $variant): array
{
    $pdo = new PDO(dsn((int) env('CB_SUBJECT_PORT'), $run->name('subject')), env('CB_USER'), env('CB_PASSWORD'), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    ]);
    $run->pid = (int) $pdo->query('select pg_backend_pid()')->fetchColumn();
    $marker = $run->name('tx');
    $caught = null;
    $pdo->beginTransaction();
    $pdo->exec('insert into item (name, qty) values ('.$pdo->quote($marker).', 0)');
    $run->xids['tx'] = currentXid($pdo);
    if ($variant === 'caught-error') {
        try {
            $pdo->exec("insert into uniq (code) values ('taken')");
        } catch (PDOException $e) {
            $caught = describe($e);
        }
    }
    if ($variant === 'deferred-fk') {
        $pdo->exec('insert into child (parent_id) values (1)');
    }
    $run->checkpoint('before-end', [$marker]);
    $inTransactionBefore = $pdo->inTransaction();
    try {
        $return = $pdo->commit();
        $api = ['outcome' => 'returned'];
    } catch (Throwable $e) {
        $return = null;
        $api = ['outcome' => 'raised'] + describe($e);
    }
    $driver = [
        'commit_return' => $return,
        'error_info' => $pdo->errorInfo(),
        'in_transaction_before_commit' => $inTransactionBefore,
        'in_transaction_after_commit' => $pdo->inTransaction(),
    ];
    $run->checkpoint('after-end', [$marker]);

    return ['caught' => $caught, 'api' => $api, 'driver' => $driver];
}

[, $scenario, $rep] = $argv + [null, null, null];
if (!in_array($scenario, SCENARIOS, true) || !ctype_digit((string) $rep)) {
    fwrite(STDERR, "usage: php scenario.php <scenario> <repetition>\n");
    exit(2);
}

$observer = directPdo('cb-observer');
if ((string) $observer->query('show cluster_name')->fetchColumn() !== env('CB_TOKEN')) {
    fwrite(STDERR, "cluster_name does not match CB_TOKEN; refusing to run\n");
    exit(2);
}
$run = new Run($scenario, (int) $rep, $observer, directPdo('cb-sink'));

$result = match ($scenario) {
    'laravel.commit' => managed($run, 'commit'),
    'laravel.error-escapes' => managed($run, 'error-escapes'),
    'laravel.caught-error' => managed($run, 'caught-error'),
    'laravel.savepoint-recovery' => managed($run, 'savepoint-recovery'),
    'laravel.deferred-fk' => managed($run, 'deferred-fk'),
    'laravel.explicit-caught-error' => explicit($run, 'caught-error'),
    'laravel.explicit-deferred-fk' => explicit($run, 'deferred-fk'),
    'pdo.commit' => pdo($run, 'commit'),
    'pdo.caught-error' => pdo($run, 'caught-error'),
    'pdo.deferred-fk' => pdo($run, 'deferred-fk'),
};

echo json_encode([
    'scenario' => $run->scenario,
    'rep' => $run->rep,
    'subject_application_name' => $run->name('subject'),
    'subject_pid' => $run->pid,
    'observer_pid' => $run->observerPid,
    'sink_pid' => $run->sinkPid,
    'xids' => $run->xids,
    ...$result,
    'callbacks_in_process' => $run->fired,
    'checkpoints' => $run->checkpoints,
    'versions' => [
        'php' => PHP_VERSION,
        'pdo_pgsql' => phpversion('pdo_pgsql'),
        'libpq' => $observer->getAttribute(PDO::ATTR_CLIENT_VERSION),
        'server' => $observer->getAttribute(PDO::ATTR_SERVER_VERSION),
        'illuminate/database' => InstalledVersions::getPrettyVersion('illuminate/database'),
    ],
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)."\n";
