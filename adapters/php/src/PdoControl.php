<?php

declare(strict_types=1);

namespace Ppcs;

/**
 * PDO PostgreSQL control. Two completion policies, plus a persistent-connection
 * mode that uses the correct policy.
 *
 * correct: a caught statement error selects PDO::rollBack() and does not call
 * PDO::commit(). PDO has no public transaction-status or command-tag API, so
 * this policy cannot do what the JDBC control does with PgConnection.getTransactionState().
 * A thrown rollBack() drops the handle.
 *
 * unsafe: PDO::commit() returning true is reported as committed, including after
 * a caught unique violation. A thrown rollBack() keeps the handle. The next unit
 * continues on that handle when beginTransaction reports an active transaction.
 *
 * Neither policy reads a command tag. A true return from commit() is not treated
 * as proof that PostgreSQL committed.
 */
final class PdoControl
{
    private const FORM = 'PDO::beginTransaction(), prepared inserts against item and uniq, then PDO::commit() or PDO::rollBack(). One connection is held. It is not a pool.';

    private const CONTRACT_CORRECT = 'The correct pdo-control policy uses PDO::beginTransaction, PDO::commit, PDO::rollBack, and PDOStatement::execute. '
        .'PHP 8.5 PDO::commit() returns true on success and throws PDOException on failure. It does not return a PostgreSQL command tag. '
        .'pdo_pgsql 8.5.12 (pgsql_handle_commit through pdo_pgsql_transaction_cmd, and pgsql_handle_doer for exec()) treats PGRES_COMMAND_OK as success and does not read PQcmdStatus. The deprecated Pdo\\Pgsql::TRANSACTION_* constants have no effect. '
        .'Because no public PDO API reports the transaction status or the command tag, a statement error caught inside the transaction selects PDO::rollBack() and the policy does not call PDO::commit(). '
        .'That reports rolled_back. It does not claim that PDO::commit() observed a ROLLBACK tag. '
        .'If PDO::rollBack() throws, the policy drops the handle and reports failed. It does not report a confirmed rollback from a thrown rollback. '
        .'If PDO::commit() throws on a path that does call it, the policy reports failed and drops the handle.';

    private const CONTRACT_UNSAFE = 'The unsafe pdo-control policy reports committed when PDO::commit() returns true, including after a unique violation was caught in the same transaction. '
        .'It does not read a command tag, and PDO::commit() does not return one. A true return is the success signal. '
        .'When PDO::commit() throws, the policy reports rolled_back. '
        .'When the body throws and PDO::rollBack() throws, the policy reports failed and keeps the PDO handle. '
        .'The next unit calls PDO::beginTransaction(). If that throws "already an active transaction", the policy writes and calls PDO::commit() on the same handle. '
        .'There is no Connection.setAutoCommit. This is not the JDBC unsafe policy\'s setAutoCommit(true) call.';

    public static function main(): void
    {
        self::requireRuntime();
        $protocol = new Protocol();
        $fault = new Fault();
        $session = null;
        $helloSent = false;
        $mode = 'unknown';
        $result = ['type' => 'result'];
        try {
            $message = $protocol->read();
            if (($message['type'] ?? null) !== 'case') {
                throw new ProtocolException('expected a case message');
            }
            $mode = (string) ($message['mode'] ?? '');
            if (!in_array($mode, ['correct', 'unsafe', 'persistent'], true)) {
                throw new \RuntimeException('unknown mode "'.$mode.'"');
            }
            $session = PdoSession::open($message, $fault, $protocol, $mode === 'persistent');
            $protocol->send(self::hello($mode, $session));
            $helloSent = true;
            $outcome = self::dispatch($session, $protocol, $message, $fault, $mode);
            $protocol->checkpoint('after-end', null, null);
            $result['status'] = 'completed';
            foreach ($outcome as $key => $value) {
                $result[$key] = $value;
            }
            $result['diagnostics'] = $session->diagnostics();
        } catch (\Throwable $e) {
            if (!$helloSent) {
                try {
                    $protocol->send(self::fallbackHello($mode));
                } catch (\Throwable) {
                }
            }
            $result['status'] = 'error';
            $error = Errors::info($e);
            $error['protocol'] = Errors::isProtocol($e);
            $result['error'] = $error;
            if ($session !== null) {
                $result['diagnostics'] = $session->diagnostics();
            }
        } finally {
            $session?->close();
        }
        try {
            $protocol->send($result);
        } catch (\Throwable) {
        }
    }

    private static function requireRuntime(): void
    {
        if (PHP_VERSION !== '8.5.12') {
            fwrite(STDERR, 'pdo-control requires PHP 8.5.12; this runtime is '.PHP_VERSION."\n");
            exit(2);
        }
        if (!extension_loaded('pdo_pgsql')) {
            fwrite(STDERR, "pdo_pgsql is not loaded\n");
            exit(2);
        }
    }

    /** @return array<string, mixed> */
    private static function hello(string $mode, PdoSession $session): array
    {
        $correct = $mode !== 'unsafe';

        return [
            'type' => 'hello',
            'adapter' => ['name' => 'pdo-control', 'version' => '0.1.0'],
            'framework' => ['name' => 'pdo_pgsql', 'version' => (string) phpversion('pdo_pgsql')],
            'driver' => ['name' => 'libpq', 'version' => $session->clientVersion()],
            'components' => [
                'pdo_pgsql' => (string) phpversion('pdo_pgsql'),
                'libpq' => $session->clientVersion(),
                'postgresql' => $session->serverVersion(),
            ],
            'runtime' => ['name' => 'php', 'version' => PHP_VERSION],
            'mode' => $mode,
            'configuration' => [
                'commit_outcome' => $correct
                    ? 'a caught statement error calls PDO::rollBack and does not call PDO::commit; command tag is not visible'
                    : 'committed when PDO::commit returns true',
                'commit_error' => $correct ? 'reported as failed; handle dropped' : 'reported as rolled_back',
                'failed_rollback' => $correct ? 'handle dropped' : 'handle kept; next beginTransaction may continue on it',
                'persistent' => $session->persistent ? 'PDO::ATTR_PERSISTENT true' : 'PDO::ATTR_PERSISTENT false',
                'connections' => 'one PDO handle at a time, not a pool',
                'command_tag' => 'not exposed by pdo_pgsql',
            ],
        ];
    }

    /** @return array<string, mixed> */
    private static function fallbackHello(string $mode): array
    {
        return [
            'type' => 'hello',
            'adapter' => ['name' => 'pdo-control', 'version' => '0.1.0'],
            'framework' => ['name' => 'pdo_pgsql', 'version' => (string) phpversion('pdo_pgsql')],
            'driver' => ['name' => 'libpq', 'version' => 'unknown'],
            'components' => new \stdClass(),
            'runtime' => ['name' => 'php', 'version' => PHP_VERSION],
            'mode' => $mode,
            'configuration' => new \stdClass(),
        ];
    }

    /** @param array<string, mixed> $message */
    private static function dispatch(PdoSession $session, Protocol $protocol, array $message, Fault $fault, string $mode): array
    {
        $case = $message['case'] ?? null;
        if (!is_array($case) || !isset($case['id'])) {
            throw new ProtocolException('the case message has no id');
        }
        $id = (string) $case['id'];
        $markers = $message['markers'] ?? [];
        if (!is_array($markers)) {
            throw new ProtocolException('the case message has no markers');
        }
        $settings = is_array($case['settings'] ?? null) ? $case['settings'] : [];
        $unsafe = $mode === 'unsafe';

        return match ($id) {
            'CTL-01.commit', 'TX-01B.commit-reply-unseen' => self::commit($session, $protocol, $markers, $unsafe),
            'CTL-01.rollback' => self::rollback($session, $protocol, $markers, $unsafe),
            'TX-01A.caught-error-then-commit' => self::caughtError($session, $protocol, $markers, $unsafe),
            'TX-01B.conn-lost-before-commit' => self::connLost($session, $protocol, $markers, $settings, $unsafe),
            'TX-03.rollback-not-sent' => self::reuse($session, $protocol, $markers, $settings, $fault, $unsafe, 'rollback-not-sent'),
            'TX-03.statement-error-rollback-not-sent' => self::reuse($session, $protocol, $markers, $settings, $fault, $unsafe, 'statement-error'),
            'TX-03.conn-lost-in-transaction' => self::reuse($session, $protocol, $markers, $settings, $fault, $unsafe, 'conn-lost'),
            default => throw new \RuntimeException('this adapter does not implement '.$id),
        };
    }

    /** @param array<string, mixed> $markers */
    private static function commit(PdoSession $session, Protocol $protocol, array $markers, bool $unsafe): array
    {
        $outcome = self::run($session, $unsafe, false, function () use ($session, $protocol, $markers): void {
            $session->insertItem(self::marker($markers, 'tx'));
            $ident = $session->identify();
            $protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
        });

        return self::result($unsafe, $outcome, []);
    }

    /** @param array<string, mixed> $markers */
    private static function rollback(PdoSession $session, Protocol $protocol, array $markers, bool $unsafe): array
    {
        $outcome = self::run($session, $unsafe, false, function () use ($session, $protocol, $markers): void {
            $session->insertItem(self::marker($markers, 'tx'));
            $ident = $session->identify();
            $protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
            throw new AppException('application error: the request fails');
        });

        return self::result($unsafe, $outcome, []);
    }

    /** @param array<string, mixed> $markers */
    private static function caughtError(PdoSession $session, Protocol $protocol, array $markers, bool $unsafe): array
    {
        $violation = null;
        $outcome = self::run($session, $unsafe, false, function () use ($session, $protocol, $markers, &$violation): void {
            $session->insertItem(self::marker($markers, 'tx'));
            $ident = $session->identify();
            $protocol->checkpoint('after-write', $ident['xid'], $ident['pid']);
            try {
                $session->insertTaken();
            } catch (\Throwable $e) {
                if (Errors::isProtocol($e)) {
                    throw $e;
                }
                $violation = $e;
            }
            if (!$violation instanceof \Throwable) {
                throw new \RuntimeException('the duplicate insert did not raise');
            }
            $protocol->checkpoint('before-end', null, $ident['pid']);
        }, $violation);
        $steps = [];
        if ($violation instanceof \Throwable) {
            $steps['violation'] = Errors::info($violation);
        }

        return self::result($unsafe, $outcome, $steps);
    }

    /**
     * @param array<string, mixed> $markers
     * @param array<string, mixed> $settings
     */
    private static function connLost(PdoSession $session, Protocol $protocol, array $markers, array $settings, bool $unsafe): array
    {
        $outcome = self::run($session, $unsafe, false, function () use ($session, $protocol, $markers, $settings): void {
            $session->insertItem(self::marker($markers, 'tx'));
            $ident = $session->identify();
            $protocol->checkpoint('before-end', $ident['xid'], $ident['pid']);
            self::settle($settings);
        });

        return self::result($unsafe, $outcome, []);
    }

    /**
     * @param array<string, mixed> $markers
     * @param array<string, mixed> $settings
     */
    private static function reuse(PdoSession $session, Protocol $protocol, array $markers, array $settings, Fault $fault, bool $unsafe, string $kind): array
    {
        $violation = null;
        $unit1Pid = null;
        $outcome = self::run($session, $unsafe, false, function () use ($session, $protocol, $markers, $settings, $fault, $kind, &$violation, &$unit1Pid): void {
            $session->insertItem(self::marker($markers, 'doomed'));
            $ident = $session->identify();
            $unit1Pid = $ident['pid'];
            $protocol->checkpoint('unit1-after-write', $ident['xid'], $ident['pid']);
            if ($kind === 'conn-lost') {
                self::settle($settings);
                throw new AppException('application error: the request fails');
            }
            $fault->arm('root', 'client-reject');
            if ($kind === 'statement-error') {
                try {
                    $session->insertTaken();
                } catch (\Throwable $e) {
                    if (Errors::isProtocol($e)) {
                        throw $e;
                    }
                    $violation = $e;
                    throw $e;
                }
            }
            throw new AppException('application error: the request fails');
        });
        $protocol->checkpoint('after-unit1', null, $unit1Pid);

        $bound = (int) ($settings['bound_ms'] ?? 5000);
        $started = hrtime(true);
        $unit2Pid = null;
        $unit2 = self::unit2($session, $protocol, $markers, $unsafe, $bound, $started, $unit2Pid);
        $steps = [
            'unit2' => $unit2,
            'reuse' => [
                'unit1_pid' => $unit1Pid,
                'unit2_pid' => $unit2Pid,
                'same_backend' => $unit1Pid !== null && $unit1Pid === $unit2Pid,
                'persistent' => $session->persistent,
            ],
        ];
        if ($violation instanceof \Throwable) {
            $steps['violation'] = Errors::info($violation);
        }
        if ($kind !== 'conn-lost') {
            $steps['fault'] = $fault->report();
        }

        return self::result($unsafe, $outcome, $steps);
    }

    /**
     * @param array<string, mixed> $markers
     * @return array<string, mixed>
     */
    private static function unit2(PdoSession $session, Protocol $protocol, array $markers, bool $unsafe, int $boundMs, int $started, ?int &$unit2Pid): array
    {
        try {
            $inner = self::run($session, $unsafe, $unsafe, function () use ($session, $protocol, $markers, &$unit2Pid): void {
                $session->insertItem(self::marker($markers, 'next'));
                $ident = $session->identify();
                $unit2Pid = $ident['pid'];
                $protocol->checkpoint('unit2-after-write', $ident['xid'], $ident['pid']);
            });
            $unit = [
                'outcome' => 'completed',
                'elapsed_ms' => self::elapsedMs($started),
                'reported' => $inner['reported'],
            ];
            if (isset($inner['api_error'])) {
                $unit['api_error'] = $inner['api_error'];
            }

            return $unit;
        } catch (\Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            $elapsed = self::elapsedMs($started);

            return [
                'outcome' => 'completed',
                'elapsed_ms' => $elapsed,
                'reported' => 'failed',
                'api_error' => Errors::info($e),
            ];
        }
    }

    /**
     * $statementError is set by the work callback when it catches a statement
     * error and continues. It is a reference so the assignment inside the
     * callback is visible after the callback returns.
     *
     * @param callable(): void $work
     * @return array{reported: string, basis: string, api_error?: array<string, mixed>}
     */
    private static function run(PdoSession $session, bool $unsafe, bool $continueIfActive, callable $work, ?\Throwable &$statementError = null): array
    {
        $pdo = $session->pdo();
        try {
            $pdo->beginTransaction();
        } catch (\PDOException $e) {
            if ($continueIfActive && str_contains($e->getMessage(), 'already an active transaction')) {
                $session->note('PDO::beginTransaction reported an active transaction; the unsafe policy continued');
            } else {
                throw $e;
            }
        }
        $body = null;
        try {
            $work();
        } catch (\Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            $body = $e;
        }
        if ($statementError instanceof \Throwable && $body === null) {
            return self::finishCaught($session, $unsafe, $statementError);
        }

        return self::finish($session, $unsafe, $body);
    }

    /** @return array{reported: string, basis: string, api_error?: array<string, mixed>} */
    private static function finishCaught(PdoSession $session, bool $unsafe, \Throwable $violation): array
    {
        if (!$unsafe) {
            try {
                $session->pdo()->rollBack();
            } catch (\Throwable $e) {
                if (Errors::isProtocol($e)) {
                    throw $e;
                }
                $session->discard();

                return self::failed('a statement error was caught and PDO::rollBack() then threw. The handle was dropped. The policy does not report a confirmed rollback.', $e);
            }

            return self::rolledBack(
                'a statement error was caught. PDO exposes no transaction status and no command tag, so the policy called PDO::rollBack() and did not call PDO::commit().',
                $violation,
            );
        }
        try {
            $ok = $session->pdo()->commit();
        } catch (\Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }

            return self::rolledBack('PDO::commit() threw, which the unsafe policy reports as a rollback', $e);
        }
        if ($ok !== true) {
            return self::failed('PDO::commit() returned false after a caught statement error. The unsafe policy does not report a commit.', new \RuntimeException('PDO::commit returned false'));
        }

        return self::committed('PDO::commit() returned true after a caught statement error. The return value is not a command tag. The unsafe policy reports committed.');
    }

    /** @return array{reported: string, basis: string, api_error?: array<string, mixed>} */
    private static function finish(PdoSession $session, bool $unsafe, ?\Throwable $body): array
    {
        if ($body !== null) {
            try {
                $session->pdo()->rollBack();
            } catch (\Throwable $e) {
                if (Errors::isProtocol($e)) {
                    throw $e;
                }
                if (!$unsafe) {
                    $session->discard();

                    return self::failed('the body threw and PDO::rollBack() threw. The handle was dropped.', $e);
                }
                $session->note('PDO::rollBack threw; the unsafe policy kept the handle');

                return self::failed('the body threw and PDO::rollBack() threw. The handle was kept.', $e);
            }

            return self::rolledBack('the body threw and PDO::rollBack() returned', $body);
        }
        try {
            $ok = $session->pdo()->commit();
        } catch (\Throwable $e) {
            if (Errors::isProtocol($e)) {
                throw $e;
            }
            if (!$unsafe) {
                $session->discard();

                return self::failed('PDO::commit() threw. The policy reports failed and drops the handle. It does not report a confirmed rollback.', $e);
            }

            return self::rolledBack('PDO::commit() threw, which the unsafe policy reports as a rollback', $e);
        }
        if ($ok !== true) {
            if (!$unsafe) {
                $session->discard();
            }

            return self::failed('PDO::commit() returned false. The policy does not report a commit.', new \RuntimeException('PDO::commit returned false'));
        }

        return self::committed('PDO::commit() returned true. The return value is not a PostgreSQL command tag.');
    }

    /** @param array<string, mixed> $steps
     *  @param array{reported: string, basis: string, api_error?: array<string, mixed>} $outcome
     *  @return array<string, mixed>
     */
    private static function result(bool $unsafe, array $outcome, array $steps): array
    {
        $result = [
            'reported' => $outcome['reported'],
            'basis' => $outcome['basis'],
            'contract' => $unsafe ? self::CONTRACT_UNSAFE : self::CONTRACT_CORRECT,
            'form' => self::FORM,
            'steps' => $steps === [] ? new \stdClass() : $steps,
        ];
        if (isset($outcome['api_error'])) {
            $result['api_error'] = $outcome['api_error'];
        }

        return $result;
    }

    /** @return array{reported: string, basis: string} */
    private static function committed(string $basis): array
    {
        return ['reported' => 'committed', 'basis' => $basis];
    }

    /** @return array{reported: string, basis: string, api_error: array<string, mixed>} */
    private static function rolledBack(string $basis, \Throwable $error): array
    {
        return ['reported' => 'rolled_back', 'basis' => $basis, 'api_error' => Errors::info($error)];
    }

    /** @return array{reported: string, basis: string, api_error: array<string, mixed>} */
    private static function failed(string $basis, \Throwable $error): array
    {
        return ['reported' => 'failed', 'basis' => $basis, 'api_error' => Errors::info($error)];
    }

    /** @param array<string, mixed> $markers */
    private static function marker(array $markers, string $name): string
    {
        if (!isset($markers[$name]) || !is_string($markers[$name])) {
            throw new ProtocolException('missing marker '.$name);
        }

        return $markers[$name];
    }

    /** @param array<string, mixed> $settings */
    private static function settle(array $settings): void
    {
        $ms = (int) ($settings['settle_ms'] ?? 0);
        if ($ms > 0) {
            usleep($ms * 1000);
        }
    }

    private static function elapsedMs(int $started): int
    {
        return (int) ((hrtime(true) - $started) / 1_000_000);
    }
}
