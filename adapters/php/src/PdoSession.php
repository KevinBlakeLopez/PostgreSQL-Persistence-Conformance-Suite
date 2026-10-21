<?php

declare(strict_types=1);

namespace Ppcs;

/**
 * One PDO connection at a time. This is not a pool.
 * discard() drops the handle so the next pdo() opens another.
 * With ATTR_PERSISTENT, PHP may hand back the same backend.
 */
final class PdoSession
{
    private ?FaultingPdo $pdo = null;

    /** @var list<string> */
    private array $notes = [];

    /** @param array<int, mixed> $options */
    public function __construct(
        private readonly string $dsn,
        private readonly string $user,
        #[\SensitiveParameter] private readonly string $password,
        private readonly array $options,
        private readonly Fault $fault,
        private readonly Protocol $protocol,
        public readonly bool $persistent,
    ) {
    }

    public static function open(array $message, Fault $fault, Protocol $protocol, bool $persistent): self
    {
        $c = $message['connection'] ?? null;
        if (!is_array($c)) {
            throw new ProtocolException('the case message has no connection');
        }
        foreach (['host', 'port', 'user', 'password', 'database', 'application_name'] as $key) {
            if (!isset($c[$key]) || $c[$key] === '') {
                throw new ProtocolException('the connection is missing '.$key);
            }
        }
        $dsn = sprintf(
            'pgsql:host=%s;port=%d;dbname=%s;application_name=%s',
            (string) $c['host'],
            (int) $c['port'],
            (string) $c['database'],
            str_replace("'", "\\'", (string) $c['application_name']),
        );
        $options = [
            \PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION,
            \PDO::ATTR_PERSISTENT => $persistent,
            \PDO::ATTR_EMULATE_PREPARES => false,
            \PDO::ATTR_STRINGIFY_FETCHES => false,
        ];

        return new self($dsn, (string) $c['user'], (string) $c['password'], $options, $fault, $protocol, $persistent);
    }

    public function pdo(): FaultingPdo
    {
        if ($this->pdo === null) {
            $this->pdo = new FaultingPdo($this->dsn, $this->user, $this->password, $this->options, $this->fault, $this->protocol);
            $this->note($this->persistent ? 'new FaultingPdo ATTR_PERSISTENT true' : 'new FaultingPdo');
        }

        return $this->pdo;
    }

    public function discard(): void
    {
        $pdo = $this->pdo;
        $this->pdo = null;
        if ($pdo === null) {
            return;
        }
        $this->note('dropped PDO handle');
        unset($pdo);
    }

    public function close(): void
    {
        $this->discard();
    }

    public function note(string $line): void
    {
        if (count($this->notes) < 300) {
            $this->notes[] = $line;
        }
    }

    public function insertItem(string $name): void
    {
        $this->note('insert into item (name, qty) values (?, 0)');
        $stmt = $this->pdo()->prepare('insert into item (name, qty) values (?, 0)');
        $stmt->execute([$name]);
    }

    public function insertTaken(): void
    {
        $this->note("insert into uniq (code) values ('taken')");
        $stmt = $this->pdo()->prepare('insert into uniq (code) values (?)');
        $stmt->execute(['taken']);
    }

    public function readItem(string $name): void
    {
        $this->note('select name from item where name = ?');
        $stmt = $this->pdo()->prepare('select name from item where name = ?');
        $stmt->execute([$name]);
        $stmt->fetchAll();
    }

    /** @return array{xid: string, pid: int, isolation: string|null} */
    public function identify(bool $isolation = false): array
    {
        $sql = $isolation
            ? "select pg_current_xact_id()::text as xid, pg_backend_pid() as pid, current_setting('transaction_isolation') as isolation"
            : 'select pg_current_xact_id()::text as xid, pg_backend_pid() as pid';
        $this->note($sql);
        $stmt = $this->pdo()->prepare($sql);
        $stmt->execute();
        $row = $stmt->fetch(\PDO::FETCH_ASSOC);
        if (!is_array($row) || !isset($row['xid'], $row['pid'])) {
            throw new \RuntimeException('identify returned no row');
        }
        $pid = (int) $row['pid'];
        $this->fault->pid = $pid;

        return [
            'xid' => (string) $row['xid'],
            'pid' => $pid,
            'isolation' => isset($row['isolation']) ? (string) $row['isolation'] : null,
        ];
    }

    public function clientVersion(): string
    {
        $value = $this->pdo()->getAttribute(\PDO::ATTR_CLIENT_VERSION);

        return is_string($value) ? $value : (string) $value;
    }

    public function serverVersion(): string
    {
        $value = $this->pdo()->getAttribute(\PDO::ATTR_SERVER_VERSION);

        return is_string($value) ? $value : (string) $value;
    }

    /** @return array<string, mixed> */
    public function diagnostics(): array
    {
        return [
            'trace' => $this->notes,
            'fault_trace' => $this->fault->trace,
            'commit' => $this->fault->commitObservation(),
            'persistent' => $this->persistent,
            'command_tag' => null,
            'command_tag_note' => 'pdo_pgsql does not expose PQcmdStatus. PDO::commit() return value is not a command tag.',
        ];
    }
}
