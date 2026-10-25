"""Builds results-matrix.md from the row definitions below and the recorded outputs.

For each row, the repetition count and the SHA-256 prefix are computed from output/<path>.rep*.out, so they cannot
drift from the evidence. A row whose repetitions disagree prints "DISAGREE" instead of a hash.

Usage: python -I analysis/build_matrix.py > results-matrix.md   (from research/connection-pool-session-state)
"""

import glob
import hashlib
import sys

H = "HikariCP 7.1.0, pgjdbc 42.7.14"
HP = "HikariCP 7.1.0 + one-line fix, pgjdbc 42.7.14"
HF = "HikariCP 7.1.0 + completion-flag fix, pgjdbc 42.7.14"
A = "asyncpg 0.32.0 `Pool`"
SA_A = "SQLAlchemy 2.1.6 `AsyncAdaptedQueuePool`, asyncpg 0.32.0"
SA_S = "SQLAlchemy 2.1.6 `QueuePool`, psycopg 3.3.6"
PP = "psycopg_pool 3.3.3, psycopg 3.3.6"
N = "Npgsql 10.0.3 `NpgsqlDataSource`"
PG = "pg-pool 3.14.0, pg 8.23.1"

# framework, driver/pool, state category, scenario, same backend, cleanup result, observed state, contract,
# classification, evidence (output path without .repN.out)
ROWS = [
    ("PostgreSQL 18.6", "none: one session", "All categories A–K", "Baseline: commit, rollback, failed statement, RESET ALL, DISCARD ALL, termination",
     "n/a", "n/a", "As documented: §5", "PostgreSQL documentation", "CONFIRMED BEHAVIOR (control)", "baseline/baseline"),

    ("HikariCP", H, "Isolation, set through JDBC", "Normal close", "yes", "Completed", "Cleared",
     "`transactionIsolation`: default of connections returned from the pool", "CONFIRMED BEHAVIOR (positive control)", "hikari/iso-reset"),
    ("HikariCP", H, "`search_path` through `setSchema()`", "Normal close, `schema` unset", "yes",
     "Not attempted: reset only when `schema` is configured", "Retained: B's unqualified insert in `tenant_a`",
     "`schema`: \"If this property is not specified, the default schema defined by the JDBC driver is used\"",
     "KNOWN UPSTREAM (HikariCP #2081, open)", "hikari/schema-unconfigured"),
    ("HikariCP", H, "`search_path` through `setSchema()`", "Normal close, `schema=public`", "yes", "Completed", "Cleared",
     "As above", "CONFIRMED BEHAVIOR (positive control)", "hikari/schema-configured"),
    ("HikariCP", H, "Configured `schema`, applied at connection setup", "`autoCommit=false`; first borrower rolls back", "yes",
     "Setup's SET left uncommitted, undone by A's rollback", "Configured schema lost: B's committed insert in `public`",
     "`schema`: \"sets the default schema\"", "KNOWN UPSTREAM (#1369, #1633, #2235; pgjdbc#3005)", "hikari/setup-schema-noautocommit"),
    ("HikariCP", H, "Configured `schema`, reset on close", "`autoCommit=false`; next borrower rolls back", "yes",
     "Reset ran in a transaction HikariCP never ends; B's rollback undid it", "C's committed insert in A's `tenant_a`",
     "As above", "KNOWN UPSTREAM (#2144; pgjdbc#3005)", "hikari/reset-undone"),
    ("HikariCP", H, "Isolation + transaction opened by `getSchema()`", "`autoCommit=false`, isolation at driver default; `close()` throws 25001", "yes",
     "Failed: pgjdbc rejected the reset, nothing sent", "Retained: B inside A's SERIALIZABLE transaction, stale snapshot; C SERIALIZABLE",
     "`transactionIsolation` default (driver default when unset)", "CONFIRMED DEFECT (F-H2)", "hikari/reset-fails"),
    ("HikariCP", H, "Isolation only", "Control for the row above", "yes", "Completed", "Cleared", "As above",
     "CONFIRMED BEHAVIOR (control)", "hikari/reset-fails-control"),
    ("HikariCP", H, "Read-only + autocommit + transaction opened by `getSchema()`", "Pool `autoCommit=true`; `close()` throws 25001", "yes",
     "Failed", "Retained: autocommit off, read-only, open transaction; B's insert fails 25006",
     "`autoCommit` and `readOnly` defaults of connections from the pool", "CONFIRMED DEFECT (F-H2)", "hikari/reset-fails-readonly"),
    ("HikariCP", H, "Isolation (configured READ COMMITTED) + `getSchema()`", "`autoCommit=false`, `schema=public`; 25001", "yes",
     "Failed", "Retained: SERIALIZABLE, stale snapshot", "Configured `transactionIsolation`", "CONFIRMED DEFECT (F-H2)",
     "hikari/reset-fails-configured-getschema"),
    ("HikariCP", H, "Isolation + schema (both configured) + `setSchema()`", "As above, trigger `setSchema(\"tenant_a\")`; 25001", "yes",
     "Failed; schema reset skipped", "Retained: SERIALIZABLE; B's committed insert in `tenant_a`",
     "Configured `transactionIsolation` and `schema`", "CONFIRMED DEFECT (F-H2)", "hikari/reset-fails-configured-setschema"),
    ("HikariCP", H, "Isolation (configured) + `setSavepoint()`", "As above, trigger `setSavepoint()`; 25001", "yes",
     "Failed", "Retained: B inside A's transaction, SERIALIZABLE (no stale read: SAVEPOINT takes no snapshot)",
     "Configured `transactionIsolation`", "CONFIRMED DEFECT (F-H2)", "hikari/reset-fails-configured-savepoint"),
    ("HikariCP", H, "Isolation (configured)", "Control: no trigger", "yes", "Completed", "Cleared", "As above",
     "CONFIRMED BEHAVIOR (control)", "hikari/reset-fails-configured-none"),
    ("HikariCP", H, "As the `setSchema()` row", "Then `softEvictConnections()` before B", "no (replacement)",
     "Failed; connection evicted by the probe", "Cleared (B joins the new connection's setup transaction, #1369)", "As above",
     "Recovery control", "hikari/reset-fails-configured-evicted"),
    ("HikariCP", H, "Read-only report, `getSchema()` after `commit()`", "Pool defaults; three later borrowers", "yes (B, C, D)",
     "Failed", "Retained for B, C and D: autocommit off, read-only; inserts fail 25006, 25P02, 25P02; alive check passes",
     "`autoCommit` and `readOnly` defaults", "CONFIRMED DEFECT (F-H2)", "hikari/readonly-report-poison"),
    ("HikariCP", H, "Isolation (configured) + `getSchema()`", "`isolateInternalQueries=true`", "yes",
     "Failed; the alive check's rollback ended A's transaction", "Isolation retained (SERIALIZABLE); fresh snapshot",
     "Configured `transactionIsolation`", "CONFIRMED DEFECT (F-H2); partial mitigation only", "hikari/reset-fails-isolate-internal"),
    ("HikariCP", H, "Read-only report, as above", "`SQLExceptionOverride` returning MUST_EVICT for 25001", "no",
     "Failed; connection evicted", "Cleared", "As above", "Configuration-only mitigation: works", "hikari/readonly-report-override"),
    ("HikariCP", H, "Autocommit (dirty) + isolation + transaction opened by `getSchema()`", "Pool `autoCommit=true`; read-only not dirty", "yes",
     "Completed: the autocommit reset committed the driver-begun transaction, then the isolation reset ran", "Cleared",
     "As above", "CONFIRMED BEHAVIOR (shows why the read-only variant is needed on default pools)", "hikari/autocommit-reset-commits"),
    ("HikariCP", H, "Role, `search_path`, advisory lock, temp table, all set with SQL", "Normal close, `schema=public`", "yes",
     "Not attempted (HikariCP tracks JDBC API calls only)", "Retained: B's insert in `tenant_a` as `ssc_tenant_a`; lock held",
     "No session reset documented", "CONFIRMED BEHAVIOR — NOT A DEFECT (UNSUPPORTED)", "hikari/raw-sql-state"),

    ("HikariCP", HP, "As `reset-fails`", "Patched", "no (closed)", "Failed; connection closed", "Cleared",
     "", "Fix validated", "hikari-patched/reset-fails"),
    ("HikariCP", HP, "As `reset-fails-control`", "Patched", "yes", "Completed", "Cleared",
     "", "Control: output identical to unpatched", "hikari-patched/reset-fails-control"),
    ("HikariCP", HP, "As `reset-fails-readonly`", "Patched", "no (closed)", "Failed; connection closed", "Cleared",
     "", "Fix validated", "hikari-patched/reset-fails-readonly"),
    ("HikariCP", HP, "As `reset-fails-configured-getschema`", "Patched", "no (closed)", "Failed; connection closed", "Cleared",
     "", "Fix validated", "hikari-patched/reset-fails-configured-getschema"),
    ("HikariCP", HP, "As `reset-fails-configured-setschema`", "Patched", "no (closed)", "Failed; connection closed",
     "Cleared (B joins the new connection's setup transaction, #1369)", "", "Fix validated", "hikari-patched/reset-fails-configured-setschema"),
    ("HikariCP", HP, "As `reset-fails-configured-savepoint`", "Patched", "no (closed)", "Failed; connection closed", "Cleared",
     "", "Fix validated", "hikari-patched/reset-fails-configured-savepoint"),
    ("HikariCP", HP, "As `reset-fails-configured-none`", "Patched", "yes", "Completed", "Cleared",
     "", "Control: output identical to unpatched", "hikari-patched/reset-fails-configured-none"),
    ("HikariCP", HP, "As `readonly-report-poison`", "Patched", "no (closed)", "Failed; connection closed",
     "Cleared for B, C and D; inserts succeed", "", "Fix validated", "hikari-patched/readonly-report-poison"),
    ("HikariCP", HF, "As `reset-fails`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails"),
    ("HikariCP", HF, "As `reset-fails-control`", "Completion-flag fix", 'yes', 'Completed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-control"),
    ("HikariCP", HF, "As `reset-fails-readonly`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-readonly"),
    ("HikariCP", HF, "As `reset-fails-configured-getschema`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-configured-getschema"),
    ("HikariCP", HF, "As `reset-fails-configured-setschema`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', "Cleared (B joins the new connection's setup transaction, #1369)", "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-configured-setschema"),
    ("HikariCP", HF, "As `reset-fails-configured-savepoint`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-configured-savepoint"),
    ("HikariCP", HF, "As `reset-fails-configured-none`", "Completion-flag fix", 'yes', 'Completed', 'Cleared', "", "Output identical to the one-line fix", "hikari-patched-flag/reset-fails-configured-none"),
    ("HikariCP", HF, "As `readonly-report-poison`", "Completion-flag fix", 'no (closed)', 'Failed; connection closed', 'Cleared for B, C and D; inserts succeed', "", "Output identical to the one-line fix", "hikari-patched-flag/readonly-report-poison"),
    ("HikariCP", "HikariCP 4.0.3, 5.1.0, 6.3.3, 7.0.2, 7.1.0; pgjdbc 42.7.14", "Isolation (configured) + `getSchema()`",
     "Minimal single-file reproduction, per version", "yes", "Failed", "Retained: SERIALIZABLE, stale snapshot",
     "Configured `transactionIsolation`", "CONFIRMED DEFECT (F-H2), all five versions",
     ["hikari-versions/minimal-4.0.3", "hikari-versions/minimal-5.1.0", "hikari-versions/minimal-6.3.3",
      "hikari-versions/minimal-7.0.2", "hikari-versions/minimal-7.1.0"]),
    ("HikariCP", "HikariCP 4.0.3, 5.1.0, 6.3.3, 7.0.2, 7.1.0; pgjdbc 42.7.14", "Read-only report, `getSchema()` after `commit()`",
     "Minimal single-file reproduction, HikariCP defaults, per version", "yes (B, C, D)", "Failed",
     "Retained for B, C and D: autocommit off, read-only; inserts fail 25006, 25P02, 25P02; 0 rows",
     "`autoCommit` and `readOnly` defaults", "CONFIRMED DEFECT (F-H2), all five versions",
     ["hikari-versions/minimal-readonly-4.0.3", "hikari-versions/minimal-readonly-5.1.0", "hikari-versions/minimal-readonly-6.3.3",
      "hikari-versions/minimal-readonly-7.0.2", "hikari-versions/minimal-readonly-7.1.0"]),
    ("HikariCP", HP, "As the row above", "One-line fix", "no (closed)", "Failed; connection closed",
     "Cleared for B, C and D; 3 rows", "", "Fix validated", "hikari-versions/minimal-readonly-7.1.0-fixed"),
    ("HikariCP", HF, "As the row above", "Completion-flag fix", "no (closed)", "Failed; connection closed",
     "Cleared for B, C and D; 3 rows; output identical to the one-line fix", "", "Fix validated",
     "hikari-versions/minimal-readonly-7.1.0-fixed-flag"),
    ("pgjdbc", "pgjdbc 42.7.14, no pool", "Transaction state", "`getSchema()` with autocommit off", "n/a", "n/a",
     "`getSchema()` leaves the session `idle in transaction`; `setTransactionIsolation()` then fails 25001",
     "Not documented either way; #3005 covers `setSchema()` only", "CONFIRMED BEHAVIOR (contributing trigger)", "hikari-minimal/pgjdbc-getschema"),

    ("asyncpg", A, "`search_path`, custom GUC, advisory lock, LISTEN", "Normal release", "yes", "Completed", "Cleared",
     "Default reset: `pg_advisory_unlock_all()`, `CLOSE ALL`, `UNLISTEN *`, `RESET ALL`", "CONFIRMED BEHAVIOR (positive control)",
     "asyncpg/normal-release"),
    ("asyncpg", A, "Raw `BEGIN` + insert + session changes", "Release with the transaction open", "yes", "ROLLBACK, then reset",
     "Cleared; insert rolled back", "`reset()`: \"an open transaction (if any) is rolled back\"", "CONFIRMED BEHAVIOR", "asyncpg/open-transaction"),
    ("asyncpg", A, "As `normal-release`", "Custom `reset` raises", "no", "Failed → connection terminated", "Cleared",
     "Source: any reset failure terminates the connection", "CONFIRMED BEHAVIOR (safe)", "asyncpg/reset-raises"),
    ("asyncpg", A, "As `normal-release`", "0.5 s custom reset, `release(timeout=0.1)`", "no", "Timed out → terminated client-side",
     "B clean, but A's old backend still runs and holds A's advisory lock: B's `pg_try_advisory_lock` false",
     "As above", "CONFIRMED BEHAVIOR (PostgreSQL notices the disconnect late)", "asyncpg/reset-timeout"),
    ("asyncpg", A, "As `normal-release`", "5 s custom reset, `release(timeout=0.1)`", "no", "Terminated; no cancel request sent",
     "Orphaned backend alive > 1 s, gone < 6 s (log: session 5.011 s)", "As above", "CONFIRMED BEHAVIOR (operational note)",
     "asyncpg/reset-timeout-long"),
    ("asyncpg", A, "As `normal-release`", "`release()` cancelled 0.1 s into a 0.5 s reset", "yes", "Completed under `asyncio.shield`",
     "Cleared; B waited for the reset", "`Pool.release()` shields the release from cancellation", "CONFIRMED BEHAVIOR (safe)",
     "asyncpg/cancel-during-reset"),
    ("asyncpg", A, "As `normal-release`", "Backend terminated before release", "no", "n/a: connection already closed", "Cleared",
     "", "CONFIRMED BEHAVIOR (safe)", "asyncpg/backend-killed"),
    ("asyncpg", A, "As `normal-release`", "Long query cancelled, then immediate release", "yes", "Waited for the cancellation, then reset",
     "Cleared", "", "CONFIRMED BEHAVIOR (safe)", "asyncpg/cancelled-query"),

    ("SQLAlchemy", SA_A, "`search_path` (committed) + uncommitted insert", "Normal `close()`", "yes", "Rollback",
     "Insert rolled back; `search_path` retained", "`reset_on_return='rollback'`; other session state documented to remain",
     "CONFIRMED BEHAVIOR (documented)", "sqlalchemy/async-normal-close"),
    ("SQLAlchemy", SA_A, "As above", "`close()` cancelled during a slow reset", "no", "Interrupted → invalidated", "Cleared",
     "Source: a BaseException in the reset invalidates the record", "CONFIRMED BEHAVIOR (safe)", "sqlalchemy/async-cancel-close"),
    ("SQLAlchemy", SA_S, "As above", "Normal `close()`", "yes", "Rollback", "Insert rolled back; `search_path` retained",
     "As above", "CONFIRMED BEHAVIOR (documented)", "sqlalchemy/sync-normal-close"),
    ("SQLAlchemy", SA_S, "As above", "Backend terminated before `close()`", "no", "Failed → invalidated", "Cleared",
     "", "CONFIRMED BEHAVIOR (safe)", "sqlalchemy/sync-rollback-fails"),

    ("psycopg_pool", PP, "`search_path` (committed) + uncommitted insert", "Block exits with an error; no `reset` callback", "yes",
     "Rollback", "Insert rolled back; `search_path` retained", "Session reset is the user's `reset` callback",
     "CONFIRMED BEHAVIOR (documented)", "psycopg_pool/sync-normal"),
    ("psycopg_pool", PP, "As above", "Backend terminated inside the block", "no", "Rollback failed → discarded", "Cleared",
     "Source: rollback failure discards", "CONFIRMED BEHAVIOR (safe)", "psycopg_pool/sync-rollback-fails"),
    ("psycopg_pool", PP, "As above", "`reset` callback raises", "no", "Failed → discarded", "Cleared",
     "Docs and source: a failing reset discards", "CONFIRMED BEHAVIOR (safe)", "psycopg_pool/sync-reset-raises"),
    ("psycopg_pool", PP, "As above", "Async: long query cancelled", "yes", "Server-side cancel, rollback",
     "Insert rolled back; `search_path` retained", "As the first row", "CONFIRMED BEHAVIOR (documented)", "psycopg_pool/async-cancel-in-query"),
    ("psycopg_pool", PP, "`search_path`", "Async: borrower cancelled while its 0.5 s reset runs in the pool worker", "yes",
     "Completed", "Cleared", "`reset` runs in a worker task", "CONFIRMED BEHAVIOR (safe)", "psycopg_pool/async-reset-cancelled"),

    ("Npgsql", N, "Role, `search_path`, advisory lock, temp table, LISTEN, SQL PREPARE", "Normal close", "yes",
     "Deferred: sent with B's first statement",
     "While idle: lock held, temp table present, competitor blocked; after B's first statement: cleared",
     "Docs: reset \"the next time it's used\", sent \"with the first user statement after the connection is reopened\"",
     "CONFIRMED BEHAVIOR (documented lazy reset)", "npgsql/normal"),
    ("Npgsql", N, "As above", "`No Reset On Close=true`", "yes", "Not attempted", "Retained, all of it",
     "Docs: \"at the cost of leaking state\"", "CONFIRMED BEHAVIOR (documented)", "npgsql/no-reset"),
    ("Npgsql", N, "As above", "Npgsql prepared statement present", "yes", "Reset without `DEALLOCATE ALL`",
     "Cleared, except A's SQL-level PREPARE", "Docs: equivalent statements, \"to prevent closing those statements\"",
     "CONFIRMED BEHAVIOR (minor carryover)", "npgsql/prepared"),
    ("Npgsql", N, "As above, inside a transaction", "Backend terminated before close", "no", "Rollback failed → connector broken",
     "Cleared", "Source: a broken connector is never returned", "CONFIRMED BEHAVIOR (safe)", "npgsql/rollback-fails"),
    ("Npgsql", N, "As above", "Idle connector's backend terminated", "no", "Prepended reset fails → connector broken",
     "Next borrower's first statement throws; the one after gets a clean connector", "No validation on checkout",
     "CONFIRMED BEHAVIOR (loud)", "npgsql/idle-killed"),
    ("Npgsql", N, "Advisory lock", "Idle lifetime 1 s, pruning every 1 s", "n/a", "Connector pruned",
     "Lock held right after close, free 4 s later", "Pruning settings", "CONFIRMED BEHAVIOR", "npgsql/pruned"),

    ("node-postgres", PG, "Role, `search_path`, open transaction", "`release()` without ending the transaction", "yes", "Not attempted",
     "Retained; B's \"autocommit\" insert joins A's transaction and is lost when the connection closes",
     "No reset documented; `release(err)` destroys", "APPLICATION MISUSE (no reset is promised)", "node/open-transaction"),
    ("node-postgres", PG, "Aborted transaction", "`release()` after a failed statement", "yes", "Not attempted",
     "B's first statement fails 25P02", "As above", "APPLICATION MISUSE", "node/aborted-transaction"),
    ("node-postgres", PG, "As `open-transaction`", "`release(err)`", "no", "Client destroyed", "Cleared", "As above",
     "CONFIRMED BEHAVIOR", "node/release-err"),
]


def evidence(paths):
    paths = [paths] if isinstance(paths, str) else paths
    digests, files = set(), 0
    for p in paths:
        reps = sorted(glob.glob(f"output/{p}.rep*.out"))
        if not reps:
            sys.exit(f"no outputs for {p}")
        files += len(reps)
        digests |= {hashlib.sha256(open(f, "rb").read()).hexdigest()[:12] for f in reps}
    link = ", ".join(f"[`{p}`](output/{p}.rep1.out)" for p in paths)
    digest = digests.pop() if len(digests) == 1 else "DISAGREE"
    return f"{link} `{digest}`", str(files) + (" (all identical)" if digest != "DISAGREE" else "")


print("""# Results matrix

Generated by [`analysis/build_matrix.py`](analysis/build_matrix.py) from the recorded outputs. Every row's repetitions are byte-identical; the hash is the first 12 hex digits of each repetition's SHA-256. "Same backend" means the same backend PID *and* `backend_start`, as the observer read them. Pool size 1 throughout. PostgreSQL 18.6.

Classifications follow the research brief. "KNOWN UPSTREAM" marks behaviour already reported in an open or closed issue: it is reproduced here, not new. The report is [`README.md`](README.md).

| Framework | Driver/pool | State category | Scenario | Same backend | Cleanup result | Observed state | Contract | Classification | Evidence | Repetitions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |""")
for row in ROWS:
    ev, reps = evidence(row[9])
    cells = list(row[:9]) + [ev, reps]
    print("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
