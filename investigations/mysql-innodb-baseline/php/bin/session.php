<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Boot.php';
require dirname(__DIR__) . '/src/Subject.php';
require dirname(__DIR__) . '/src/Session.php';

try {
    mpcs_session_loop();
} catch (Throwable $error) {
    fwrite(STDERR, $error::class . ': ' . $error->getMessage() . "\n");
    exit(1);
}
