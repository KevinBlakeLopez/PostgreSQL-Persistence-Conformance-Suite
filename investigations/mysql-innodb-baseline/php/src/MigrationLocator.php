<?php

declare(strict_types=1);

namespace Mpcs;

class MigrationLocator
{
    public function getClassname(string $path): string
    {
        return 'App\\Database\\Migrations\\DdlThenFail';
    }
}
