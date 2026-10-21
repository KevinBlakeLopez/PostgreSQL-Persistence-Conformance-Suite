<?php

declare(strict_types=1);

// Used by the PDO control, which does not load Illuminate. The Laravel adapter
// uses Composer's autoload instead, which maps the same namespace.
spl_autoload_register(static function (string $class): void {
    $prefix = 'Ppcs\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }
    $relative = str_replace('\\', '/', substr($class, strlen($prefix)));
    $path = __DIR__.'/'.$relative.'.php';
    if (is_file($path)) {
        require $path;
    }
});
