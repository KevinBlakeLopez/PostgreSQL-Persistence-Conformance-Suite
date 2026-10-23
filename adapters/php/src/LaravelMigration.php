<?php

declare(strict_types=1);

namespace Ppcs;

use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Database\Migrations\DatabaseMigrationRepository;
use Illuminate\Database\Migrations\Migrator;
use Illuminate\Filesystem\Filesystem;
use Throwable;

/**
 * MG-02 and MG-03 through Illuminate's Migrator. The migration file is generated for the case.
 * up() inserts the marker and, when the case holds the gate, waits on pg_advisory_xact_lock inside
 * the migration transaction. Migrator then logs the history row after that transaction commits.
 * There is no advisory lock of Laravel's own. A migration with no down() still has its history
 * row deleted: runMigration skips a missing method, and runDown deletes the repository row after that.
 */
final class LaravelMigration
{
    private const CONTRACT = 'Laravel 13.38.0 Migrator::run() executes pending files and Migrator::rollback() reverts the last batch (Migrations/Migrator.php). runMigration wraps up() or down() in Connection::transaction() when the grammar supports schema transactions and withinTransaction is true. repository->log() and repository->delete() run after that transaction. There is no advisory lock. illuminate/filesystem is the package the migrator typehints for reading migration files.';

    private const FORM = 'Migrator::run() and Migrator::rollback() on the Capsule connection, history table migrations. The migration file is generated for the case.';

    /** @param array<string, mixed> $message
     *  @return array<string, mixed>
     */
    public static function run(Capsule $capsule, array $message): array
    {
        $migration = is_array($message['migration'] ?? null) ? $message['migration'] : [];
        $markers = is_array($message['markers'] ?? null) ? $message['markers'] : [];
        $marker = (string) ($markers['m1'] ?? '');
        $dir = self::write($marker, $migration);
        try {
            $manager = $capsule->getDatabaseManager();
            $repository = new DatabaseMigrationRepository($manager, 'migrations');
            if (!$repository->repositoryExists()) {
                $repository->createRepository();
            }
            $migrator = new Migrator($repository, $manager, new Filesystem());
            $revert = ($migration['operation'] ?? '') === 'revert';
            $ran = $revert ? $migrator->rollback($dir) : $migrator->run($dir);
            $count = is_array($ran) ? count($ran) : 0;
            if ($revert) {
                return self::outcome($count > 0 ? 'reverted' : 'nothing_to_do', 0, $count > 0 ? 'Migrator::rollback() returned a migration' : 'Migrator::rollback() returned nothing');
            }

            return self::outcome($count > 0 ? 'applied' : 'nothing_to_do', 0, $count > 0 ? 'Migrator::run() returned a migration' : 'Migrator::run() returned nothing');
        } catch (Throwable $e) {
            $revert = (($message['migration']['operation'] ?? '') === 'revert');

            return self::outcome('failed', 1, $revert ? 'Migrator::rollback() threw' : 'Migrator::run() threw', Errors::info($e));
        } finally {
            self::remove($dir);
        }
    }

    /** @param array<string, mixed> $migration */
    private static function write(string $marker, array $migration): string
    {
        $dir = sys_get_temp_dir().'/ppcs-laravel-mg-'.bin2hex(random_bytes(6));
        if (!mkdir($dir, 0700, true) && !is_dir($dir)) {
            throw new \RuntimeException('could not create the migration directory');
        }
        $safe = var_export($marker, true);
        $gate = (int) ($migration['gate'] ?? 0);
        $hold = ($migration['hold'] ?? false) === true;
        $reversal = (string) ($migration['reversal'] ?? 'valid');
        $down = match ($reversal) {
            'none' => '',
            'partial-then-error' => <<<PHP

    public function down(): void
    {
        Capsule::connection()->statement('delete from item where name = ?', [{$safe}]);
        Capsule::connection()->statement('insert into ppcs_undo (name) values (?)', [{$safe}]);
        throw new \\RuntimeException('the reversal failed on purpose after deleting the marker');
    }
PHP,
            default => <<<PHP

    public function down(): void
    {
        Capsule::connection()->statement('delete from item where name = ?', [{$safe}]);
        Capsule::connection()->statement('insert into ppcs_undo (name) values (?)', [{$safe}]);
    }
PHP,
        };
        $lock = $hold ? "\n        Capsule::connection()->statement('select pg_advisory_xact_lock(?)', [{$gate}]);" : '';
        $source = <<<PHP
<?php

use Illuminate\\Database\\Capsule\\Manager as Capsule;
use Illuminate\\Database\\Migrations\\Migration;

return new class extends Migration {
    public function up(): void
    {
        Capsule::connection()->statement('insert into item (name) values (?)', [{$safe}]);{$lock}
    }{$down}
};
PHP;
        file_put_contents($dir.'/2020_01_01_000000_ppcsm1.php', $source);

        return $dir;
    }

    /** @param array<string, mixed>|null $error
     *  @return array<string, mixed>
     */
    private static function outcome(string $reported, int $exitCode, string $basis, ?array $error = null): array
    {
        $result = [
            'reported' => $reported,
            'exit_code' => $exitCode,
            'basis' => $basis,
            'contract' => self::CONTRACT,
            'form' => self::FORM,
        ];
        if ($error !== null) {
            $result['api_error'] = $error;
        }

        return $result;
    }

    private static function remove(string $dir): void
    {
        $file = $dir.'/2020_01_01_000000_ppcsm1.php';
        if (is_file($file)) {
            unlink($file);
        }
        if (is_dir($dir)) {
            rmdir($dir);
        }
    }
}
