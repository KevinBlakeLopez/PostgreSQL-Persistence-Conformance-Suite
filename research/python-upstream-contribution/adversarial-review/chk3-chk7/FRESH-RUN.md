# Fresh-run record for CHK-3 and CHK-7

Review date: 2026-10-24. Written by: GPT-6 (effort setting not exposed).

All paths prefixed R below are under `/private/tmp/chk3-chk7-review.tPQMYZ/`. This directory and the two review Markdown files are review-owned and local. Required programs ran unchanged with `-I`. No author log-summarizer or verbatim-check helper was executed. No reviewed file was changed.

## Environment and commands

The client is macOS arm64, Python 3.13.11 from `/opt/homebrew/bin/python3.13`. The primary container was `ppcs-chk3-chk7-review-f0dd84c6`, using the pinned image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336`. It mapped both `127.0.0.1:55492` and `127.0.0.1:55454` to its own PostgreSQL port 5432 so both original programs could run unchanged, in different databases. It used `--tmpfs /var/lib/postgresql`, a random password and cluster_name, `log_statement=all`, `log_connections=on`, `log_disconnections=on`, and `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '`. Server version is 18.6 (Debian 18.6-1.pgdg13+2).

Both host ports were free in active `DOCKER_CONTEXT=colima docker ps` and `nc -z`. `sa-tx-probe` was stopped and remained stopped. No Colima start/stop/configuration action occurred. `ppcs-postgres` and other containers were not accessed except by the initial read-only inventory. Every Docker subprocess used `DOCKER_CONTEXT=colima` through its environment.

Before database mutation, the host connection to 55492/postgres verified the random cluster token. A host connection to 55454/scratch verified the same token before subject runs. After setup, the host app_login connection verified the token and `rolsuper=False`. Random secrets were held in process memory and the temporary mode-0600 libpq passfile outside the repositories; that passfile was removed. No credentials appear in saved commands or logs. The app password was passed only through `CHK3_APP_PASSWORD`; the setup disables its SQL statement logging before ALTER ROLE. The whole saved log was checked against both actual generated passwords before being written.

Two fresh virtualenvs were built outside the repositories:

```sh
/opt/homebrew/bin/python3.13 -m venv R/venv-psycopg
R/venv-psycopg/bin/python -I -m pip install --only-binary=:all: --no-cache-dir SQLAlchemy==2.1.6 psycopg==3.3.6 psycopg-binary==3.3.6 typing_extensions==4.16.0
/opt/homebrew/bin/python3.13 -m venv R/venv-psycopg2
R/venv-psycopg2/bin/python -I -m pip install --only-binary=:all: --no-cache-dir SQLAlchemy==2.1.6 psycopg2-binary==2.9.13 typing_extensions==4.16.0
```

The first pip attempt was sandbox-network blocked and installed no packages; the approved network retry installed the exact wheels. Both environments have pip 25.3, SQLAlchemy 2.1.6 and typing_extensions 4.16.0. Psycopg environment: psycopg 3.3.6, psycopg-binary 3.3.6, binary implementation, libpq 180006. Psycopg2 environment: psycopg2-binary 2.9.13, libpq 170011. Greenlet is absent; each environment contains only its intended driver. Both SQLAlchemy wheel RECORD audits pass 270/270 module files, and all fetched cited modules agree with rel_2_1_6. Full freezes are saved in R/versions-*.txt.

`R/run_review.py` is the exact executable orchestration; R/fresh/commands.json records each original script invocation and exit/hash. Its main invocation was:

```sh
R/venv-psycopg/bin/python -I R/run_review.py
```

It performs the token checks, runs C3/chk3_setup.py, runs C3/chk3_reset_recipe.py three times per driver with driver/rep arguments, runs C3/demo_reset_recipe.py three times per driver, and runs the unchanged ORM check/p5a_close_v2.py three times. It captures stdout/stderr, runs psql checks and the independent witness-row query, saves password-free server logs, queries actual logged XIDs through psql, compares output bytes, and removes only its own container in finally. `DOCKER_CONTEXT=colima docker exec ... psql` is used because host psql is not installed. This is an independent server client, not an API return-value verdict.

## Required output comparison

| Fresh outputs (each r1,r2,r3) | SHA-256, identical across repetitions | Comparison |
| --- | --- | --- |
| fresh/chk3-psycopg-r*.out | 5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac | Exact recorded combined stdout/stderr |
| fresh/chk3-psycopg2-r*.out | f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e | Exact recorded combined stdout/stderr |
| fresh/demo-psycopg-r*.out | a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2 | Exact recorded stdout |
| fresh/demo-psycopg2-r*.out | 0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31 | Exact recorded stdout |
| fresh/demo-psycopg-r*.masked.stderr | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | Exact recorded empty stderr |
| fresh/demo-psycopg2-r*.masked.stderr | 9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6 | Exact recorded stderr after only venv/directory prefix masking |
| fresh/chk7-r*.out | fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39 | Exact check/p5a_close_v2.out and draft Observed block |

All 15 subject executions exited 0. There are 21 exact byte comparisons including normalized demo stderr, all true in fresh/comparison.json. P5a raw stderr contains the expected two reset exceptions per run; normalization of the temporary virtualenv prefix yields the recorded 2.1.6 stderr, with its original script path unchanged. The older 2.1.5 e0 comparison still has only the two documented line-number shifts. No PIDs, rep numbers or timestamps appear in the outputs required to match. Log PIDs/vxids/XIDs/timestamps differ normally. The 48-row psql item output also matches the recorded output exactly. The psql mechanism-check output is semantically the same, but fresh stderr was concatenated after stdout, moving its expected DISCARD ALL error to the end; that file is not byte-identical.

## Independent log reading and transaction fates

`R/audit_logs.py` is this review's independent parser; it does not call the author's helpers. It reconstructs the six original per-run extracts from the original full log and matches every byte. Its fresh findings are in R/log-audit.json. The table in REVIEW.md records every required arm's hook-session SQL and outcome. Representative fresh lines:

- fresh/server.log:182–186, backend 85, vxid 8/4: `BEGIN`, `CLOSE ALL`, `RESET ALL`, `DISCARD TEMP`, `ROLLBACK`; reset xid 768. Lines 194–198 repeat the reset as xid 770. These are aborted in fresh/psql-xact-status.txt. All six fresh program documented-reset XIDs have aborted status.
- Corrected ordinary hook, backend 86: lines 233 and 241 are standalone `DISCARD ALL` under distinct vxids. Prepared arm, backend 91: lines 450–451 are `DISCARD ALL`, then driver `DEALLOCATE ALL` under another vxid; later `_pg3_1` execution is successful.
- Psycopg2 REPEATABLE READ, backend 121: lines 1562–1563 and 1569–1570 show `DISCARD ALL` then `SET default_transaction_isolation TO DEFAULT`, followed by the next repeatable-read BEGIN.
- P5a case 1: backend 163/vxid 80/3 contains both inserts and COMMIT, with no intermediate end, lines 2521–2532; logged COMMIT xid 945 is committed. Repetitions 2/3 are backend 167/vxid 84/3/xid 952 and backend 171/vxid 88/3/xid 959, also committed. Case 2 similarly commits 947, 954, 961. Case 3's discarded backends are 164,168,172; each disconnects after doomed without COMMIT. No old case-3 XID was inferred from gaps.

The server log confirms the demo's two documented psycopg reset blocks per invocation, no reset SQL before each psycopg2 documented connection disconnects, and standalone DISCARD ALL for each corrected return. The original demo's raw stderr checksums match its recorded runs.txt; replacing only the two permitted path prefixes reproduces all saved masked copies exactly. The original full-log SHA checks also pass.

## Supplemental counterexamples and optional coverage

The primary container additionally ran fresh/hold-cursor.sql through psql. It showed a WITH HOLD cursor before the reset command sequence and zero remaining cursors after that sequence rolled back. That single-run counterexample falsifies “resets nothing”; it does not change any required output.

The second own container was `ppcs-chk3-chk7-supp-3b61238a`, on 127.0.0.1:55492, using the same pinned image, tmpfs, random credentials/token and transaction-aware logging. `R/supplemental.py` verifies its token through the host before running setup and extracts the unchanged documented/corrected hook ASTs for its controls. Invocation:

```sh
R/venv-psycopg/bin/python -I R/supplemental.py
```

Its corrected-hook/open-transaction controls each ran three times with reset_on_return=None and three times with reset_on_return='rollback'. The exact result was same_dbapi=true, role=app_login, uncommitted_rows=0, transaction_was_reset=true. The witness is a separate raw autocommit connection. Its documented-hook AUTOCOMMIT control ran once and reset the GUC/search_path/timeout/temp table while keeping tenant_a. Its psql first-write control ran once: SELECT pg_current_xact_id() assigned xid 772 before the first INSERT, and the INSERT log already carries 772. This falsifies the generic first-write-xid=0 sentence. Scripts, full outputs, raw logs and cleanup are retained in R/supplemental.

## Clone-only plan probe and integrity checks

`R/probe_plan.py` creates R/plan-clones/{orm,ppcs} using git clone --shared, copies the untracked evidence and tracker bytes from the reviewed roots, and executes the original plan against those clone paths. Its hook changes only a clone README and runs the real content guard. The plan exits 0 despite a manifest/committed-blob mismatch; R/plan-probe.json and plan-probe.stdout/stderr preserve the result. Three commits exist only in the disposable clones. The separate others-probe.json demonstrates unchanged snapshots after changing a clone's untracked file. No content-guard rule or configuration was modified.

Starting manifest: 75/75 files match, 0 differences. README checksum audit: all 71 enumerated hash checks pass (including the two external original full logs), plus all six original raw-demo checksum checks pass. Verbatim/AST and draft-output checks all pass. The current tracked P5a program retains hash 52bab81dcc588b53e78a83f38e29549b74d8b445ed1c946365b05315c08984b3, identical to its version in cca9b98. Full checksum details are in R/audit.json. Final manifest/status verification is recorded at the end of REVIEW.md.

## Cleanup and created-file inventory

Both review containers were removed by their own script finally blocks and their names were verified absent from `DOCKER_CONTEXT=colima docker ps -a`. R/fresh/cleanup.txt and R/supplemental/cleanup.txt record removal. Both temporary passfiles were removed. No other container was started, stopped, removed or reconfigured.

Created repository directory: `$WORKTREE/research/python-upstream-contribution/adversarial-review/chk3-chk7/`, containing only REVIEW.md and FRESH-RUN.md. It stays local and untracked. Created temporary root: `/private/tmp/chk3-chk7-review.tPQMYZ/`, including orchestration/audit/report-building scripts, two virtualenvs, fresh and supplemental evidence, fetched upstream records, clone-only repositories, JSON audits, the two prepared Markdown files and inventory/hash lists. Those are all this review's filesystem creations. The downloaded packages live only in the virtualenvs; --no-cache-dir avoided a pip cache.

`R/CREATED-FILES.txt` enumerates every created file and directory, including the clone Git metadata and virtualenv contents, with directory markers. Removed passfiles are explicitly listed there as removed. `R/OUTPUTS.sha256` lists every retained fresh/supplemental output checksum; `R/ARTIFACTS.sha256` lists the other retained non-venv, non-clone evidence/script hashes. Removing the review directory and the single temporary root removes all retained review artifacts; the clones' alternates read original objects but do not own them. Do not delete any pre-existing author scratch directory or repository sibling review.

## Retained output hashes

| Output relative to R | SHA-256 |
| --- | --- |
| fresh/chk3-psycopg-r1.out | `5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac` |
| fresh/chk3-psycopg-r2.out | `5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac` |
| fresh/chk3-psycopg-r3.out | `5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac` |
| fresh/chk3-psycopg2-r1.out | `f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e` |
| fresh/chk3-psycopg2-r2.out | `f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e` |
| fresh/chk3-psycopg2-r3.out | `f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e` |
| fresh/chk7-r1.out | `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` |
| fresh/chk7-r1.stderr | `34474b91c44dffd0feff58903e6f30b381826283f7fe7e2ae46f221ce2c6b1a7` |
| fresh/chk7-r2.out | `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` |
| fresh/chk7-r2.stderr | `34474b91c44dffd0feff58903e6f30b381826283f7fe7e2ae46f221ce2c6b1a7` |
| fresh/chk7-r3.out | `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` |
| fresh/chk7-r3.stderr | `34474b91c44dffd0feff58903e6f30b381826283f7fe7e2ae46f221ce2c6b1a7` |
| fresh/cleanup.txt | `3cbd5dc0db838c8228058429346a55de3ed2a7bea667e8654ea1ac59f103d342` |
| fresh/commands.json | `d1e67a4f46120e8f6670f23f4a8687ee61fbf26833485e09f8af52178f163a6e` |
| fresh/comparison.json | `a10fb149c925e8b879209a74ed256e3dbfdb836b27a596c375efa250e6dc48c7` |
| fresh/demo-psycopg-r1.masked.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg-r1.out | `a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2` |
| fresh/demo-psycopg-r1.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg-r2.masked.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg-r2.out | `a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2` |
| fresh/demo-psycopg-r2.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg-r3.masked.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg-r3.out | `a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2` |
| fresh/demo-psycopg-r3.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| fresh/demo-psycopg2-r1.masked.stderr | `9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6` |
| fresh/demo-psycopg2-r1.out | `0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31` |
| fresh/demo-psycopg2-r1.stderr | `490591f7b1abbd4fa2bdc52e24eae2611f6d1773ab199df100095c13d8786b82` |
| fresh/demo-psycopg2-r2.masked.stderr | `9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6` |
| fresh/demo-psycopg2-r2.out | `0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31` |
| fresh/demo-psycopg2-r2.stderr | `490591f7b1abbd4fa2bdc52e24eae2611f6d1773ab199df100095c13d8786b82` |
| fresh/demo-psycopg2-r3.masked.stderr | `9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6` |
| fresh/demo-psycopg2-r3.out | `0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31` |
| fresh/demo-psycopg2-r3.stderr | `490591f7b1abbd4fa2bdc52e24eae2611f6d1773ab199df100095c13d8786b82` |
| fresh/docker-before.txt | `6dc9ab56558b3d59b773e28aee36978c0ea694ab10cc36bdaa0b5191b503eb41` |
| fresh/environment.json | `b15531000f8a6ea4c8790ae4ad575f06158b52dfee2309e1083c5a1df052be30` |
| fresh/hold-cursor.out | `b3b0e89726e63a678eb99281ecfe6a6e96801048e31ba2c49ebcf39f0bb71ca5` |
| fresh/hold-cursor.sql | `4f026f51aa3c1f14f9c9076362b6d6973137604862a9200adb0b64d83aa49a1d` |
| fresh/psql-checks.out | `beee5e20d31f6ecd1ec8e68ba32fe554effe44a6d6ab548a745184bda8b36c73` |
| fresh/psql-item-rows.txt | `5269e640cb19a2017d60202888443184d95d4c0fe11d21f853c8d05cb0fcfd84` |
| fresh/psql-xact-status.txt | `bd833a747825240849b09f12a6bb76fbab197ceefe092828852ad102c31bdf57` |
| fresh/server.log | `65b8d6dabb8d18b89c6d5b06cf4311750f96cce8c84345dd03b254ce06a57e91` |
| fresh/setup.out | `98c28baacd25336cc01c894f7486a0c9e385968842bc64806e9e71bcbd6930f2` |
| fresh/setup.stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| supplemental/cleanup.txt | `15f909ccdaa02bcb17c1422314dd22611388b450b5a36b47caf8aec6336ba5cf` |
| supplemental/docker-before.txt | `e5ebae9e42d42734f831699b26ae4f365341bfa2d41733aa2082c906947261c8` |
| supplemental/first-write.out | `95cf0381dbbfcd4751787db280b04402d85d391afa111c3981d7d0d1a45dc837` |
| supplemental/first-write.sql | `82752c6addd4c1017fe59032e7bdcf67832215b203bc0856e87eb3a9d27e76fb` |
| supplemental/results.json | `e7b1761dfb92a719d6df97adf6527b2db457e763bb2acedefa7991d9e2cf3ac8` |
| supplemental/server.log | `4554a701ff2eef41c311413738c5d40e74d3cc8b5d05c2d4d30121ad0f110f28` |
| supplemental/setup.out | `98c28baacd25336cc01c894f7486a0c9e385968842bc64806e9e71bcbd6930f2` |
