<?php

declare(strict_types=1);

namespace Ppcs;

use Illuminate\Database\Connectors\PostgresConnector;

/**
 * Laravel's Postgres connector, with one change: the PDO it constructs is
 * FaultingPdo. Isolation, search_path, and the DSN still come from
 * PostgresConnector. The fault fires before Laravel sees the error.
 */
final class FaultingConnector extends PostgresConnector
{
    public function __construct(
        private readonly Fault $fault,
        private readonly Protocol $protocol,
    ) {
    }

    protected function createPdoConnection($dsn, $username, #[\SensitiveParameter] $password, $options)
    {
        return new FaultingPdo(
            (string) $dsn,
            $username === null ? null : (string) $username,
            $password === null ? null : (string) $password,
            is_array($options) ? $options : [],
            $this->fault,
            $this->protocol,
        );
    }
}
