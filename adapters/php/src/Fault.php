<?php

declare(strict_types=1);

namespace Ppcs;

/**
 * One client-side fault, armed by the case and fired at most once from FaultingPdo,
 * before Laravel or the PDO policy sees the error.
 *
 * mode is the harness signature name: client-reject withholds the statement,
 * rewrite sends a ROLLBACK TO SAVEPOINT that names a savepoint which does not exist.
 */
final class Fault
{
    public string $kind = '';

    public string $modeName = '';

    public bool $armed = false;

    public int $fired = 0;

    public ?int $pid = null;

    /** @var list<string> */
    public array $withheld = [];

    /** @var list<string> */
    public array $rewritten = [];

    /** @var list<string> */
    public array $replyCodes = [];

    /** @var list<string> */
    public array $trace = [];

    public int $commitCalls = 0;

    public bool|null $lastCommitReturn = null;

    /** @var array<int, mixed>|null */
    public ?array $lastCommitErrorInfo = null;

    public ?bool $inTransactionBeforeCommit = null;

    public ?bool $inTransactionAfterCommit = null;

    public function arm(string $kind, string $mode): void
    {
        $this->kind = $kind;
        $this->modeName = $mode;
        $this->armed = true;
    }

    public function take(string $kind): bool
    {
        if (!$this->armed || $this->kind !== $kind) {
            return false;
        }
        $this->armed = false;
        $this->fired++;

        return true;
    }

    public function note(string $line): void
    {
        if (count($this->trace) < 300) {
            $this->trace[] = $line;
        }
    }

    /** @return array<string, mixed> */
    public function report(): array
    {
        $report = [
            'mode' => $this->modeName,
            'fired' => $this->fired,
            'withheld' => $this->withheld,
        ];
        if ($this->rewritten !== []) {
            $report['rewritten'] = $this->rewritten;
        }
        if ($this->replyCodes !== []) {
            $report['reply_codes'] = $this->replyCodes;
        }

        return $report;
    }

    /** @return array<string, mixed> */
    public function commitObservation(): array
    {
        $info = $this->lastCommitErrorInfo;
        $sqlState = null;
        if (is_array($info) && isset($info[0]) && is_string($info[0]) && Errors::isSqlState($info[0])) {
            $sqlState = $info[0];
        }

        return [
            'commit_calls' => $this->commitCalls,
            'commit_return' => $this->lastCommitReturn,
            'commit_sqlstate' => $sqlState,
            'in_transaction_before_commit' => $this->inTransactionBeforeCommit,
            'in_transaction_after_commit' => $this->inTransactionAfterCommit,
            'command_tag_visible' => false,
        ];
    }
}
