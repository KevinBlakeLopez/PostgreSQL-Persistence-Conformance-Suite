<?php

declare(strict_types=1);

namespace Ppcs;

use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Connection;
use Illuminate\Database\QueryException;
use Throwable;

/**
 * Laravel's Illuminate database connection, through Capsule, without a full
 * application. Writes use Eloquent. Transactions use Connection::transaction()
 * or beginTransaction()/commit()/rollBack(). The PDO underneath is FaultingPdo,
 * created by FaultingConnector so category C faults fire before Laravel sees them.
 *
 * Capsule does not install DatabaseTransactionsManager. afterCommit() is
 * therefore not part of this native path. A separate probe records callbacks.
 */
final class LaravelAdapter
{
    private const CONTRACT_MANAGED = 'Laravel 13.38.0 Illuminate\\Database\\Connection::transaction() (ManagesTransactions) begins a transaction, runs the callback, and on return calls getPdo()->commit() when $this->transactions === 1. '
        .'A thrown callback calls rollBack() and rethrows, unless the exception is a concurrency error and attempts remain. The default attempts value is 1. '
        .'Connection::commit() calls getPdo()->commit() only when transactionLevel() === 1. A nested commit decrements the counter and does not send RELEASE SAVEPOINT. '
        .'Connection::beginTransaction() at level 0 calls PDO::beginTransaction(). At level 1 or more it execs SAVEPOINT transN (Grammar::compileSavepoint). '
        .'rollBack() to level 0 calls PDO::rollBack() when PDO::inTransaction() is true. A nested rollBack execs ROLLBACK TO SAVEPOINT transN (Grammar::compileSavepointRollBack). '
        .'Neither commit() nor transaction() reads PDO::errorInfo() or a PostgreSQL command tag after commit(). '
        .'executeBeginTransactionStatement() is getPdo()->beginTransaction() only. It takes no isolation argument. '
        .'PostgresConnector::configureIsolationLevel runs "set session characteristics as transaction isolation level {$config[\'isolation_level\']}" when the connection is opened, if that config key is set. '
        .'This adapter does not set DatabaseTransactionsManager. Capsule does not set it either, so afterCommit() is not called on this path.';

    private const CONTRACT_EXPLICIT = 'Laravel 13.38.0 Connection::beginTransaction(), Connection::commit(), and Connection::rollBack() are the explicit API. '
        .'The adapter calls beginTransaction(), runs the work, calls commit() when the work returns, and on a thrown error calls rollBack() and reports that error. '
        .'commit() calls getPdo()->commit() only when transactionLevel() === 1, then decrements the counter and fires the committed event. It does not read a command tag. '
        .'A nested beginTransaction() is SAVEPOINT transN. A nested rollBack() is ROLLBACK TO SAVEPOINT transN. A nested commit() does not send RELEASE SAVEPOINT. '
        .'executeBeginTransactionStatement() does not take an isolation level. Session isolation, when requested, is PostgresConnector::configureIsolationLevel at connect time.';

    private ?Connection $connection = null;

    private ?Capsule $capsule = null;

    public function __construct(
        private readonly Protocol $protocol,
        private readonly Fault $fault,
        private readonly string $mode,
    ) {
    }

    public static function main(): void
    {
        self::requireRuntime();
        $protocol = new Protocol();
        $fault = new Fault();
        $adapter = null;
        $helloSent = false;
        $mode = 'unknown';
        $result = ['type' => 'result'];
        try {
            $message = $protocol->read();
            if (($message['type'] ?? null) !== 'case') {
                throw new ProtocolException('expected a case message');
            }
            $mode = (string) ($message['mode'] ?? '');
            if (!in_array($mode, ['managed', 'explicit', 'persistent'], true)) {
                throw new \RuntimeException('unknown mode "'.$mode.'"');
            }
            $adapter = new self($protocol, $fault, $mode);
            $adapter->open($message, null);
            $protocol->send($adapter->hello($message));
            $helloSent = true;
            $outcome = $adapter->dispatch($message);
            $protocol->checkpoint('after-end', null, null);
            $result['status'] = 'completed';
            foreach ($outcome as $key => $value) {
                $result[$key] = $value;
            }
            $result['diagnostics'] = $adapter->diagnostics();
        } catch (Throwable $e) {
            if (!$helloSent) {
                try {
                    $protocol->send(self::fallbackHello($mode));
                } catch (Throwable) {
                }
            }
            $result['status'] = 'error';
            $error = Errors::info($e);
            $error['protocol'] = Errors::isProtocol($e);
            $result['error'] = $error;
            if ($adapter !== null) {
                $result['diagnostics'] = $adapter->diagnostics();
            }
        } finally {
            $adapter?->close();
        }
        try {
            $protocol->send($result);
        } catch (Throwable) {
        }
    }

    private static function requireRuntime(): void
    {
        if (PHP_VERSION !== '8.5.6') {
            fwrite(STDERR, 'laravel adapter requires PHP 8.5.6; this runtime is '.PHP_VERSION."\n");
            exit(2);
        }
        if (!extension_loaded('pdo_pgsql')) {
            fwrite(STDERR, "pdo_pgsql is not loaded\n");
            exit(2);
        }
    }

    /** @param array<string, mixed> $message */
    public function open(array $message, ?string $isolation): void
    {
        $c = $message['connection'] ?? null;
        if (!is_array($c)) {
            throw new ProtocolException('the case message has no connection');
        }
        $this->connectionConfig = $c;
        $capsule = new Capsule();
        $fault = $this->fault;
        $protocol = $this->protocol;
        $capsule->getContainer()->bind('db.connector.pgsql', static function () use ($fault, $protocol): FaultingConnector {
            return new FaultingConnector($fault, $protocol);
        });
        $config = [
            'driver' => 'pgsql',
            'host' => (string) $c['host'],
            'port' => (int) $c['port'],
            'database' => (string) $c['database'],
            'username' => (string) $c['user'],
            'password' => (string) $c['password'],
            'charset' => 'utf8',
            'prefix' => '',
            'schema' => 'public',
            'application_name' => (string) $c['application_name'],
            'options' => [
                \PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION,
                \PDO::ATTR_PERSISTENT => $this->mode === 'persistent',
                \PDO::ATTR_EMULATE_PREPARES => false,
            ],
        ];
        if ($isolation !== null) {
            if ($isolation !== 'serializable') {
                throw new \RuntimeException('this adapter only forwards isolation level serializable');
            }
            $config['isolation_level'] = $isolation;
        }
        $capsule->addConnection($config);
        $capsule->setAsGlobal();
        $capsule->bootEloquent();
        $connection = $capsule->getConnection();
        $pdo = $connection->getPdo();
        if (!$pdo instanceof FaultingPdo) {
            throw new \RuntimeException('Laravel opened '.($pdo === null ? 'no PDO' : $pdo::class).' instead of FaultingPdo');
        }
        $this->capsule = $capsule;
        $this->connection = $connection;
    }

    /** @param array<string, mixed> $message
     *  @return array<string, mixed>
     */
    private function hello(array $message): array
    {
        $version = \Composer\InstalledVersions::getPrettyVersion('illuminate/database') ?? '13.38.0';
        $pdo = $this->connection?->getPdo();
        $libpq = 'unknown';
        $server = 'unknown';
        if ($pdo instanceof \PDO) {
            $client = $pdo->getAttribute(\PDO::ATTR_CLIENT_VERSION);
            $serverAttr = $pdo->getAttribute(\PDO::ATTR_SERVER_VERSION);
            $libpq = is_string($client) ? $client : (string) $client;
            $server = is_string($serverAttr) ? $serverAttr : (string) $serverAttr;
        }

        return [
            'type' => 'hello',
            'adapter' => ['name' => 'laravel', 'version' => '0.1.0'],
            'framework' => ['name' => 'illuminate/database', 'version' => $version],
            'driver' => ['name' => 'pdo_pgsql', 'version' => (string) phpversion('pdo_pgsql')],
            'components' => [
                'illuminate/database' => $version,
                'pdo_pgsql' => (string) phpversion('pdo_pgsql'),
                'libpq' => $libpq,
                'postgresql' => $server,
            ],
            'runtime' => ['name' => 'php', 'version' => PHP_VERSION],
            'mode' => $this->mode,
            'configuration' => [
                'api' => $this->explicit() ? 'beginTransaction/commit/rollBack' : 'Connection::transaction(Closure)',
                'writes' => 'Eloquent Item::query()->create and Uniq::query()->create',
                'nested' => 'savepoint transN on the same connection',
                'transactions_manager' => 'not set; Capsule does not install DatabaseTransactionsManager',
                'persistent' => $this->mode === 'persistent' ? 'PDO::ATTR_PERSISTENT true' : 'PDO::ATTR_PERSISTENT false',
                'pool' => 'none; one connection on the Capsule manager',
                'isolation' => 'connection config isolation_level, applied by PostgresConnector when set; transaction() takes no isolation argument',
                'command_tag' => 'not read; PDO::commit() does not expose one',
            ],
        ];
    }

    /** @return array<string, mixed> */
    private static function fallbackHello(string $mode): array
    {
        return [
            'type' => 'hello',
            'adapter' => ['name' => 'laravel', 'version' => '0.1.0'],
            'framework' => ['name' => 'illuminate/database', 'version' => '13.38.0'],
            'driver' => ['name' => 'pdo_pgsql', 'version' => (string) phpversion('pdo_pgsql')],
            'components' => new \stdClass(),
            'runtime' => ['name' => 'php', 'version' => PHP_VERSION],
            'mode' => $mode,
            'configuration' => new \stdClass(),
        ];
    }

    /** @param array<string, mixed> $message */
    private function dispatch(array $message): array
    {
        $case = $message['case'] ?? null;
        if (!is_array($case) || !isset($case['id'])) {
            throw new ProtocolException('the case message has no id');
        }
        $this->case = $case;
        $this->markers = is_array($message['markers'] ?? null) ? $message['markers'] : [];
        $id = (string) $case['id'];
        if ($id === 'TX-05.managed-serializable' || $id === 'TX-05.explicit-serializable') {
            return $this->isolation();
        }

        return match ($id) {
            'CTL-01.commit' => $this->commitCase(),
            'CTL-01.rollback' => $this->rollbackCase(),
            'TX-01A.caught-error-then-commit' => $this->caughtError(),
            'TX-01B.conn-lost-before-commit' => $this->connLost(),
            'TX-02.savepoint-rollback-not-sent' => $this->savepoint('not-sent'),
            'TX-02.savepoint-rollback-rejected' => $this->savepoint('rejected'),
            'TX-02.conn-lost-before-savepoint-rollback' => $this->savepoint('conn-lost'),
            'TX-03.rollback-not-sent' => $this->reuse('rollback-not-sent'),
            'TX-03.statement-error-rollback-not-sent' => $this->reuse('statement-error'),
            'TX-03.conn-lost-in-transaction' => $this->reuse('conn-lost'),
            'TX-04.nested-failure-contained' => $this->propagation('nested-fails'),
            'TX-04.nested-released-outer-rollback' => $this->propagation('outer-fails'),
            default => throw new \RuntimeException('this adapter does not implement '.$id),
        };
    }

    /** @var array<string, mixed> */
    private array $case = [];

    /** @var array<string, mixed> */
    private array $markers = [];

    private function commitCase(): array
    {
        $outcome = $this->complete(function (Connection $tx): void {
            $this->insertItem($this->marker('tx'));
            $ident = $this->identify($tx);
            $this->protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
        });

        return $this->pack($outcome, []);
    }

    private function rollbackCase(): array
    {
        $outcome = $this->complete(function (Connection $tx): void {
            $this->insertItem($this->marker('tx'));
            $ident = $this->identify($tx);
            $this->protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
            throw new AppException('application error: the request fails');
        });

        return $this->pack($outcome, []);
    }

    private function caughtError(): array
    {
        $violation = null;
        $outcome = $this->complete(function (Connection $tx) use (&$violation): void {
            $this->insertItem($this->marker('tx'));
            $ident = $this->identify($tx);
            $this->protocol->checkpoint('after-write', $ident['xid'], $ident['pid']);
            try {
                Uniq::query()->create(['code' => 'taken']);
            } catch (Throwable $e) {
                if (Errors::isProtocol($e)) {
                    throw $e;
                }
                $violation = $e;
            }
            if (!$violation instanceof Throwable) {
                throw new \RuntimeException('the duplicate insert did not raise');
            }
            $this->protocol->checkpoint('before-end', null, $ident['pid']);
        });
        $steps = [];
        if ($violation instanceof Throwable) {
            $steps['violation'] = Errors::info($violation);
        }

        return $this->pack($outcome, $steps);
    }

    private function connLost(): array
    {
        $outcome = $this->complete(function (Connection $tx): void {
            $this->insertItem($this->marker('tx'));
            $ident = $this->identify($tx);
            $this->protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
            $this->settle();
        });

        return $this->pack($outcome, []);
    }

    private function savepoint(string $kind): array
    {
        $nested = ['caught' => false];
        $outerPid = null;
        $outcome = $this->complete(function (Connection $tx) use ($kind, &$nested, &$outerPid): void {
            $this->insertItem($this->marker('outer'));
            $ident = $this->identify($tx);
            $outerPid = $ident['pid'];
            $this->protocol->checkpoint('outer-after-write', $ident['xid'], $ident['pid']);
            $this->inner($tx, $kind, $nested, false);
        });
        $this->protocol->checkpoint('after-outer', null, $outerPid);
        $steps = ['nested' => $nested];
        if ($kind !== 'conn-lost') {
            $steps['fault'] = $this->fault->report();
        }

        return $this->pack($outcome, $steps);
    }

    private function propagation(string $kind): array
    {
        $nested = ['caught' => false];
        $outcome = $this->complete(function (Connection $tx) use ($kind, &$nested): void {
            $this->insertItem($this->marker('outer'));
            $this->inner($tx, $kind, $nested, true);
            if ($kind === 'outer-fails') {
                throw new AppException('application error: the request fails');
            }
        });

        return $this->pack($outcome, ['nested' => $nested]);
    }

    /** @param array<string, mixed> $nested */
    private function inner(Connection $tx, string $kind, array &$nested, bool $captureXid): void
    {
        $body = function (Connection $inner) use ($kind, $captureXid): void {
            $this->insertItem($this->marker('inner'));
            $ident = $this->identify($inner);
            $this->protocol->checkpoint(
                'inner-after-write',
                $captureXid ? $ident['xid'] : null,
                $ident['pid'],
            );
            if ($kind === 'not-sent') {
                $this->fault->arm('savepoint', 'client-reject');
            } elseif ($kind === 'rejected') {
                $this->fault->arm('savepoint', 'rewrite');
            } elseif ($kind === 'conn-lost') {
                $this->settle();
            }
            if ($kind !== 'outer-fails') {
                throw new AppException('application error: the request fails');
            }
        };
        if (!$this->explicit()) {
            try {
                $tx->transaction(function (Connection $inner) use ($body): void {
                    $body($inner);
                });
                $nested['completed'] = true;
            } catch (Throwable $e) {
                if (Errors::isProtocol($e)) {
                    throw $e;
                }
                $nested['caught'] = true;
                $nested['error'] = Errors::info($e);
            }

            return;
        }
        $tx->beginTransaction();
        try {
            $body($tx);
            $tx->commit();
            $nested['completed'] = true;
        } catch (Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            try {
                $tx->rollBack();
            } catch (Throwable $cleanup) {
                if (Errors::isProtocol($cleanup)) {
                    throw $cleanup;
                }
                $nested['caught'] = true;
                $nested['error'] = Errors::info($cleanup);

                return;
            }
            $nested['caught'] = true;
            $nested['error'] = Errors::info($e);
        }
    }

    private function reuse(string $kind): array
    {
        $violation = null;
        $unit1Pid = null;
        $outcome = $this->complete(function (Connection $tx) use ($kind, &$violation, &$unit1Pid): void {
            $this->insertItem($this->marker('doomed'));
            $ident = $this->identify($tx);
            $unit1Pid = $ident['pid'];
            $this->protocol->checkpoint('unit1-after-write', $ident['xid'], $ident['pid']);
            if ($kind === 'conn-lost') {
                $this->settle();
                throw new AppException('application error: the request fails');
            }
            $this->fault->arm('root', 'client-reject');
            if ($kind === 'statement-error') {
                try {
                    Uniq::query()->create(['code' => 'taken']);
                } catch (Throwable $e) {
                    if (Errors::isProtocol($e)) {
                        throw $e;
                    }
                    $violation = $e;
                    throw $e;
                }
                throw new \RuntimeException('the duplicate insert did not raise');
            }
            throw new AppException('application error: the request fails');
        });
        $this->protocol->checkpoint('after-unit1', null, $unit1Pid);
        $started = hrtime(true);
        $unit2Pid = null;
        $unit2 = $this->unit2($unit2Pid);
        $unit2['elapsed_ms'] = (int) ((hrtime(true) - $started) / 1_000_000);
        $steps = [
            'unit2' => $unit2,
            'reuse' => [
                'unit1_pid' => $unit1Pid,
                'unit2_pid' => $unit2Pid,
                'same_backend' => $unit1Pid !== null && $unit1Pid === $unit2Pid,
                'transaction_level_after_unit1' => $this->level(),
                'persistent' => $this->mode === 'persistent',
            ],
        ];
        if ($violation instanceof Throwable) {
            $steps['violation'] = Errors::info($violation);
        }
        if ($kind !== 'conn-lost') {
            $steps['fault'] = $this->fault->report();
        }

        return $this->pack($outcome, $steps);
    }

    /** @return array<string, mixed> */
    private function unit2(?int &$unit2Pid): array
    {
        try {
            $inner = $this->complete(function (Connection $tx) use (&$unit2Pid): void {
                $this->insertItem($this->marker('next'));
                $ident = $this->identify($tx);
                $unit2Pid = $ident['pid'];
                $this->protocol->checkpoint('unit2-after-write', $ident['xid'], $ident['pid']);
            });
            $unit = ['outcome' => 'completed', 'reported' => $inner['reported']];
            if (isset($inner['api_error'])) {
                $unit['api_error'] = $inner['api_error'];
            }

            return $unit;
        } catch (Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }

            return ['outcome' => 'completed', 'reported' => 'failed', 'api_error' => Errors::info($e)];
        }
    }

    private function isolation(): array
    {
        $this->close();
        $message = ['connection' => $this->connectionConfig, 'case' => $this->case, 'markers' => $this->markers];
        $startError = null;
        try {
            $this->open($message, 'serializable');
        } catch (Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            $startError = $e;
            $this->open($message, null);

            return $this->baseline($startError);
        }
        $reached = false;
        $outcome = $this->complete(function (Connection $tx) use (&$reached): void {
            $reached = true;
            $this->insertItem($this->marker('tx'));
            Item::query()->where('name', $this->marker('tx'))->get();
            $ident = $this->identify($tx, true);
            $this->protocol->checkpoint('after-read', $ident['xid'], $ident['pid'], $ident['isolation']);
        });
        if (!$reached) {
            return $this->baseline(new \RuntimeException((string) ($outcome['basis'] ?? 'the transaction did not start')));
        }

        return $this->pack($outcome, [], $this->isolationForm());
    }

    /** @return array<string, mixed> */
    private function baseline(Throwable $startError): array
    {
        $plainFailed = null;
        $outcome = $this->complete(function (Connection $tx): void {
            $ident = $this->identify($tx);
            $this->protocol->checkpoint('baseline', $ident['xid'], $ident['pid']);
        });
        $steps = [];
        if ($outcome['reported'] !== 'committed') {
            $plainFailed = $outcome['api_error'] ?? Errors::info(new \RuntimeException((string) $outcome['basis']));
            $steps['baseline'] = ['error' => $plainFailed];
        }
        $failed = $this->failed(
            'PostgresConnector::configureIsolationLevel threw, or the transaction API did not start. A plain transaction through the same API was then attempted.',
            $startError,
        );

        return $this->pack($failed, $steps, $this->isolationForm());
    }

    /** @var array<string, mixed> */
    private array $connectionConfig = [];

    /** @param callable(Connection): void $body
     *  @return array{reported: string, basis: string, api_error?: array<string, mixed>}
     */
    private function complete(callable $body): array
    {
        return $this->explicit() ? $this->runExplicit($body) : $this->runManaged($body);
    }

    /** @param callable(Connection): void $body
     *  @return array{reported: string, basis: string, api_error?: array<string, mixed>}
     */
    private function runManaged(callable $body): array
    {
        try {
            $this->connection()->transaction(function (Connection $tx) use ($body): void {
                $body($tx);
            });

            return $this->committed('Connection::transaction() returned. When the callback returns, Laravel calls PDO::commit() if the transaction level is 1. The return value of PDO::commit() is not inspected.');
        } catch (Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }

            return $this->fromEscape($e, 'Connection::transaction() threw');
        }
    }

    /** @param callable(Connection): void $body
     *  @return array{reported: string, basis: string, api_error?: array<string, mixed>}
     */
    private function runExplicit(callable $body): array
    {
        $connection = $this->connection();
        $connection->beginTransaction();
        try {
            $body($connection);
            $connection->commit();

            return $this->committed('Connection::commit() returned. At level 1 that calls PDO::commit() and does not inspect its return value or a command tag.');
        } catch (Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            try {
                $connection->rollBack();
            } catch (Throwable $cleanup) {
                if (Errors::isProtocol($cleanup)) {
                    throw $cleanup;
                }

                return $this->failed('the explicit transaction failed and Connection::rollBack() threw', $cleanup);
            }
            if ($e instanceof AppException || $this->isStatementEscape($e)) {
                return $this->rolledBack('the body threw and Connection::rollBack() returned', $e);
            }

            return $this->failed('Connection::commit() threw. Connection::rollBack() returned. This is not reported as a confirmed rollback.', $e);
        }
    }

    /** @return array{reported: string, basis: string, api_error?: array<string, mixed>} */
    private function fromEscape(Throwable $e, string $where): array
    {
        if ($e instanceof AppException || $this->isStatementEscape($e)) {
            return $this->rolledBack($where.', and the exception is the callback failure after rollBack()', $e);
        }

        return $this->failed($where.'. The exception is not the callback\'s own error, so this is not reported as a confirmed rollback.', $e);
    }

    private function isStatementEscape(Throwable $e): bool
    {
        if (str_starts_with($e->getMessage(), 'injected client-side failure')) {
            return false;
        }
        if ($e instanceof QueryException) {
            return true;
        }
        $state = Errors::sqlState($e);

        return $state === '23505';
    }

    private function insertItem(string $name): void
    {
        Item::query()->create(['name' => $name, 'qty' => 0]);
    }

    /** @return array{xid: string, pid: int, isolation: string|null} */
    private function identify(Connection $connection, bool $isolation = false): array
    {
        $sql = $isolation
            ? "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as isolation"
            : 'select pg_current_xact_id()::text as xid, pg_backend_pid() as pid';
        $row = $connection->selectOne($sql);
        $xid = is_object($row) ? ($row->xid ?? null) : (is_array($row) ? ($row['xid'] ?? null) : null);
        $pid = is_object($row) ? ($row->pid ?? null) : (is_array($row) ? ($row['pid'] ?? null) : null);
        $level = is_object($row) ? ($row->isolation ?? null) : (is_array($row) ? ($row['isolation'] ?? null) : null);
        if (!is_string($xid) || $pid === null) {
            throw new \RuntimeException('identify returned no row');
        }
        $pid = (int) $pid;
        $this->fault->pid = $pid;

        return ['xid' => $xid, 'pid' => $pid, 'isolation' => is_string($level) ? $level : null];
    }

    /** @param callable(Connection): void $body */
    private function connection(): Connection
    {
        if (!$this->connection instanceof Connection) {
            throw new \RuntimeException('the Laravel connection is not open');
        }

        return $this->connection;
    }

    private function explicit(): bool
    {
        return $this->mode === 'explicit';
    }

    private function level(): ?int
    {
        try {
            return $this->connection?->transactionLevel();
        } catch (Throwable) {
            return null;
        }
    }

    /** @return array<string, mixed> */
    public function diagnostics(): array
    {
        $pdo = null;
        try {
            $pdo = $this->connection?->getPdo();
        } catch (Throwable) {
            $pdo = null;
        }

        return [
            'write_api' => 'eloquent',
            'call_path' => 'Item::query()->create -> Eloquent Builder -> Connection::insert -> PDOStatement::execute; transaction via Connection::transaction or beginTransaction/commit/rollBack -> PDO::beginTransaction/commit/rollBack or exec(SAVEPOINT)',
            'transaction_level_after' => $this->level(),
            'pdo_class' => $pdo === null ? null : $pdo::class,
            'persistent' => $this->mode === 'persistent',
            'transactions_manager' => false,
            'commit' => $this->fault->commitObservation(),
            'fault_trace' => $this->fault->trace,
            'command_tag' => null,
        ];
    }

    public function close(): void
    {
        try {
            $this->connection?->disconnect();
        } catch (Throwable) {
        }
        $this->connection = null;
        $this->capsule = null;
    }

    /** @param array{reported: string, basis: string, api_error?: array<string, mixed>} $outcome
     *  @param array<string, mixed> $steps
     *  @return array<string, mixed>
     */
    private function pack(array $outcome, array $steps, ?string $form = null): array
    {
        $result = [
            'reported' => $outcome['reported'],
            'basis' => $outcome['basis'],
            'contract' => $this->explicit() ? self::CONTRACT_EXPLICIT : self::CONTRACT_MANAGED,
            'form' => $form ?? ($this->explicit()
                ? 'Explicit Connection::beginTransaction(), the work, Connection::commit() or Connection::rollBack(). Nested beginTransaction() is a savepoint. Writes are Eloquent creates.'
                : 'Managed Connection::transaction(Closure). Nested transaction() is a savepoint. Writes are Eloquent creates. The persistent mode is the same callback with PDO::ATTR_PERSISTENT.'),
            'steps' => $steps === [] ? new \stdClass() : $steps,
        ];
        if (isset($outcome['api_error'])) {
            $result['api_error'] = $outcome['api_error'];
        }

        return $result;
    }

    /** @return array{reported: string, basis: string} */
    private function committed(string $basis): array
    {
        return ['reported' => 'committed', 'basis' => $basis];
    }

    /** @return array{reported: string, basis: string, api_error: array<string, mixed>} */
    private function rolledBack(string $basis, Throwable $error): array
    {
        return ['reported' => 'rolled_back', 'basis' => $basis, 'api_error' => Errors::info($error)];
    }

    /** @return array{reported: string, basis: string, api_error: array<string, mixed>} */
    private function failed(string $basis, Throwable $error): array
    {
        return ['reported' => 'failed', 'basis' => $basis, 'api_error' => Errors::info($error)];
    }

    private function isolationForm(): string
    {
        return 'Isolation is the connection config key isolation_level. PostgresConnector::configureIsolationLevel sends SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL when the PDO is opened. '
            .($this->explicit()
                ? 'The explicit case then calls beginTransaction() and commit(). Those methods take no isolation argument.'
                : 'The managed case then calls transaction(). That method takes no isolation argument.');
    }

    private function marker(string $name): string
    {
        if (!isset($this->markers[$name]) || !is_string($this->markers[$name])) {
            throw new ProtocolException('missing marker '.$name);
        }

        return $this->markers[$name];
    }

    private function setting(string $name): mixed
    {
        $settings = $this->case['settings'] ?? null;

        return is_array($settings) ? ($settings[$name] ?? null) : null;
    }

    private function settle(): void
    {
        $ms = (int) ($this->setting('settle_ms') ?? 0);
        if ($ms > 0) {
            usleep($ms * 1000);
        }
    }
}
