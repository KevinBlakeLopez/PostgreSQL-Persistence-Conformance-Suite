<?php

declare(strict_types=1);

namespace Config;

use CodeIgniter\Database\Config as DatabaseConfig;

class Database extends DatabaseConfig
{
    public string $defaultGroup = 'default';
}
