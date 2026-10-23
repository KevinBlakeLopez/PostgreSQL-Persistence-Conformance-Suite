<?php

declare(strict_types=1);

/**
 * Boot for the migration subject. service() and config() are defined before
 * CodeIgniter's Common.php so the migrator can run without an application.
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
defined('APP_NAMESPACE') || define('APP_NAMESPACE', 'App');
defined('ROOTPATH') || define('ROOTPATH', $root . DIRECTORY_SEPARATOR);
defined('APPPATH') || define('APPPATH', $root . DIRECTORY_SEPARATOR);
defined('SYSTEMPATH') || define('SYSTEMPATH', $system . DIRECTORY_SEPARATOR);
defined('FCPATH') || define('FCPATH', $root . DIRECTORY_SEPARATOR);
defined('EXIT_SUCCESS') || define('EXIT_SUCCESS', 0);
defined('EXIT_ERROR') || define('EXIT_ERROR', 1);
defined('EXIT_DATABASE') || define('EXIT_DATABASE', 8);

require $root . '/vendor/autoload.php';
require $root . '/vendor/codeigniter4/framework/app/Config/Modules.php';
$modules = new Config\Modules();
$modules->enabled = false;
CodeIgniter\Config\BaseConfig::setModules($modules);
require $root . '/src/Config/Database.php';
require $root . '/src/Config/Feature.php';
require $root . '/vendor/codeigniter4/framework/app/Config/Migrations.php';
require $root . '/src/MigrationLocator.php';

$GLOBALS['mpcs_logs'] = [];

if (! function_exists('log_message')) {
    function log_message(string $level, string $message, array $context = []): void
    {
        $text = $context['message'] ?? $message;
        $GLOBALS['mpcs_logs'][] = [
            'level' => $level,
            'message' => is_string($text) ? $text : (string) $text,
        ];
    }
}

if (! function_exists('config')) {
    function config(string $name, bool $getShared = true): object
    {
        return match ($name) {
            'Config\\Database', Config\Database::class => new Config\Database(),
            'Config\\Migrations', Config\Migrations::class => new Config\Migrations(),
            'Config\\Feature', Config\Feature::class => new Config\Feature(),
            default => throw new RuntimeException('Unexpected config ' . $name),
        };
    }
}

if (! function_exists('service')) {
    function service(string $name, ...$params): object
    {
        if ($name === 'locator') {
            return new Mpcs\MigrationLocator();
        }

        throw new RuntimeException('Unexpected service ' . $name);
    }
}

if (! function_exists('lang')) {
    function lang(string $line, array $args = []): string
    {
        if ($line === 'Database.emptyDataset') {
            return 'There is no data to ' . ($args[0] ?? '') . '.';
        }

        return $line;
    }
}

require $root . '/vendor/autoload.php';
require $system . '/Common.php';

$eventsReady = new ReflectionProperty(CodeIgniter\Events\Events::class, 'initialized');
$eventsReady->setValue(null, true);

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

function mpcs_versions(): array
{
    $probe = new mysqli();

    return [
        'php' => PHP_VERSION,
        'mysqli_client' => $probe->client_info,
        'ci4' => Composer\InstalledVersions::getPrettyVersion('codeigniter4/framework'),
        'ci4_reference' => Composer\InstalledVersions::getReference('codeigniter4/framework'),
    ];
}
