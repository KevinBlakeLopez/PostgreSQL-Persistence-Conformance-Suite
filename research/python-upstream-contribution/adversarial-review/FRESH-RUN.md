Written by: GPT-6 / Codex (effort setting not exposed)
Date: 2026-10-24 (America/Los_Angeles)

# Independent fresh execution

**VERIFIED — result.** Both draft reproductions now have a fresh execution by this reviewer. All eight standalone executions exited 0 and matched the earlier recorded results. Asyncpg ran three times on asyncio and three on uvloop; the original psycopg transaction program ran once, including its built-in three repetitions and controls. The additional psycopg pipeline-pattern program also ran once, including its six arms. Both revised drafts remain **READY** (INFERRED review verdict).

**VERIFIED — comparison.** The six asyncpg outputs match their respective original files after masking only transaction IDs. No header, result, exception message, or other output was masked. The psycopg transaction output and pipeline-pattern output are each byte-identical to their original recordings. The exact three source scripts were copied unchanged and their SHA-256 values checked before comparison. See [fresh-verification.txt](fresh-verification.txt) and [fresh-run-records.zip](fresh-run-records.zip).

## Observed results

| Program / arm | Fresh observation | Independent database observation |
| --- | --- | --- |
| Asyncpg managed, six executions | VERIFIED block exited normally after caught 23505 | VERIFIED aborted fate and absent marker in separate-connection witness; all six fates corroborated by psql |
| Asyncpg explicit, six executions | VERIFIED commit returned None; subsequent rollback raised InterfaceError saying already committed | VERIFIED aborted fate and absent marker; all six fates corroborated by psql |
| Asyncpg raw, six executions | VERIFIED execute('COMMIT') returned 'ROLLBACK' | VERIFIED aborted fate and absent marker; all six fates corroborated by psql |
| Asyncpg savepoint control, six executions | VERIFIED error caught outside inner block; outer block exited normally | VERIFIED committed fate and visible marker; all six fates corroborated by psql |
| Psycopg transaction, caught arm, three repetitions | VERIFIED INERROR before exit; no exit exception; Transaction.status committed; IDLE afterward | VERIFIED separate connection read aborted fate, absent marker, idle subject with last statement COMMIT |
| Psycopg transaction, recovered arm, three repetitions | VERIFIED INTRANS before exit; normal exit and committed status | VERIFIED separate connection read committed fate and visible marker |
| Psycopg normal transaction control | VERIFIED committed status | VERIFIED separate connection saw marker |
| Psycopg pipeline pattern, three unmarked arms | VERIFIED UndefinedColumn caught; INERROR before exit; normal exit and committed status | VERIFIED separate connection observed idle subject and last statement COMMIT; no xid/marker outcome is captured in these unmarked arms |
| Psycopg pipeline pattern, three witnessed arms | VERIFIED same API/status observations as unmarked arms | VERIFIED separate connection read aborted fate and absent marker |

**VERIFIED — independent psql corroboration.** A psql process inside the new server container, without either Python driver involved, read all 24 asyncpg transaction IDs after the programs finished. All24 matched: 18 aborted, six committed. The query and its complete output are preserved. The fresh server log independently associates each asyncpg subject PID, application name, transaction ID, 23505 error and final COMMIT. Savepoint controls include SAVEPOINT and ROLLBACK TO; other asyncpg arms sent no ROLLBACK. The psycopg log shows six original-block caught/recovered sessions and six pipeline-pattern sessions ending with COMMIT. See [fresh-psql-xact-status.txt](fresh-psql-xact-status.txt) and [fresh-server.log](fresh-server.log).

**VERIFIED — no result discrepancy.** Transaction IDs changed because this was a newly initialized cluster. The observed behavior, Python/client versions, server version and client architecture matched the originals. The comparison did not normalize away any other difference.

## Environment and isolation

| Item | Verified value / record |
| --- | --- |
| Client | Python 3.13.11, macOS 26.6.2, Darwin arm64 |
| Packages | asyncpg 0.32.0, uvloop 0.23.0, psycopg 3.3.6 and psycopg-binary 3.3.6 |
| Installation | Fresh temporary virtualenv; pip `--isolated`, explicit `https://pypi.org/simple`, `--only-binary=:all:`, `--no-cache-dir`; installation report confirms files.pythonhosted.org wheel URLs and hashes |
| PostgreSQL | 18.6 (Debian 18.6-1.pgdg13+2), aarch64 Linux |
| Image | `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`, locally inspected image ID matched the digest |
| Server owner | Container OS user postgres, uid 999/gid 999, recorded with `id` |
| Cluster | New `initdb` directory `/tmp/fresh-pg` in container tmpfs; UTF8, locale C; no preexisting data directory reused |
| Port | 55537 inside container and published on host 127.0.0.1:55537; no default-port connection |
| Identity check | Random cluster_name matched through the new server's host port before any reproduction ran |
| Settings read back | read committed; synchronous_commit on; statement_timeout 0; idle_in_transaction_session_timeout 0; log_statement all; log_error_verbosity verbose |
| Successful server | `ppcs-independent-9494ecd996de`, started 2026-10-24T21:38:40.609116Z; run/cleanup ended 21:38:45.579605Z |
| Removal | `docker stop` succeeded; `--rm` removed the container and tmpfs cluster; subsequent `docker inspect` reported no such object |

**VERIFIED — setup variations.** The client/server versions and architecture match the original recordings. This reviewer used direct non-root initdb and a read-only container filesystem with tmpfs data, rather than the image's normal initialization entrypoint. Authentication used trust for the disposable cluster's local connection and Docker gateway address 172.17.0.1/32; host publication remained loopback-only. Log verbosity included SQLSTATEs. Original CHK-2 explicitly enabled log_lock_waits, while this run left that setting at its image/initdb default. The complete successful configuration and commands are retained in the bundle. No observed outcome differed under this setup.

## Records and commands

**VERIFIED — complete bundle.** `fresh-run-records.zip` contains the exact three reproduction scripts, runner and verifier source, all eight complete stdout/stderr captures, successful server log, psql query/output, environment, wheel-install report and log, package freeze, argv/timing/exit-code transcript, server user/identity/access-rule captures, cleanup records, and failed setup/analysis records. The virtualenv itself is excluded. No old evidence or draft was overwritten.

**VERIFIED — package installation command executed:**

```sh
/opt/homebrew/bin/python3.13 -m venv /private/tmp/ppcs-fresh-run-20261024/venv
/private/tmp/ppcs-fresh-run-20261024/venv/bin/python -I -m pip --isolated install \
  --index-url https://pypi.org/simple --only-binary=:all: --no-cache-dir \
  --disable-pip-version-check \
  --report /private/tmp/ppcs-fresh-run-20261024/pip-install-report.json \
  asyncpg==0.32.0 uvloop==0.23.0 'psycopg[binary]==3.3.6'
```

**VERIFIED — runtime commands.** The runner invoked the fresh virtualenv Python with `-I` for every program. Its exact argv and DATABASE_URL values are in `execution-commands.json` inside the bundle. The asyncpg DSN was `postgresql://postgres@127.0.0.1:55537/postgres`. The psycopg DSNs appended application_name values for server-log identification; program source was unchanged. No password/token authentication was used, so these DSNs contain no credential secret. The fresh cluster_name is a disposable identity marker, not an authentication credential.

## Failures retained, and limits

**VERIFIED — setup failures.** Two earlier fresh containers were removed before any reproduction ran. The first host connection was refused during setup; a second attempt retried host readiness and its server log showed the Docker gateway rejected by the default pg_hba rules. A subsequent runner edit had a syntax error before starting a server. Those scripts, logs, command transcripts and cleanup records are preserved with attempt1/attempt2/attempt3 prefixes. Correcting the disposable cluster's gateway rule allowed the successful run above. No failed experiment result was replaced by a successful one: the eight reproduction programs were executed only in the successful attempt.

**VERIFIED — analysis correction.** The first post-run log verifier assumed two spaces after the SQLSTATE prefix, but fresh verbose logs used one. It failed after completing all original-output comparisons and the psql comparison. Its source and partial output are retained as `verify-failed-parse.*`. The corrected verifier uses whitespace-tolerant parsing, passed all comparisons and log checks, and is preserved as `verify_fresh.py`. Recorded reproduction outputs were not edited.

**NOT CHECKED — unchanged boundaries.** This run did not execute upstream pytest suites, implement a fix, rerun P6's other SQLSTATEs, or rerun SQLAlchemy/Tortoise. It did not test other PostgreSQL/client versions, a Linux client, pgbouncer, pools, AsyncConnection.transaction, COMMIT queued while a psycopg pipeline remains open, or a COMMIT that itself raises. The pipeline script reproduces an upstream test's pattern with try/except in place of pytest.raises; it is not an execution of that upstream pytest test. The managed COMMIT command tag is still inferred from source/raw-arm evidence, rather than captured directly from a protocol trace of the managed call.

**VERIFIED — repository preservation.** Before packaging, repository status, tracked diff hash and both draft hashes matched the pre-run baseline. Deliverables are confined to new files in the existing adversarial-review directory. The old review, recheck, source evidence, drafts, tracker and roadmap were left unchanged by this fresh execution.
