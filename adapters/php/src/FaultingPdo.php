<?php

declare(strict_types=1);

namespace Ppcs;

/**
 * PDO PostgreSQL connection that can withhold or rewrite one transaction-cleanup
 * statement. PHP's pdo_pgsql implements commit() and rollBack() in C. They call
 * PQexec directly. A top-level ROLLBACK is therefore withheld on rollBack(),
 * before that call. ROLLBACK TO SAVEPOINT is SQL that Laravel sends with exec()
 * or prepare(), and is withheld or rewritten there.
 *
 * commit() is not rewritten. Its return value is recorded. pdo_pgsql does not
 * expose PQcmdStatus, so this class does not report a command tag.
 */
final class FaultingPdo extends \Pdo\Pgsql
{
    private const SAVEPOINT_ROLLBACK = '/^rollback\s+to\s+(savepoint\s+)?/i';

    public function __construct(
        string $dsn,
        ?string $username,
        #[\SensitiveParameter] ?string $password,
        ?array $options,
        private readonly Fault $fault,
        private readonly Protocol $protocol,
    ) {
        parent::__construct($dsn, $username, $password, $options ?? []);
        $this->setAttribute(\PDO::ATTR_ERRMODE, \PDO::ERRMODE_EXCEPTION);
    }

    public function beginTransaction(): bool
    {
        $this->fault->note('BEGIN via PDO::beginTransaction');

        return parent::beginTransaction();
    }

    public function commit(): bool
    {
        $this->fault->commitCalls++;
        try {
            $this->fault->inTransactionBeforeCommit = $this->inTransaction();
        } catch (\Throwable) {
            $this->fault->inTransactionBeforeCommit = null;
        }
        try {
            $ok = parent::commit();
            $this->fault->lastCommitReturn = $ok;
            $this->fault->lastCommitErrorInfo = $this->errorInfo();
            $this->fault->note('COMMIT via PDO::commit returned '.($ok ? 'true' : 'false'));

            return $ok;
        } catch (\PDOException $e) {
            $this->fault->lastCommitReturn = null;
            try {
                $this->fault->lastCommitErrorInfo = $this->errorInfo();
            } catch (\Throwable) {
                $this->fault->lastCommitErrorInfo = null;
            }
            $this->fault->note('COMMIT via PDO::commit threw '.Errors::message($e));
            throw $e;
        } finally {
            try {
                $this->fault->inTransactionAfterCommit = $this->inTransaction();
            } catch (\Throwable) {
                $this->fault->inTransactionAfterCommit = null;
            }
        }
    }

    public function rollBack(): bool
    {
        if ($this->fault->take('root')) {
            $this->fault->withheld[] = 'ROLLBACK';
            $this->fault->note('ROLLBACK -- WITHHELD on PDO::rollBack before send');
            $this->protocol->checkpoint('after-fault', null, $this->fault->pid);
            throw new \PDOException('injected client-side failure: ROLLBACK was not sent');
        }
        $this->fault->note('ROLLBACK via PDO::rollBack');

        return parent::rollBack();
    }

    public function exec(string $statement): int|false
    {
        $this->fault->note($this->oneLine($statement));
        $this->interceptSavepoint($statement);

        return parent::exec($statement);
    }

    public function prepare(string $query, array $options = []): \PDOStatement|false
    {
        $this->fault->note($this->oneLine($query));
        $this->interceptSavepoint($query);

        return parent::prepare($query, $options);
    }

    public function query(string $query, ?int $fetchMode = null, mixed ...$fetchModeArgs): \PDOStatement|false
    {
        $this->fault->note($this->oneLine($query));
        $this->interceptSavepoint($query);
        if ($fetchMode === null) {
            return parent::query($query);
        }

        return parent::query($query, $fetchMode, ...$fetchModeArgs);
    }

    private function interceptSavepoint(string $sql): void
    {
        $flat = $this->oneLine($sql);
        if (preg_match(self::SAVEPOINT_ROLLBACK, $flat) !== 1) {
            return;
        }
        if (!$this->fault->take('savepoint')) {
            return;
        }
        $this->fault->withheld[] = $flat;
        if ($this->fault->modeName === 'client-reject') {
            $this->fault->note($flat.' -- WITHHELD before send');
            $this->protocol->checkpoint('after-fault', null, $this->fault->pid);
            throw new \PDOException('injected client-side failure: ROLLBACK TO SAVEPOINT was not sent');
        }
        $rewritten = 'ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint';
        $this->fault->rewritten[] = $rewritten;
        $this->fault->note($rewritten.' -- REWRITE of: '.$flat);
        $error = null;
        try {
            parent::exec($rewritten);
        } catch (\PDOException $e) {
            $error = $e;
            $code = Errors::sqlState($e) ?? 'error';
            $this->fault->replyCodes[] = $code;
        }
        $this->protocol->checkpoint('after-fault', null, $this->fault->pid);
        if ($error !== null) {
            throw $error;
        }
        throw new \PDOException('rewritten ROLLBACK TO SAVEPOINT was not rejected');
    }

    private function oneLine(string $sql): string
    {
        $flat = preg_replace('/\s+/', ' ', trim($sql)) ?? trim($sql);

        return substr($flat, 0, 300);
    }
}
