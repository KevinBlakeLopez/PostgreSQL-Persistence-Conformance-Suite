<?php

declare(strict_types=1);

/**
 * Boots enough of CodeIgniter 4 to construct a MySQLi connection.
 *
 * The subject does not start a CodeIgniter application. log_message() is
 * defined here so system/Common.php keeps this collector. Events discovery
 * is marked initialized so a query does not search an application tree.
 */

ini_set('display_errors', '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);

set_error_handler(static function (int $severity, string $message, string $file, int $line): bool {
    if ((error_reporting() & $severity) === 0) {
        return false;
    }

    throw new ErrorException($message, 0, $severity, $file, $line);
});

$root = dirname(__DIR__);
$system = $root . '/vendor/codeigniter4/framework/system';

defined('ENVIRONMENT') || define('ENVIRONMENT', 'production');
defined('CI_DEBUG') || define('CI_DEBUG', false);
defined('ROOTPATH') || define('ROOTPATH', $root . DIRECTORY_SEPARATOR);
defined('APPPATH') || define('APPPATH', $root . DIRECTORY_SEPARATOR);
defined('SYSTEMPATH') || define('SYSTEMPATH', $system . DIRECTORY_SEPARATOR);
defined('FCPATH') || define('FCPATH', $root . DIRECTORY_SEPARATOR);
defined('EXIT_SUCCESS') || define('EXIT_SUCCESS', 0);
defined('EXIT_ERROR') || define('EXIT_ERROR', 1);
defined('EXIT_DATABASE') || define('EXIT_DATABASE', 8);

require $root . '/vendor/autoload.php';

$GLOBALS['mpcs_logs'] = [];

if (! function_exists('log_message')) {
    /**
     * @param array<string, mixed> $context
     */
    function log_message(string $level, string $message, array $context = []): void
    {
        $text = $context['message'] ?? $message;
        $GLOBALS['mpcs_logs'][] = [
            'level' => $level,
            'message' => is_string($text) ? $text : (string) $text,
            'file' => isset($context['exFile']) ? basename((string) $context['exFile']) : null,
            'line' => $context['exLine'] ?? null,
        ];
    }
}

require $system . '/Common.php';

$eventsReady = new ReflectionProperty(CodeIgniter\Events\Events::class, 'initialized');
$eventsReady->setValue(null, true);

/**
 * @return list<array{level: string, message: string, file: string|null, line: mixed}>
 */
function mpcs_logs(): array
{
    return $GLOBALS['mpcs_logs'];
}

function mpcs_env(string $key): string
{
    $value = getenv($key);
    if (! is_string($value) || $value === '') {
        throw new RuntimeException($key . ' is not set');
    }

    return $value;
}

function mpcs_database(): string
{
    $name = mpcs_env('MPCS_DATABASE');
    if (preg_match('/^[a-z][a-z0-9_]*$/', $name) !== 1) {
        throw new RuntimeException('MPCS_DATABASE is not an identifier');
    }

    return $name;
}

/**
 * @return array{php: string, mysqli_client: string, pdo_client: string|null, ci4: string|null, ci4_reference: string|null}
 */
function mpcs_versions(): array
{
    $probe = new mysqli();
    $pdoClient = null;

    try {
        $pdo = new PDO(
            'mysql:host=' . mpcs_env('MPCS_HOST') . ';port=' . mpcs_env('MPCS_PORT') . ';dbname=' . mpcs_database() . ';charset=utf8mb4',
            mpcs_env('MPCS_USER'),
            mpcs_env('MPCS_PASSWORD'),
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION],
        );
        $pdoClient = (string) $pdo->getAttribute(PDO::ATTR_CLIENT_VERSION);
        $pdo = null;
    } catch (Throwable) {
        $pdoClient = null;
    }

    return [
        'php' => PHP_VERSION,
        'mysqli_client' => $probe->client_info,
        'pdo_client' => $pdoClient,
        'ci4' => Composer\InstalledVersions::getPrettyVersion('codeigniter4/framework'),
        'ci4_reference' => Composer\InstalledVersions::getReference('codeigniter4/framework'),
    ];
}
