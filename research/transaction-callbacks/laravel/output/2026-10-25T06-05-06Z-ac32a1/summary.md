# Run 2026-10-25T06-05-06Z-ac32a1

PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), PHP 8.5.12, pdo_pgsql 8.5.12, libpq 18.6, illuminate/database v13.38.0. 3 repetitions per scenario. "Fate" is pg_xact_status() of the transaction ID captured inside the transaction, read on the observer's own connection. "Marker visible" and "Callback log" are read on that connection too.

| Scenario | Repetitions agreeing | API | Caught | PDO::commit() | Session before end | Fate before end | Wire: end statement [status before] -> reply | Fate after end | Marker visible | Callback log after end | Reuse | Manager pending/committed after end | Manager pending/committed at exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `laravel.commit` | 3 of 3 | returned | - | - | idle in transaction | in progress | COMMIT [T] -> COMMIT | committed | 1 | afterCommit | - | 0/0 | 0/0 |
| `laravel.error-escapes` | 3 of 3 | raised UniqueConstraintViolationException 23505 | - | - | idle in transaction | in progress | ROLLBACK [E] -> ROLLBACK | aborted | 0 | afterRollBack | - | 0/0 | 0/0 |
| `laravel.caught-error` | 3 of 3 | returned | 23505 | - | idle in transaction (aborted) | aborted | COMMIT [E] -> ROLLBACK; COMMIT [T] -> COMMIT | aborted | 0 | afterCommit | committed; markers 0,1; log afterCommit, afterCommit:reuse | 0/0 | 0/0 |
| `laravel.explicit-caught-error` | 3 of 3 | returned | 23505 | - | idle in transaction (aborted) | aborted | COMMIT [E] -> ROLLBACK | aborted | 0 | afterCommit | - | 0/0 | 0/0 |
| `laravel.savepoint-recovery` | 3 of 3 | returned | 23505 | - | idle in transaction | in progress | ROLLBACK TO SAVEPOINT trans2 [E] -> ROLLBACK; COMMIT [T] -> COMMIT | committed | 1 | afterRollBack:inner, afterCommit | - | 0/0 | 0/0 |
| `laravel.deferred-fk` | 3 of 3 | raised PDOException 23503 | - | - | idle in transaction | in progress | COMMIT [T] -> error 23503; COMMIT [T] -> COMMIT | aborted | 0 | none | committed; markers 0,1; log afterCommit, afterCommit:reuse | 1/0 | 0/0 |
| `laravel.explicit-deferred-fk` | 3 of 3 | raised PDOException 23503 | - | - | idle in transaction | in progress | COMMIT [T] -> error 23503; COMMIT [T] -> COMMIT | aborted | 0 | afterRollBack | committed; markers 0,1; log afterRollBack, afterCommit:reuse | 0/0 | 0/0 |
| `pdo.commit` | 3 of 3 | returned | - | true | idle in transaction | in progress | COMMIT [T] -> COMMIT | committed | 1 | none | - | - | - |
| `pdo.caught-error` | 3 of 3 | returned | 23505 | true | idle in transaction (aborted) | aborted | COMMIT [E] -> ROLLBACK | aborted | 0 | none | - | - | - |
| `pdo.deferred-fk` | 3 of 3 | raised PDOException 23503 | - | null | idle in transaction | in progress | COMMIT [T] -> error 23503 | aborted | 0 | none | - | - | - |
