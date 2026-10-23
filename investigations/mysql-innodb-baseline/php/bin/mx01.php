<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Boot.php';
require dirname(__DIR__) . '/src/Subject.php';

$scenario = $argv[1] ?? '';

try {
    $result = mpcs_run_scenario($scenario);
    $result['logs'] = mpcs_logs();

    try {
        $result['versions'] = mpcs_versions();
    } catch (Throwable $versionError) {
        $result['versions_error'] = $versionError->getMessage();
    }
    echo json_encode($result, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), "\n";
} catch (Throwable $error) {
    $payload = [
        'scenario' => $scenario,
        'failed' => true,
        'class' => $error::class,
        'message' => $error->getMessage(),
        'file' => basename($error->getFile()),
        'line' => $error->getLine(),
        'logs' => function_exists('mpcs_logs') ? mpcs_logs() : [],
    ];

    fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
    exit(1);
}
