# PY-8 review package

Prepared on 2026-10-25, between about 04:50 and 06:05 UTC. Written by: Claude Opus 5.5 (max).

This package is for an independent correctness review of a small Tortoise ORM patch before it is proposed upstream. Nothing in it has been committed, pushed or posted.

**The patch.** In the asyncpg and psycopg backends, `TransactionWrapper.commit()` translates an integrity error raised by `COMMIT` (SQLSTATE class 23, for example a deferred foreign key) into `tortoise.exceptions.IntegrityError`. Other errors pass through unchanged. Two PostgreSQL-only tests and a changelog entry come with it. It sits uncommitted on branch `fix/commit-integrity-error` of a local clone of `tortoise/tortoise-orm`, based on `develop` `ad0d6ce2b878f6d5188374eabb61d80484aedfa4`.
- **The current diff** is `../branch/fix-v2.patch`, SHA-256 `8f2244c160004a266908ebb260f8ee080c61cf895402636befb843f6b3bdcfd8`.
- **The runs used `../branch/fix.patch`,** SHA-256 `ac1bad08bc41016ca597885db9170cbe6065eb9d6dcbc66dfce24b60356a1540`.
- The two differ only in the changelog line, which now names `update_or_create()` too, as the assessment recommended (8.9).

## How to read it

1. [`materials.md`](materials.md), items 1–4. The complete diff, then verbatim excerpts:
   - the transaction code of both backends, the transaction contexts and the exception translators, plus the driver code they call (asyncpg 0.31.0, psycopg 3.3.3, psycopg-pool 3.3.0);
   - `get_or_create()`, `_create_or_get()` and `update_or_create()`;
   - the `db_isolated` fixture, the `IntFields` model, and the surrounding tests.

   Every excerpt gives its path, line range and file hash. [`make_materials.py`](make_materials.py) regenerates it.
2. [`assessment.md`](assessment.md), items 5–8. The `update_or_create()` reproducer, connection reuse after a failed COMMIT, exception chaining, the remaining failure modes, a classification of each concern, and a recommendation. It is a separate file so that the materials can be read first.

The rest of the evidence for this patch is in the parent directory's README: step 1 (verification and four candidate designs) and step 2 (the branch).

## The runs behind items 5, 6 and 8.4

| Program (parent directory) | Outputs | Runs |
| --- | --- | --- |
| `chk_update_or_create.py` | `output/update-or-create/{develop,branch}-{asyncpg,psycopg}.rep{1,2,3}.out` | 12, all exit 0 |
| `chk_connection_reuse.py` | `output/connection-reuse/{develop,branch}-{asyncpg,psycopg}.rep{1,2,3}.out` | 12, all exit 0 |
| `chk_explicit_commit.py` | `output/explicit-commit/{develop,branch}-{asyncpg,psycopg}.rep{1,2,3}.out` | 12, all exit 0 |

- **Develop and branch.** "Develop" ran Tortoise from a detached `git worktree` of `origin/develop` `ad0d6ce2b878`, put first on `sys.path` through `PY8_TORTOISE_SRC`; the worktree was removed afterwards. "Branch" ran the checkout with the patch. The branch checkout was never modified, and its `git diff` hashed the same before and after.
- **Environment.** Both used the clone's virtualenv: Python 3.13.11, asyncpg 0.31.0, psycopg 3.3.3, psycopg-pool 3.3.0.
- **Repetitions.** Each group's three repetitions are byte-identical.
- **Servers.** Two throwaway containers, each removed after its runs. Each ran `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` on `127.0.0.1:55497`, with a tmpfs data directory, a random password and `cluster_name` token, and `log_statement=all`.
  - The first served items 5 and 6, 05:04:03–05:04:10 UTC. Full log: 2,247 lines, SHA-256 `e8a4c4634bebe5895be6b725b0a770bc84d97f5ff70767d15f37d8c54c53cb8a`.
  - The second served item 8.4, 05:08:24–05:08:28 UTC. Full log: 957 lines, SHA-256 `c0eb59a82667e04f6c4dd26c8e94f0e97eec628ac60ede4fb729a1e3f195e16c`.
  - The full logs are not kept. `output/server-log-extract*.txt` hold the subject sessions, and `output/server-log-transcripts*.txt` their per-run statement transcripts, identical across repetitions.
- **Independent checks.** These programs print transaction fates read by a separate connection, but not the transaction IDs, so the step-1 `psql` cross-check did not apply. The server-log transcripts are the second source.

```sh
# DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55497/postgres; <python> is the clone's virtualenv.
for program in chk_update_or_create.py chk_connection_reuse.py chk_explicit_commit.py; do
  for label in develop branch; do for b in asyncpg psycopg; do for rep in 1 2 3; do
    PY8_TORTOISE_SRC=<develop worktree or branch checkout> PY8_SRC_LABEL=$label PY8_REP=$rep \
      <python> -I -B $program $b > review/output/<dir>/$label-$b.rep$rep.out 2>&1
  done; done; done
done
```

**Changes during preparation:**
- Trial runs, on separate containers, changed two programs before their recorded runs. `chk_update_or_create.py` now prints real row ids and the competitor's id. `chk_connection_reuse.py` now wraps asyncpg's `Pool.release` on the class, because asyncpg's `Pool` defines `__slots__`. No trial output is kept.
- `../server_log_check.py` now also extracts `py8-uoc-` and `py8-reuse-` sessions. Its step-1 and step-2 checks and transcripts reproduce byte-identically after the change.
