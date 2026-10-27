# php-src — `PDO::commit()` returns true when PostgreSQL answers COMMIT with ROLLBACK

**Not filed.** Drafted 2026-10-25. Production relevance (2026-10-26): [`unfiled findings`](../../unfiled-findings-production-relevance/README.md), section "PHP `PDO::commit()` returns true". Likelihood: low. Written by: Claude Opus 5.5 (max). Nothing below has been posted. Filing needs the user's approval of the exact text.

## Notes (not part of the issue)

**Before posting:**

- Repeat the duplicate search on the day; this study's record is in [`../duplicate-search/`](../duplicate-search/README.md).
- Check that `pgsql_handle_commit()` on `master` is still unchanged.
- php-src's `CONTRIBUTING.md` ("LLM usage in GitHub comments") asks that LLM-generated paragraphs be disclosed as markdown quotes. So either the user rewrites the prose in their own words, or the LLM-written paragraphs go in as quotes. The code and its output are a recorded run.

**The issue form.** php-src's bug report form has three fields: Description (the code, the output, and the expected output), PHP Version, and Operating System. The body below follows it.

**Title:** `pdo_pgsql: PDO::commit() returns true when PostgreSQL answers COMMIT with ROLLBACK`

**Kept out of the issue on purpose:**

- **Laravel's laravel/framework#61964.** With a locally patched driver, Laravel's `DB::transaction()` keeps the failed transaction's callbacks, and runs them at the next commit. That is Laravel's to fix, and belongs on #61964 if anywhere ([`../stage-4-review.md`](../stage-4-review.md), check 9).
- **A preferred SQLSTATE.** The maintainers should choose it (design questions in the review).

**Evidence:**

- [`../repro/pdo-commit-rollback.php`](../repro/pdo-commit-rollback.php) is the code in the body. It ran three times with identical output ([`../repro/output/`](../repro/output/)).
- The wire tag, `pg_xact_status()`, the session state and the server log are in [`../laravel/`](../laravel/README.md) (scenario `pdo.caught-error`).
- The ext/pgsql comparison is [`../pgsql-extension/`](../pgsql-extension/commit-tag.php).
- The patched-driver runs are in [`../patched-driver/`](../patched-driver/README.md).

**Line numbers** are PHP 8.5.12: `pdo_pgsql_transaction_cmd()` is at `ext/pdo_pgsql/pgsql_driver.c:587-602`, and `pgsql_handle_commit()` at `:609-622`. The two functions were identical on `PHP-8.5` and on `master` at `296e8eac57` (2026-10-22).

## Body

### Description

When a statement fails inside a transaction, PostgreSQL aborts the transaction. If the application then calls `PDO::commit()`, PostgreSQL rolls the transaction back, and answers `COMMIT` with the command tag `ROLLBACK`:

- `PQresultStatus()` is `PGRES_COMMAND_OK`;
- `PQcmdStatus()` is `ROLLBACK`.

`PDO::commit()` returns `true`, the same value as for a real commit. Nothing is committed.

The following code (connection settings from libpq's `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and `PGPASSWORD`):

```php
<?php
$options = [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION];
$app = new PDO('pgsql:', null, null, $options);
$observer = new PDO('pgsql:', null, null, $options);

$app->exec('DROP TABLE IF EXISTS pdo_commit_rollback');
$app->exec('CREATE TABLE pdo_commit_rollback (id int PRIMARY KEY)');
$app->exec('INSERT INTO pdo_commit_rollback VALUES (1)');

foreach (['healthy' => 2, 'aborted' => 3] as $label => $id) {
    $app->beginTransaction();
    $app->exec("INSERT INTO pdo_commit_rollback VALUES ($id)");
    if ($label === 'aborted') {
        try {
            $app->exec('INSERT INTO pdo_commit_rollback VALUES (1)');
        } catch (PDOException $e) {
            echo "$label: caught SQLSTATE {$e->errorInfo[0]}\n";
        }
    }
    $returned = $app->commit();
    $visible = $observer->query("SELECT count(*) FROM pdo_commit_rollback WHERE id = $id")->fetchColumn();
    echo "$label: commit() returned ", var_export($returned, true), ", row $id visible to another connection: $visible\n";
}

$app->exec('DROP TABLE pdo_commit_rollback');
```

Resulted in this output:

```
healthy: commit() returned true, row 2 visible to another connection: 1
aborted: caught SQLSTATE 23505
aborted: commit() returned true, row 3 visible to another connection: 0
```

But I expected this output instead: for the aborted transaction, `commit()` reports a failure. It should return `false`, or throw a `PDOException` under `PDO::ERRMODE_EXCEPTION`, as it already does when `COMMIT` fails with an error, for example a deferred constraint.

PostgreSQL calls this an unsuccessful commit. `src/backend/tcop/utility.c` sets the `ROLLBACK` tag to "report unsuccessful commit". The application has no other way to tell the two outcomes apart through PDO:

- `inTransaction()` is `true` before both commits, and `false` after;
- `Pdo\Pgsql` has no method that returns a command tag or the transaction status;
- the native pgsql extension does return `ROLLBACK`, from `pg_result_status($result, PGSQL_STATUS_STRING)`.

The cause is in `pgsql_handle_commit()`. It calls `pdo_pgsql_transaction_cmd("COMMIT")`, which fails only when `PQresultStatus()` is not `PGRES_COMMAND_OK`, and never reads `PQcmdStatus()`. The code is the same on `master`.

Code that trusts `commit()` treats the work as committed. Frameworks then run their after-commit work for a transaction PostgreSQL rolled back: Laravel's after-commit callbacks and queued jobs, for example. The same silent `ROLLBACK` also happens without any application catch, when pdo_pgsql's own `DEALLOCATE` fails (GH-21869). Checking the tag in `pgsql_handle_commit()` would surface that case too.

A possible fix is for `pgsql_handle_commit()` to treat the tag `ROLLBACK` as a failure. I tried the patch below against 8.5.12. With it, the aborted transaction's `commit()` raises, and the connection is left as it is after a `COMMIT` that fails with an error:

- `inTransaction()` is `false`;
- `rollBack()` reports that there is no active transaction;
- the next transaction commits.

A healthy commit, and a commit after `ROLLBACK TO SAVEPOINT`, still return `true`.

Two open questions:

- **Which SQLSTATE to report,** since PostgreSQL sends none. pdo_pgsql reports `HY000` when it has none, as in the patch; `25P02` or `40000` would name the state or the outcome. `40001` would be wrong: it means a serialization failure, and Laravel, for one, retries the whole transaction on it.
- **The behavior change.** Code that today commits after a caught error would start to get an exception.

<details>
<summary>Patch tried locally against 8.5.12</summary>

```diff
--- a/ext/pdo_pgsql/pgsql_driver.c
+++ b/ext/pdo_pgsql/pgsql_driver.c
@@ -608,8 +608,22 @@
 
 static bool pgsql_handle_commit(pdo_dbh_t *dbh)
 {
-	bool ret = pdo_pgsql_transaction_cmd("COMMIT", dbh);
+	pdo_pgsql_db_handle *H = (pdo_pgsql_db_handle *)dbh->driver_data;
+	PGresult *res = PQexec(H->server, "COMMIT");
+	bool ret = true;
+
+	if (PQresultStatus(res) != PGRES_COMMAND_OK) {
+		pdo_pgsql_error(dbh, PQresultStatus(res), pdo_pgsql_sqlstate(res));
+		ret = false;
+	} else if (strcmp(PQcmdStatus(res), "ROLLBACK") == 0) {
+		/* PostgreSQL ends an aborted transaction with ROLLBACK even when COMMIT
+		   is sent, and reports that only through the command tag. */
+		pdo_pgsql_error_msg(dbh, PGRES_FATAL_ERROR, "COMMIT was answered with ROLLBACK: the transaction was rolled back");
+		ret = false;
+	}
 
+	PQclear(res);
+
 	/* When deferred constraints are used the commit could
 	   fail, and a ROLLBACK implicitly ran. See bug #67462 */
 	if (ret) {
```

</details>

### PHP Version

```
PHP 8.5.12 (cli) (NTS), pdo_pgsql 8.5.12, libpq 18.6
```

The PostgreSQL server was 18.6. The code is unchanged on `master`.

### Operating System

macOS 26.6.2 (arm64). The PostgreSQL server ran in the official `postgres:18.6` container.
