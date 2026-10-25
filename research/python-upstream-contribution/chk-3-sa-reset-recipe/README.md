# CHK-3: SQLAlchemy's PostgreSQL reset-on-return recipe, on psycopg 3 and psycopg2

Run on 2026-10-24 (US Pacific); the server logs are in UTC, 2026-10-25 01:38–01:46. Written by: Claude Opus 5.5 (max).

This is check CHK-3 from [`../../python-upstream-contribution-roadmap.md`](../../python-upstream-contribution-roadmap.md) §11, for PY-5. It is **not a PPCS case.** It runs outside `harness/`, so no CTL-01 or `pg-control` gate applies. The independent checks are listed under "Independent verification".

The facts for the author are in [`FACTS.md`](FACTS.md). SQLAlchemy's rules forbid AI-written prose in its discussions, issues and PRs, so nothing here is text to post, and nothing was posted.

## Questions

The gap analysis's probe P7 ([`../../python-production-failure-gap-analysis/p7_sa_reset_recipe.py`](../../python-production-failure-gap-analysis/p7_sa_reset_recipe.py), SQLAlchemy 2.1.5) observed that, after the documented recipe on psycopg 3, the role, a custom GUC, `search_path`, `statement_timeout` and a temp table all carried over. That "the hook ran" was inferred from the absence of an invalidation. CHK-3 asks:

- **(a)** What does the documented recipe send on psycopg 3? Does the hook run?
- **(b)** What does the recipe do, verbatim, on psycopg2, the driver in its URL? Hypothesis H-d: `dbapi_connection.execute()` raises, and the pool invalidates the connection on every return.
- **(c)** Does the corrected example in roadmap §7 reset the role, a custom GUC, `search_path`, `statement_timeout` and a temp table, on both drivers?
- **(d)** On an engine created with `isolation_level="AUTOCOMMIT"`, does autocommit survive a return under the corrected example?
- **(e)** Does the corrected example discard the `search_path` set by the docs' "Setting Alternate Search Paths on Connect" recipe? Does a startup `options=-csearch_path=...` survive?

**Added beyond the brief,** each a question a reader of the corrected example would ask. They are labelled "added" wherever they appear.
- Does an engine's `isolation_level="REPEATABLE READ"` survive?
- On psycopg 3, after the driver has prepared a statement server-side, does the next checkout work? The roadmap's §3.2 E.3 answered that from source.
- A negative control for (d): P7's own corrected variant, which sets `autocommit = False` after its reset. It shows that the measurement in (d) detects a lost autocommit.

## Files

| File | What it is |
| --- | --- |
| `chk3_setup.py` | Creates the roles, the database `chk3`, and an `item` table in schemas `public` and `tenant_s`. app_login's password comes from the environment, and is set with `log_statement` off |
| `chk3_reset_recipe.py` | The program. One engine per arm, a pool of one, two units of work, a witness, and listeners that count reset calls (see "The program") |
| `psql_checks.sql` | The PostgreSQL mechanism, checked in `psql` with no Python |
| `server_log_extract.py` | Extracts each run's sessions from the server log and summarizes them by virtual transaction. It refuses to write any line that mentions a password |
| `verbatim_check.py` | Checks that the code under test is copied unchanged from SQLAlchemy's docs, the roadmap, and P7 |
| `demo_reset_recipe.py` | A short standalone program, two hooks only, small enough to paste (see "The demo") |
| `demo_server_log.py` | Summarizes the demo's sessions from its server log |
| `sa_search.py` | The read-only GitHub searches, shared with CHK-7 |
| `output/psycopg.rep{1,2,3}.out`, `output/psycopg2.rep{1,2,3}.out` | The program's complete stdout and stderr, one file per run |
| `output/server-log.<driver>.rep<n>.txt` | Every server-log line of that run's sessions: its arms and its witness |
| `output/server-log-summary.<driver>.rep<n>.txt` | The same sessions, statements grouped by virtual transaction |
| `output/server-log-extract.stdout.txt` | The xids on the `ROLLBACK` lines of reset transactions |
| `output/psql-checks.out` | `psql_checks.sql`, run as app_login |
| `output/psql-xact-status.txt` | `pg_xact_status()` of those reset xids, read with `psql` |
| `output/psql-item-rows.txt` | Every `item` row after the six runs, read with `psql` |
| `output/runs.txt` | Exit codes and UTC start and end times |
| `output/versions.txt`, `output/install-check.txt`, `output/verbatim-check.txt` | Versions, the RECORD and tag check, and the verbatim check |
| `output/github-search.txt` | The recipe searches |
| `output/demo/` | The demo's outputs, its server-log summary, and its `pg_xact_status()` check |
| `supplement/chk3_supplement.py` | The supplement program, run after the outside review (see "The supplement") |
| `supplement/psql_hold_cursor.sql` | The supplement's `psql` check of `CLOSE ALL` and WITH HOLD cursors |
| `supplement/verbatim_check.py` | Checks that the supplement's two hooks are byte-identical to the main program's |
| `supplement/output/` | The supplement's outputs, server-log extracts and summaries, `psql` checks, run times, and the first `psql` attempt (`psql-attempt-1/`) |

**The full server logs are not kept.** They are 2,105 lines (the program's container) and 508 lines (the demo's), and stay outside the repository. No line of either matched `password` or contained any of the passwords, because the one statement that set a password was not logged. Their SHA-256 are `a9d4ce806ceb5e080929e088929892da49c7505f6a448e472c76ecc38e9887df` and `ae21fd8c2ae62d16791e855ea2791130135d041cb27d2f0a6204ee122dffa1ad`. Only the extracts above are kept, as the task asked.

### SHA-256

```text
282ace868468a52f3eee77c3b1758ba0755195248fb1d76120666851b8bdc169  chk3_reset_recipe.py
651a5c280212d52b4790ba50470b0a2f8f67d9bcc95c496872c8fdec6736352b  chk3_setup.py
ffad3e9caaa7a93c76aaf06e9f295cbae38044b2f54de08b4e1380ea54632ed3  demo_reset_recipe.py
096411dd7f4d66fddd092582b4c1f140a979ae971d1ef4f70ce94fa84a2d70e1  demo_server_log.py
c60c9710b2bfb20819a28ff7d0b48b5b08027484ac0aeb622ac6630815e86121  psql_checks.sql
e326fcf97fcfa4c0809b55413935565be5480524ade1118a80ac5933fb18c7ec  sa_search.py
eeb9e10b9ced2ce2fcf688bc6d19007e1db5f85144ab64e414dd64de29cce1be  server_log_extract.py
10290b057de030995d31e2677ae02916cdddb2fc7d9cdcb47eba0b2e668d7ee2  verbatim_check.py
cafbdcaf2bbed55f28a7c5f08e79923921743a70655d7798def8e71656c38c34  output/github-search.txt
82876846f33080723147231900b8c815b954a8f47bb88d357ab874dbd7145edc  output/install-check.txt
6f7a1fa08a4754cebee5733bd83c7109d801e91c93fe6a025c9770859dcf612a  output/psql-checks.out
5269e640cb19a2017d60202888443184d95d4c0fe11d21f853c8d05cb0fcfd84  output/psql-item-rows.txt
ab83f614f827e338ecbb72c4d8de292c2bc2264266f10d4ed07dacc05c3aba5c  output/psql-xact-status.txt
5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac  output/psycopg.rep1.out
5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac  output/psycopg.rep2.out
5fe8b9e4a1e6e31260e777f2ad603e2110802883e8d199cf346a4d0544a4b2ac  output/psycopg.rep3.out
f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e  output/psycopg2.rep1.out
f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e  output/psycopg2.rep2.out
f73be010cfb96e48a7ff600727bca566c80fd7d32cdc6262d964ed35de699c7e  output/psycopg2.rep3.out
9eb1833dc47311cabfcf15b51f9f27542feb97129a2c68edc0a789463181f39e  output/runs.txt
4cb9f407c55b2c2587a45ec6eb6e979752f7e55b676043a39e95d768092b70f6  output/server-log-extract.stdout.txt
fd30a875fdd7c59cc250003ed8132259dfda4edc7eb683cf51ba9dabddb49a58  output/server-log-summary.psycopg.rep1.txt
e91fc26a49b73330f3ecdb0b2e3ed95a9dc6f28c0fb27cccf00e39865d16c1c6  output/server-log-summary.psycopg.rep2.txt
61b87c7b0f3d91986e621b14fc250a326a0a241ad9385e04cb371d2d5499caec  output/server-log-summary.psycopg.rep3.txt
c61eaecf1777b255aee785eb0f4e8ea6d5dbf87d54df4b0005a4b7ac551fba80  output/server-log-summary.psycopg2.rep1.txt
2cfbc45a403a5ae06ec94137c0b292737e6e1762c67977e3d64eb4c9ce0d1a87  output/server-log-summary.psycopg2.rep2.txt
9b702a081b54442c73a6cb2358ea59f515f009422771d456586c53e62e381d66  output/server-log-summary.psycopg2.rep3.txt
e36d4453b1a61df4a063b13f5485e78d99f674062a35a8d30136fccd8cf3358f  output/server-log.psycopg.rep1.txt
fca1e06bf05373e9f490b78e3c9da3319ce75dcc4840fdf5ee85ffd6197440cf  output/server-log.psycopg.rep2.txt
f000092df3f75a81a991885828ae6d6c2ed2c586140ca44d456e52feadcc44f8  output/server-log.psycopg.rep3.txt
5e62bb99f0b50f2e6dc30b02216a0e2fe64b30179746179c74bc3f4a63b9ab4b  output/server-log.psycopg2.rep1.txt
20988a784d6c79db3ff4a3b6d5170dd1f0c8715406e6448aeaddd7789c504616  output/server-log.psycopg2.rep2.txt
a144d9c5b299547689fbd231d3b3bc5a93b2fcccc6f6ccdf32524967e0892b49  output/server-log.psycopg2.rep3.txt
93f07caae904d7f8ae95c3f3c9a9464c791f7fd6249b3bec032a5207778007f6  output/verbatim-check.txt
59f118ce79c97ca302a2e54a31711040248a216d6fe935f69e9d0bbb05224499  output/versions.txt
6f34299e9236c811975f37dc02630c1cb9b90243511173c8c76f19d354dd33ee  output/demo/psql-xact-status.txt
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  output/demo/psycopg.rep1.stderr
a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2  output/demo/psycopg.rep1.stdout
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  output/demo/psycopg.rep2.stderr
a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2  output/demo/psycopg.rep2.stdout
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  output/demo/psycopg.rep3.stderr
a6154af48f1c63ad77c0b5bc029acc988d11b115b17855f7f9cb8306ee2d80e2  output/demo/psycopg.rep3.stdout
9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6  output/demo/psycopg2.rep1.stderr
0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31  output/demo/psycopg2.rep1.stdout
9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6  output/demo/psycopg2.rep2.stderr
0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31  output/demo/psycopg2.rep2.stdout
9175fecc05a702f2c912d0f49780aee86bcfa75b1879414d4e2fe03ff2a865c6  output/demo/psycopg2.rep3.stderr
0d35ff443f8284bd79e2114b3550d208c72c49456b7d6788986bff0327e0aa31  output/demo/psycopg2.rep3.stdout
5ce848ea933640d4900a83113c04cdbe8fd2c0f153354d56cf5696d2e6fc46a1  output/demo/runs.txt
dfc1b0fd9510581c3c5bfb671dcffbbbc899c60f1b16601c3a467905657c2617  output/demo/server-log-summary.txt
0196aedda01f788a6e18e057384d5e4aa94a0f8284b36303b750eaf64bacdaec  supplement/chk3_supplement.py
6daf45b912bad0edacb078b547678376dc26251408c48c01093718d9b8357c64  supplement/psql_hold_cursor.sql
36ecd1d1511099009eb526da30ce8f224ee16b497fe7133ab05f5a104a3448c2  supplement/verbatim_check.py
2e2b844469ae3714199e3c886bb4d2facf89b7635f0f0cfbe990c378f970fb3d  supplement/output/psql-attempt-1/psql-hold-cursor.rep1.out
5d6e49be232720ff1506f20c9b546d7c176027764195d6463f906d77a7790ebf  supplement/output/psql-attempt-1/psql-hold-cursor.rep2.out
5d6e49be232720ff1506f20c9b546d7c176027764195d6463f906d77a7790ebf  supplement/output/psql-attempt-1/psql-hold-cursor.rep3.out
66e794ea0f052082a125b2a8075c5cf8fd330d358c2ecd6084eb5f0e6ef9c471  supplement/output/psql-hold-cursor.rep1.out
66e794ea0f052082a125b2a8075c5cf8fd330d358c2ecd6084eb5f0e6ef9c471  supplement/output/psql-hold-cursor.rep2.out
66e794ea0f052082a125b2a8075c5cf8fd330d358c2ecd6084eb5f0e6ef9c471  supplement/output/psql-hold-cursor.rep3.out
bcb7aff9c6b0c7a922b04e870e4e49f68367ea592fa58a0709f873d6e9d0a115  supplement/output/psql-item-rows.txt
c4e647ebe5516fe94b128370873757dd633f277865dd4da44130abc797fb6e31  supplement/output/psql-xact-status.txt
d3366591164c6dc08614be87234ba17119fc11ba38653df793f4c862907ebd6c  supplement/output/psycopg.rep1.out
d3366591164c6dc08614be87234ba17119fc11ba38653df793f4c862907ebd6c  supplement/output/psycopg.rep2.out
d3366591164c6dc08614be87234ba17119fc11ba38653df793f4c862907ebd6c  supplement/output/psycopg.rep3.out
032a2955e9c56ba1e5e446f0163e5d34081387de67fc22b53e4f2e07b3dd1ccf  supplement/output/psycopg2.rep1.out
032a2955e9c56ba1e5e446f0163e5d34081387de67fc22b53e4f2e07b3dd1ccf  supplement/output/psycopg2.rep2.out
032a2955e9c56ba1e5e446f0163e5d34081387de67fc22b53e4f2e07b3dd1ccf  supplement/output/psycopg2.rep3.out
76d1da9b9b728f2dbc58f0fd93c50de2becd0ccb263372f8358901eda6c8a2b5  supplement/output/runs.txt
e7dfe2f4826bca8ba73f16ea21adf5ad9b6598ea28c74d95b5baaee3f9395e83  supplement/output/server-log-summary.psycopg.rep1.txt
f906a1674e53eaa1b83e3979c6bed8849ba36d9e6a88f214372d030c35e09f4c  supplement/output/server-log-summary.psycopg.rep2.txt
7d3d0ff411b82c6e21a9b493e48e30c7d62159f677de859e35ca9f161fe6154a  supplement/output/server-log-summary.psycopg.rep3.txt
361656e5eec5b5a273a7863016643ce337a92e4e677268c6283e6d58979d8350  supplement/output/server-log-summary.psycopg2.rep1.txt
e036431b66c70272899d71c59f777b2c447a416968c0a3db1c10e2a9e1479b20  supplement/output/server-log-summary.psycopg2.rep2.txt
6ae13dbe0ba0767231f08ff990ac7dc16fb1c9aed5323f563817731711d6038a  supplement/output/server-log-summary.psycopg2.rep3.txt
10991a4e0a6184553eafcab58f7c177cad8d96d03b894aa6761590850dd7d208  supplement/output/server-log.psycopg.rep1.txt
a36ae47750e74bfe7c097b90f5278f3934456fbb24767238e9a6512ab594fc21  supplement/output/server-log.psycopg.rep2.txt
836996baa19951f272a5bf025d6d331c6bc497de0dcf9de52a35f74f5f03b432  supplement/output/server-log.psycopg.rep3.txt
25bfa7868c17c128c8f869001862134f37c189fe52453c1c061cf425a4cd4bce  supplement/output/server-log.psycopg2.rep1.txt
5d0b105b3fe766737160591dcabdc36c7a1575f121f206ef64a2bda4e2dca142  supplement/output/server-log.psycopg2.rep2.txt
21f3ce2d2db29ed4064441fb25218abe378ff0ea58dc0491f4ac11953560759a  supplement/output/server-log.psycopg2.rep3.txt
6b70d9c7efa957338b3e23c88f7fbd38c5ed5de388d98fcec522342f8ba6fc2f  supplement/output/verbatim-check.txt
```

Repetitions of the program and of the demo print byte-identical output, per driver. That is by design: the program prints no PIDs, timestamps or rep numbers. The server-log files differ between runs, in PIDs, vxids, xids and timestamps.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest). Two throwaway containers, one after the other, both on `127.0.0.1:55492`, each with a tmpfs data directory, a random password and a random `cluster_name`: `ppcs-chk3-sa-reset-pg` for the program and the psql checks, `ppcs-chk3-demo-pg` for the demo. Both removed. Not `ppcs-postgres` |
| Server settings | `max_connections=100`, `log_statement=all`, `log_connections=on`, `log_disconnections=on`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '`. The program's container also had `log_lock_waits=on` and `deadlock_timeout=1s`. Read back before the runs: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout` and `idle_in_transaction_session_timeout` 0, `search_path` `"$user", public` |
| Login | `app_login`: `rolsuper` false, a member of the NOLOGIN role `tenant_a`. Checked through the program's own URL before the runs: `current_user` app_login, not a superuser, and `cluster_name` equal to the container's token |
| Host | macOS arm64, colima (aarch64 VM), `DOCKER_CONTEXT=colima` |
| Python | 3.13.11 (Homebrew) |
| psycopg 3 virtualenv | SQLAlchemy 2.1.6, psycopg 3.3.6, psycopg-binary 3.3.6 (libpq 18.6, reported as `180006`), typing_extensions 4.16.0. psycopg2 is not importable |
| psycopg2 virtualenv | SQLAlchemy 2.1.6, psycopg2-binary 2.9.13 (`2.9.13 (dt dec pq3 ext lo64)`, libpq 17.11, reported as `170011`), typing_extensions 4.16.0. psycopg 3 is not importable |
| Install | Both virtualenvs were fresh, created with `pip install --only-binary=:all:`. In each, all 270 SQLAlchemy files match the wheel's RECORD, and the cited modules are byte-identical to tag `rel_2_1_6` (`output/install-check.txt`). These were the latest releases on PyPI that day |

## Commands

`<venv-…>`, `<password>`, `<app-password>` and `<token>` stand for local values. None of them is in any saved file. libpq read the passwords from a passfile outside the repository (`PGPASSFILE`).

```sh
docker run -d --name ppcs-chk3-sa-reset-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55492:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_lock_waits=on -c deadlock_timeout=1s \
  -c log_statement=all -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x ' \
  -c log_connections=on -c log_disconnections=on

CHK3_APP_PASSWORD=<app-password> <venv-chk3-psycopg>/bin/python -I chk3_setup.py
# then, through 127.0.0.1:55492/chk3 as postgres and as app_login: `show cluster_name` returned <token>

python -I verbatim_check.py <venv-chk3-psycopg>/lib/python3.13/site-packages/sqlalchemy/dialects/postgresql/base.py \
  ../../python-upstream-contribution-roadmap.md ../../python-production-failure-gap-analysis/p7_sa_reset_recipe.py

# six runs, each a separate process, one after another:
for drv in psycopg psycopg2; do for rep in 1 2 3; do
  <venv-chk3-$drv>/bin/python -I chk3_reset_recipe.py $drv $rep > output/$drv.rep$rep.out 2>&1
done; done

docker exec -i ppcs-chk3-sa-reset-pg psql -U app_login -d chk3 -X -e < psql_checks.sql > output/psql-checks.out 2>&1
docker logs ppcs-chk3-sa-reset-pg > <scratch>/server.full.log 2>&1
python -I server_log_extract.py <scratch>/server.full.log output > output/server-log-extract.stdout.txt
docker exec ppcs-chk3-sa-reset-pg psql -U postgres -d chk3 -X -c "select x::text as xid, \
  pg_xact_status(x::text::xid8) as status from unnest('{778,780,807,809,836,838}'::int[]) as x"
docker exec ppcs-chk3-sa-reset-pg psql -U postgres -d chk3 -X -c "select s, inserted_by, name from \
  (select 'public' s, inserted_by::text, name from public.item union all \
   select 'tenant_s', inserted_by::text, name from tenant_s.item) x order by name"
docker rm -f ppcs-chk3-sa-reset-pg
```

The program's SHA-256 was the same before the first run and after the last. Psycopg 3 rep 1 ran first, at 01:39:26 UTC, and its output was read before the other five runs (01:40:01–01:40:04 UTC). The program was not changed in between.

The demo used a second container, made with the same command (without `log_lock_waits` and `deadlock_timeout`) and the same setup. It then ran `demo_reset_recipe.py` three times per driver, at 01:45:18–01:45:19 UTC, followed by `python -I demo_server_log.py` on that container's log and a `pg_xact_status()` check of its reset xids.

## The program

Each arm builds its own engine, with `pool_size=1, max_overflow=0` and `application_name=chk3-<driver>-<arm>-r<rep>`.

- **Unit 1** (`with engine.begin()`) runs these statements, then commits: `SET ROLE tenant_a`, `SET app.tenant_id = 'a'`, `SET search_path = tenant_s, public`, `SET statement_timeout = '54321'`, `CREATE TEMP TABLE <unique name> (x int)`. The (e) arms leave out `SET search_path`.
- **Unit 2** reads `current_user`, the GUC, `search_path`, `statement_timeout`, the temp table, `transaction_isolation` and `pg_prepared_statements` on the server. It then inserts an unqualified row into `item`, and commits.

| Arm | Engine | Reset hook | Drivers |
| --- | --- | --- | --- |
| `default` (control) | defaults (`pool_reset_on_return="rollback"`) | none | both |
| `documented` — (a), (b) | `pool_reset_on_return=None` | the docs recipe, `dialects/postgresql/base.py:317-326`, verbatim | both |
| `corrected` — (c) | `pool_reset_on_return=None` | the roadmap §7 example, verbatim | both |
| `corrected-autocommit` — (d) | `+ isolation_level="AUTOCOMMIT"` | §7 example | both |
| `corrected-connect-search-path` — (e) | `pool_reset_on_return=None`, plus the docs' connect handler (`base.py:359-366`, verbatim, `schema_name = "tenant_s"`) | §7 example | both |
| `corrected-options-search-path` — (e) | `+ connect_args options="-csearch_path=tenant_s"` | §7 example | both |
| `corrected-repeatable-read` (added) | `+ isolation_level="REPEATABLE READ"` | §7 example | both |
| `corrected-prepared` (added) | `pool_reset_on_return=None`; each unit runs `select 1 as one` 8 times (psycopg's `prepare_threshold` is 5) | §7 example | psycopg 3 |
| `p7-variant-autocommit` (control for (d)) | `+ isolation_level="AUTOCOMMIT"` | P7's `corrected_reset`, verbatim, which ends with `autocommit = False` | psycopg 3 (it calls `dbapi_connection.execute`) |

`verbatim_check.py` confirms that every hook is a verbatim copy (`output/verbatim-check.txt`).

**What else is recorded:**
- **Two listeners bracket the arm's hook.** `before` records every reset call: `terminate_only`, `transaction_was_reset`, and the driver's transaction status and autocommit. `after` runs only if every listener before it returned, and records the status and autocommit afterwards.
- **Pool events** `connect`, `checkout`, `checkin` and `invalidate`.
- **The pool's error log**, with the virtualenv path shown as `<venv>`.
- **A witness.** It is a raw autocommit connection as `postgres`, through the same driver, not SQLAlchemy. It reads:
  - where unit 2's row landed, and its `inserted_by` (`DEFAULT current_user`);
  - whether the row was visible before unit 2 ended;
  - whether unit 1's backend still exists. When unit 2 is on another backend, it waits up to 5 s for that backend to leave `pg_stat_activity`;
  - whether unit 1's temp table still exists in `pg_class`.

## Results

**All six runs exited 0** (`output/runs.txt`). The three repetitions agree byte for byte, per driver. Each arm made two reset calls: one when unit 1 returned its connection, one when unit 2 did.

### psycopg 3.3.6

| Arm | Hook calls that returned | Same backend for unit 2 | Unit 2 saw: current_user, app.tenant_id, search_path, statement_timeout, temp table | Witness: unit 2's row; temp table in `pg_class` | Autocommit, unit 1 → 2; row visible before unit 2 ended |
| --- | --- | --- | --- | --- | --- |
| `default` | 2 of 2 (no hook) | yes | tenant_a, `a`, `tenant_s, public`, 54321ms, yes | `tenant_s.item` by tenant_a; 1 | False → False; no |
| `documented` | 2 of 2 | yes | tenant_a, `a`, `tenant_s, public`, 54321ms, yes | `tenant_s.item` by tenant_a; 1 | False → False; no |
| `corrected` | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no | `public.item` by app_login; 0 | False → False; no |
| `corrected-autocommit` | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no | `public.item` by app_login; 0 | True → True; **yes** |
| `corrected-connect-search-path` | 2 of 2 | yes | app_login, `''`, **`"$user", public`** (unit 1 began with `tenant_s`), 0, no | `public.item` by app_login; 0 | False → False; no |
| `corrected-options-search-path` | 2 of 2 | yes | app_login, `''`, **`tenant_s`** (unit 1 began with `tenant_s`), 0, no | `tenant_s.item` by app_login; 0 | False → False; no |
| `corrected-repeatable-read` (added) | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no; `transaction_isolation` **repeatable read** | `public.item` by app_login; 0 | False → False; no |
| `corrected-prepared` (added) | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no. Prepared statements on the server: 1 at the end of unit 1, **0** at the start of unit 2, 1 after its 8 runs, no error | `public.item` by app_login; 0 | False → False; no |
| `p7-variant-autocommit` (control) | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no | `public.item` by app_login; 0 | True → **False**; no |

### psycopg2 2.9.13

| Arm | Hook calls that returned | Same backend for unit 2 | Unit 2 saw: current_user, app.tenant_id, search_path, statement_timeout, temp table | Witness: unit 2's row; temp table in `pg_class` | Autocommit, unit 1 → 2; row visible before unit 2 ended |
| --- | --- | --- | --- | --- | --- |
| `default` | 2 of 2 (no hook) | yes | tenant_a, `a`, `tenant_s, public`, 54321ms, yes | `tenant_s.item` by tenant_a; 1 | False → False; no |
| `documented` | **0 of 2.** Both calls raised `AttributeError: 'psycopg2.extensions.connection' object has no attribute 'execute'`. The pool logged "Exception during reset or similar" and invalidated the connection, both times | **no.** A new connection; unit 1's backend exited | app_login, unset (`NULL`), `"$user", public`, 0, no | `public.item` by app_login; 0 | False → False; no |
| `corrected` | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no | `public.item` by app_login; 0 | False → False; no |
| `corrected-autocommit` | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no | `public.item` by app_login; 0 | True → True; **yes** |
| `corrected-connect-search-path` | 2 of 2 | yes | app_login, `''`, **`"$user", public`** (unit 1 began with `tenant_s`), 0, no | `public.item` by app_login; 0 | False → False; no |
| `corrected-options-search-path` | 2 of 2 | yes | app_login, `''`, **`tenant_s`** (unit 1 began with `tenant_s`), 0, no | `tenant_s.item` by app_login; 0 | False → False; no |
| `corrected-repeatable-read` (added) | 2 of 2 | yes | app_login, `''`, `"$user", public`, 0, no; `transaction_isolation` **repeatable read** | `public.item` by app_login; 0 | False → False; no |

**About `app.tenant_id`.** After `RESET ALL` or `DISCARD ALL`, a placeholder GUC that the session had set reads as `''`. On a new session that never set it, it reads as `NULL`, shown as `<unset>` in the output.

### What each hook's session sent (server log)

These are from `output/server-log-summary.<driver>.rep<n>.txt`, and are the same in all three runs.

- **`documented`, psycopg 3: (a).** On each return the session sent `BEGIN | CLOSE ALL | RESET ALL | DISCARD TEMP | ROLLBACK`, all under one virtual transaction ID (run 1: vxid `9/4`, then `9/6`). `DISCARD TEMP` was given an xid, logged on the `ROLLBACK` line (778 and 780 in run 1). `psql` reads all six such xids as `aborted` (`output/psql-xact-status.txt`).
- **`documented`, psycopg2: (b).** On return the session sent nothing, then disconnected. Unit 2's session was a new backend that also sent nothing on return, then disconnected. That is two `invalidate (AttributeError)` events per run, and two "Exception during reset or similar" entries. The captured traceback ends in the recipe's first line, `dbapi_connection.execute("CLOSE ALL")`, called from `pool/base.py` `_reset` (1466) → `event/attr.py` (514).
- **`default`, both drivers.** Nothing on return. Unit 1 had committed, so the connection was idle, and the default reset's `rollback()` sent no `ROLLBACK`.
- **The §7 example, both drivers.** On each return, one `DISCARD ALL` under its own vxid, outside any transaction block. The hook's leading `rollback()` sent nothing, because the connection was idle.
- **`corrected-autocommit`.** Every statement of both units had its own vxid, with no `BEGIN`. Autocommit held on both drivers.
- **`corrected-connect-search-path`.** `SET SESSION search_path='tenant_s'` was sent once, at connect, outside a transaction. After the first return's `DISCARD ALL`, no `SET` was sent again.
- **`corrected-repeatable-read` (added).** Both drivers start each transaction with `BEGIN ISOLATION LEVEL REPEATABLE READ`. On psycopg2, each `DISCARD ALL` is followed by `SET default_transaction_isolation TO DEFAULT`, sent when the hook restores `autocommit = False`. Src: psycopg2 2.9.13 `psycopg/connection_int.c:1321-1330` reverts that GUC when leaving autocommit with a non-default isolation level. It is an extra round trip, and the next transaction is still REPEATABLE READ.
- **`corrected-prepared` (added).**
  - Unit 1 ran `select 1 as one` five times plainly, then three times as `execute _pg3_0`.
  - On return the hook's `DISCARD ALL` was followed by `DEALLOCATE ALL`, from psycopg.
  - Unit 2 ran the query five times plainly, then three times as `execute _pg3_1`, with no error.
  - Src: psycopg 3.3.6 `_preparing.py:82-100` clears its prepared-statement state when a command status matches `DROP`, `ALTER`, `ROLLBACK`, `DISCARD ALL` or `DEALLOCATE ALL`. `clear()` (176–189) schedules the server-side flush.
- **`p7-variant-autocommit`.** Unit 1 ran in autocommit. Unit 2 ran as `BEGIN … COMMIT`, so autocommit was lost after the first return.

### psql checks (`output/psql-checks.out`)

These ran as app_login, with no SQLAlchemy or Python.

1. **Inside a block that rolls back.** After `SET ROLE tenant_a`, the GUC, `search_path`, `statement_timeout` and a temp table, the block `begin; close all; reset all; discard temp; rollback;` left everything in place.
2. **Outside a transaction block,** the same three statements reset the GUC, `search_path` and `statement_timeout`, and dropped the temp table. `current_user` stayed `tenant_a`.
3. **`DISCARD ALL` inside a block** fails: `ERROR:  DISCARD ALL cannot run inside a transaction block`.
4. **`DISCARD ALL` outside a block** returned `current_user` to app_login and dropped a temp table.
5. **`RESET ROLE`** returned `current_user` to app_login.

## Independent verification

Three sources agree for every arm.

1. **The witness connection** in each run, as above.
2. **The server log.** It shows what each session sent, and when each backend disconnected.
3. **`psql`, after the six runs, independent of Python.**
   - All six documented-recipe reset transactions on psycopg 3 are `aborted`.
   - All 48 `item` rows are where the witness reported them (`output/psql-item-rows.txt`). Only the `default` rows on both drivers, and the `documented` rows on psycopg 3, are in `tenant_s.item` by tenant_a. The `corrected-options-search-path` rows are in `tenant_s.item` by app_login. Every other row is in `public.item` by app_login.

## The demo (`demo_reset_recipe.py`)

A 64-line program for pasting.
- **Its hooks.** `documented_recipe` is the docs recipe verbatim. `rollback_then_discard_all` is the §7 example without its two comments; `verbatim_check.py` confirms the same AST.
- **What it does.** Each hook gets a new engine with a pool of one. Unit 1 sets the state, and the next checkout prints what it sees.
- **Runs.** Three per driver, one container (`output/demo/`). Each driver's stdouts are byte-identical. On psycopg2 its stderr is SQLAlchemy's two "Exception during reset or similar" tracebacks. In the saved copies, the virtualenv path is replaced with `<venv>` and this directory with `<here>`; the raw files' SHA-256 are in `output/demo/runs.txt`.
- **Its server log** (`output/demo/server-log-summary.txt`) matches the program's.
  - Session 1 is the pre-run token check.
  - On psycopg 3, the documented hook sent `BEGIN | CLOSE ALL | RESET ALL | DISCARD TEMP | ROLLBACK`, and its six reset xids are `aborted` (`output/demo/psql-xact-status.txt`).
  - On psycopg2, it sent nothing, and each returned backend disconnected.
  - The second hook sent `DISCARD ALL` alone.

Its output, identical in all three runs per driver:

```text
psycopg | documented_recipe
  next checkout: same backend: True | current_user: tenant_a | app.tenant_id: 'a' | search_path: tenant_s, public | statement_timeout: 54321ms | temp table: True
psycopg | rollback_then_discard_all
  next checkout: same backend: True | current_user: app_login | app.tenant_id: '' | search_path: "$user", public | statement_timeout: 0 | temp table: False
```

```text
psycopg2 | documented_recipe
  next checkout: same backend: False | current_user: app_login | app.tenant_id: None | search_path: "$user", public | statement_timeout: 0 | temp table: False
psycopg2 | rollback_then_discard_all
  next checkout: same backend: True | current_user: app_login | app.tenant_id: '' | search_path: "$user", public | statement_timeout: 0 | temp table: False
```

## Upstream (read-only)

Detail and dates are in [`FACTS.md`](FACTS.md); the search record is `output/github-search.txt`.

- **The recipe's text is unchanged.** It is in `lib/sqlalchemy/dialects/postgresql/base.py`, lines 275–336. The file is byte-identical on `rel_2_1_5`, `rel_2_1_6` and `main` `10f4d1e2d` (SHA-256 `cc06667e263a6424e149355a95493987ab1220097568be9603b6b99a60228575`). So is `doc/build/core/pooling.rst`, which holds the parallel SQL Server example.
- **The recorded queries found no report of this recipe's failure** on either driver. This is a search result, not proof that no report exists. The search covered 12 queries over issues, pull requests and discussions, for all time. It included `reset_on_return`, `DISCARD`, `"RESET ALL"`, `reset event psycopg`, `"DISCARD ALL"`, `"DISCARD TEMP"` and `_reset_postgresql`.

## The supplement, after the outside review

An outside review found that "the recipe resets nothing" was broader than the evidence. With the maintainer's approval, `supplement/` adds these arms. They ran on a third container, `ppcs-chk3-supplement-pg`, made with the same command, port, settings and setup as the first; it has been removed. Every arm ran 3 times, at 03:21 UTC.

| Arm | Driver | Result |
| --- | --- | --- |
| `psql_hold_cursor.sql`: a WITH HOLD cursor, then `begin; close all; reset all; discard temp; rollback;` | `psql` | The cursor is gone. Controls: it survives `begin; rollback;`, and `CLOSE ALL` alone in a rolled-back block also closes it |
| `documented-autocommit`: the documented recipe on an AUTOCOMMIT engine | psycopg 3 | Its three statements run outside a transaction block, with no `ROLLBACK`. The GUC, `search_path`, `statement_timeout` and temp table are reset; the role is still tenant_a (row in `public.item` by tenant_a) |
| `corrected-default-reset`: the corrected example with the default `pool_reset_on_return` | both | All five reset. Only `DISCARD ALL` is sent on return; the pool's rollback sends nothing on an idle connection |
| `default-open-transaction` (control): no hook; unit 1 returns its connection with an uncommitted insert open | both | `close()` sends `ROLLBACK`, and the reset call gets `transaction_was_reset=True`. All five items carry over |
| `corrected-open-transaction`, and the same with the default reset | both | The same `ROLLBACK` and `transaction_was_reset=True`, then `DISCARD ALL`. All five reset, on the same DBAPI connection |

**Checks.**
- In the open-transaction arms, the witness never saw the uncommitted row. `psql` reads all 18 of those transactions as `aborted` (`supplement/output/psql-xact-status.txt`).
- All 27 committed rows are where the witness reported them (`supplement/output/psql-item-rows.txt`).
- The program's outputs are byte-identical across repetitions, per driver.
- `server_log_extract.py` ran unchanged on that container's log. The extracts were the same before and after the `psql` checks.
- The full log (1,424 lines, SHA-256 `04562902562d8999ce43f1eb5411303c4538bf093096f5bd626b86155960315a`) has no password or token in it, and is not kept.

## Changes between attempts

- **`chk3_reset_recipe.py`.** One version ran, unchanged, for all six runs (the same SHA-256 before and after). Two changes were made before any run:
  - an immediate `pg_class` check after unit 1's return was removed, because a discarded backend exits asynchronously;
  - the witness instead waits for a different unit-1 backend to leave `pg_stat_activity`.
- **`verbatim_check.py`.**
  - Its first run compared 15 roadmap lines, including the closing code fence, and reported a difference. It was fixed to compare 14 lines.
  - It later gained the two demo checks.

  The saved output comes from the final version.
- **`server_log_extract.py`.** Run twice, on the log before and after the `psql` checks; the extracts are identical.
- **The demo** ran once per driver per rep, unchanged.
- **The first container** served the program and the psql checks; the second served only the demo.
- **The supplement.** `chk3_supplement.py` ran unchanged for all six runs, with the same SHA-256 before and after. `psql_hold_cursor.sql` ran twice, three times each:
  - **The first attempt** had an apostrophe in its first `\echo` label ("the recipe's three statements"). psql reported "unterminated quoted string" and printed the label cut short. The statements and their results were the same as in the second attempt.
  - Because that error line landed at a different place in run 1's output, the first attempt's three outputs did not all hash alike. They are kept in `supplement/output/psql-attempt-1/`.
  - **The second attempt** used the current file, whose label reads "the three recipe statements". Its outputs are byte-identical.

## What this establishes, and what it does not

- **Established**, on SQLAlchemy 2.1.6, PostgreSQL 18.6, and a non-superuser login, with a pool of one:
  - On psycopg 3.3.6, on a transactional (default) engine, the documented recipe's hook runs on every return. Its statements run inside a transaction that its own `rollback()` aborts, so the role, the GUC, `search_path`, `statement_timeout` and the temp table all carry over.
    - Its `CLOSE ALL` is the exception: WITH HOLD cursors are closed even though the block rolls back.
    - On an AUTOCOMMIT engine the same hook resets everything measured except the role (supplement).
  - On psycopg2 2.9.13, with the recipe's own `postgresql+psycopg2://` URL, the hook raised `AttributeError` on each tested return. The pool then discarded the connection. None of the measured state carried over, because no connection was reused.
  - **The §7 example** resets all five items on both drivers, and keeps the connection. That holds:
    - under the default `pool_reset_on_return`;
    - when a connection is returned with its transaction open.

    It keeps autocommit on an AUTOCOMMIT engine. Added: it keeps REPEATABLE READ, and, on psycopg 3, prepared statements keep working.
  - It discards a `search_path` set by the docs' connect-time recipe. A `search_path` from startup `options` survives.
- **Source reading.** `PoolEvents.reset` is dispatched before the pool's own reset-on-return (`pool/base.py:1465-1474`, then 1479–1499, on 2.1.6). An exception from it is logged and the record invalidated (1041–1044, 1059–1060).
- **Not run:**
  - other PostgreSQL versions;
  - asyncpg, pg8000, and psycopg's async connection;
  - pgbouncer;
  - Linux clients (the server ran in a Linux container);
  - SQLAlchemy 2.1.5 (P7 ran the documented recipe and P7's variant on it);
  - `terminate_only=True`;
  - `LISTEN` and advisory locks under the documented recipe, which sends neither `UNLISTEN` nor an advisory unlock;
  - pools larger than one.
