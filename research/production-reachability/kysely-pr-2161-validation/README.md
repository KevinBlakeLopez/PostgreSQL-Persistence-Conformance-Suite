# Kysely PR #2161 against the #2157 reproduction

Written by: Claude Opus 5.5 (max). Run 2026-10-25.

**Posted:** 2026-10-25 as https://github.com/kysely-org/kysely/pull/2161#issuecomment-6403967170, as `KevinBlakeLopez`. The proposed tracker ID is Y3.
- **Before posting:** the PR head was still `ef60ffe`, the PR had no human comments or reviews, and the content guard passed.
- **After posting:** the body returned by the API (`out/posted-body.md`) matches `comment.md`.

**What was validated:** [kysely-org/kysely#2161](https://github.com/kysely-org/kysely/pull/2161), Igal Klebanov's fix for [#2157](https://github.com/kysely-org/kysely/issues/2157) (Y2), at head `ef60ffe70ecf78c7e2d1a4aa7961924c3c6bc757`.

**The two builds:**

| Label | Build | Identity |
| --- | --- | --- |
| `base` | npm `kysely@0.29.7`, which is the PR's base commit `ac876c212c` (tag `v0.29.7`) | `sha512-fmIq+7kv4WbFm2tcfznRzikqB4cuNpgZ40PSU2fAJ2/OO5XhojqnTPrmgrCjYSRJVwBln03XcRXJGnw9H099IQ==` |
| `pr` | `https://pkg.pr.new/kysely@ef60ffe70ecf78c7e2d1a4aa7961924c3c6bc757` (tarball not kept here) | tarball sha256 `d877e4dcdf23016afa22c384aa6dd32113b498eb9b9e91e6338c8e0617573fdc` |

- The PR build also reports version `0.29.7`. Its `dist/` contains `driver/aborted-transaction-error.js` and the new `commitTransaction` check.
- The `lock/` folder has each build's `package.json` and `package-lock.json`.

**Environment:**
- **Versions:** pg 8.23.1 and Node.js v24.14.1, the same as in #2157.
- **Server:** PostgreSQL 18.6 (`postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`) ran in a throwaway container with `log_statement=all`. The container has since been removed.
- **Isolation:** packages were installed with `--ignore-scripts`. Both scripts ran behind a network guard that allowed only the container's port.

## Matrix (`scripts/validate-2161.mjs`)

Each case ran 3 times per build. In every case, all 3 repetitions agreed. No rejection went unhandled.

**Ground truth** came from an independent pg connection:
- `pg_xact_status()` of the transaction's xid;
- whether the row is visible.

**Reuse check.** A one-connection pool gets the scenario's backend back. `pg_stat_activity` must show it `idle` with no transaction. An autocommit write on it must then be visible from the independent connection.

| Case | base 0.29.7 | pr `ef60ffe` |
| --- | --- | --- |
| s1 `startTransaction()`, caught `23505`, `commit()` (#2157) | resolves; `isCommitted` true; aborted, no row | rejects `AbortedTransactionError`; `isCommitted` false, `isRolledBack` true; aborted, no row |
| s2 `transaction().execute()`, caught `23505`, callback returns (#2157) | resolves; aborted, no row | rejects `AbortedTransactionError`; aborted, no row |
| s3 control: explicit commit | committed, row kept | same |
| s4 control: managed commit | committed, row kept | same |
| s5 control: savepoint, caught `23505`, `rollbackToSavepoint`, commit | committed, row kept | same |
| s6 control: explicit, deferred FK fails at `COMMIT`, caller rolls back | `commit()` rejects `23503`; `rollback()` resolves; aborted | same |
| s7 control: managed, deferred FK fails at `COMMIT` | rejects `23503`; aborted | same |
| s8 0.29.7 docs pattern (`rollback()` in the catch) after a caught `23505` | resolves silently; `isCommitted` true; aborted | rejects `Error: Transaction is already rolled back` (from `rollback()`); `isRolledBack` true; aborted |
| s9 rows from raw `sql\`commit\``, `sql\`rollback\``, `sql\`rollback to savepoint s\`` | `[]`, `[]`, `[]` | `[{command:'COMMIT'}]`, `[{command:'ROLLBACK'}]`, `[{command:'ROLLBACK'}]` |
| Reuse after every case | same backend, idle, no transaction, autocommit write visible | same |

**The server log** (`out/server.log`, repetition 1) shows:
- **s1 and s2, both builds:** `COMMIT` is the last statement of the aborted transaction. No further `ROLLBACK` follows, which matches the PR's "without sending another rollback".
- **s8 on `pr`:** `rollback()` sends nothing, because it is refused on the client.
- **s7:** after the failed `COMMIT`, the managed path sends its usual `rollback` on both builds, and PostgreSQL warns "there is no transaction in progress".

## Standalone reproduction (`scripts/repro-2157.mjs`)

This is the script in the comment's `<details>`. Each build ran a copy that differs only in its two import lines, which point at that build's files:
- the copies are `scripts/run-base/` and `scripts/run-pr/`;
- local paths in them are replaced by `$RUN_DIR`.

Each build ran 3 times. Within a build, the output was byte-identical across runs (`out/repro-<build>-r<n>.out`):

```
# base 0.29.7 (sha256 04e7f3af…)
startTransaction: commit resolved, isCommitted=true, isRolledBack=false, pg_xact_status=aborted, rows=0
transaction().execute(): resolved, pg_xact_status=aborted, rows=0
# pr ef60ffe (sha256 41c50e40…)
startTransaction: commit rejected (AbortedTransactionError), isCommitted=false, isRolledBack=true, pg_xact_status=aborted, rows=0
transaction().execute(): rejected (AbortedTransactionError), pg_xact_status=aborted, rows=0
```

## The comment

`comment.md` is the posted text. It includes:
- s1, s2 and the standalone output;
- one sentence on the controls (s3–s7) and on reuse;
- the s8 heads-up.

It leaves out s9 as minor.

## Limits

- PostgreSQL only. The PR changes only the Postgres dialect.
- The pg JavaScript client only, not `pg-native`.
- Standalone scripts, not Kysely's test suite. The PR's 88 transaction tests were not run here.
- One machine: macOS arm64 under colima.

## Files

| File | sha256 |
| --- | --- |
| `scripts/validate-2161.mjs` | `3c05280d9c8f6f3d3b896b289b0a48c8242d0882e62a465648456bfb341bd718` |
| `scripts/repro-2157.mjs` | `122fb812c5718cc3ec22411df40acd9ba818df874bc76b4a98259f893b9cb5e9` |
| `scripts/net-guard.mjs` | `e490dcf352d9d183b0e3db4c992a8d50f10b0f0f9ba613b812582b98deb880e8` |
| `out/base.jsonl` | `4594cb5759e0378d7a2d9ba27fb43727f2075bb1be644ae64fda4cae9c2715f2` |
| `out/pr.jsonl` | `0c7d7f2b898feff5d38cb1fbb6cac3dc461dac2c4924009c32cdd9ee5d38b16a` |
| `out/server.log` | `47dab0fa3b761078bcf72909d7a966cac416ae986a760a166bd74a8e2c7d2888` |
| `out/repro-base-r{1,2,3}.out` (identical) | `04e7f3af7ce41eb4c391ebb6fca581f958b251c81d223d16d74a0ffa43b5f56e` |
| `out/repro-pr-r{1,2,3}.out` (identical) | `41c50e40f78c51e4efef20fc9fd5731b1ef8c273cf058f12b9d58b4ff1148564` |
