<?php

declare(strict_types=1);

namespace App\Database\Migrations;

use CodeIgniter\Database\Migration;
use RuntimeException;

class DdlThenFail extends Migration
{
    /** @var array<string, mixed> */
    public static array $notes = [];

    public function up(): void
    {
        $other = new \mysqli(
            mpcs_env('MPCS_HOST'),
            mpcs_env('MPCS_USER'),
            mpcs_env('MPCS_PASSWORD'),
            mpcs_database(),
            (int) mpcs_env('MPCS_PORT'),
        );
        $other->set_charset('utf8mb4');

        $this->db->transStart();
        $this->db->query("INSERT INTO marker (name) VALUES ('ddl-marker')");
        self::$notes['other_before_ddl'] = mpcs_ddl_names($other);
        self::$notes['table_before_ddl'] = mpcs_ddl_table($other, 'ddl_side');

        $this->db->query('CREATE TABLE ddl_side (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB');
        self::$notes['other_after_ddl'] = mpcs_ddl_names($other);
        self::$notes['table_after_ddl'] = mpcs_ddl_table($other, 'ddl_side');
        self::$notes['depth_after_ddl'] = $this->db->transDepth;
        self::$notes['status_after_ddl'] = $this->db->transStatus();

        $duplicate = $this->db->query("INSERT INTO uniq_row (code) VALUES ('taken')");
        self::$notes['duplicate_returned'] = $duplicate;
        self::$notes['duplicate_error'] = $this->db->error();
        self::$notes['status_before_complete'] = $this->db->transStatus();
        self::$notes['depth_before_complete'] = $this->db->transDepth;
        self::$notes['complete'] = $this->db->transComplete();
        self::$notes['other_after_complete'] = mpcs_ddl_names($other);
        self::$notes['table_after_complete'] = mpcs_ddl_table($other, 'ddl_side');
        self::$notes['depth_after_complete'] = $this->db->transDepth;

        throw new RuntimeException('migration failed after schema change');
    }

    public function down(): void
    {
    }
}
