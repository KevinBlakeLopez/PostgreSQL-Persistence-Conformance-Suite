# CHK-7: the P5a reproduction on SQLAlchemy 2.1.6

Run on 2026-10-24 (US Pacific); the server log is in UTC, 2026-10-25 01:21. Written by: Claude Opus 5.5 (max).

This is check CHK-7 from the PPCS repository's `research/python-upstream-contribution-roadmap.md`, §11. It asks one question: does [`../../check/p5a_close_v2.py`](../../check/p5a_close_v2.py) still reproduce on the latest SQLAlchemy release? That release is 2.1.6, so the script ran on 2.1.6 with psycopg 3.3.6, three times.

The facts for the author are in [`FACTS.md`](FACTS.md). The upstream checks are in [`upstream-checks.md`](upstream-checks.md).

Nothing in [`../../../sqlalchemy-p5a-close-review.md`](../../../sqlalchemy-p5a-close-review.md), [`../../../sqlalchemy-p5a-close-issue-draft.md`](../../../sqlalchemy-p5a-close-issue-draft.md), `check/`, or the rest of `p5a-review/` was changed. Nothing was posted.

## Result

- **Reproduced, 3 of 3.** Each run exited 0. Each run's stdout is byte-identical to the recorded [`../../check/p5a_close_v2.out`](../../check/p5a_close_v2.out) (SHA-256 `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` for all four files).
- **stderr** holds the same two `Exception during reset or similar` entries as the 2026-10-18 run. Only two line numbers differ (see "Comparison").
- **The server log agrees** with the script's own witness, and so does `pg_xact_status()` read through `psql`, for every xid the log identifies (see "Independent verification").

## Files

| File | Contents | SHA-256 |
| --- | --- | --- |
| `output/rep{1,2,3}.stdout` | stdout of the three runs | `fe3058190ed86255a8b4f5bad517701d96c586baebec1fd16584b72b1feadf39` (all three) |
| `output/rep{1,2,3}.stderr` | stderr of the three runs, unedited. Its paths are the local virtualenv and checkout | `03f22dc6f02809491ebd2365cd713066597f8fd105d8ba50d3551f628d55a61d` (all three) |
| `output/rep{1,2,3}.exit` | `exit=0` | `19eaf43821a7660ec323a87c8457bf74823beb296c39f5e01aa8a683aa50f061` (all three) |
| `output/stderr-vs-2026-10-18.diff` | `diff` of `../e0/run.stderr` (left) against `output/rep1.stderr` (right), after replacing each run's virtualenv prefix with `<venv>` and its script path with `<script>` | `3151077b3602d75c5bb29763177ef2033d3a7f4e9872d968403ce2d672b0593c` |
| `output/server.log` | The server's whole log (`docker logs`), from initialisation to the `psql` check. It holds no password: none was ever sent as SQL | `166af9c7dd3789b7b3977718bc89f88749bf2ddeae2a2dc237edb90ac4a23309` |
| `server_log_cases.py` | Summarizes each run's subject sessions from the log, by virtual transaction | `37a86882505c6782a5951b4980993af302a1c3c3842486576cd0e398a8c601c4` |
| `output/server-log-cases.txt` | Its output | `593b0b485eb349363c763bf9fd1fb6211e5870c917d866196e94ea808a7f3a4f` |
| `output/psql-xact-status.txt` | `pg_xact_status()`, read with `psql` inside the container, of the xids on the subject `COMMIT` lines and of three inferred case-3 xids | `fc3a739daa747ea67698bec7ab4d466c5355d00f48eae4e764d60e2841667ec4` |
| `output/versions.txt` | The virtualenv's packages, and how it was made | `209548c43a5dff7e82abe709526fb5003c0d0ee89c27725bcc2ee48f28312f75` |
| `check_install.py` | Checks the installed SQLAlchemy against its wheel's RECORD, and selected modules against the `rel_2_1_6` tag | `2986dbf82f0558cd4b6ba58b87135a88e0d5868e259a10eaa55c138b5af5d645` |
| `output/install-check.txt` | Its output | `bd369764d19484d522d3d1da61f434573389e71c6b499b3183475a20a284c3b1` |
| `sa_search.py` | The read-only GitHub searches (also used for PPCS CHK-3) | `e326fcf97fcfa4c0809b55413935565be5480524ade1118a80ac5933fb18c7ec` |
| `output/github-search.txt` | The P5a part of its results | `59ee0da3ae7e33f4e9b399e89fa2b87479ff6a7e593c0db75d5ee5182f25214f` |

The script itself was not copied. `check/p5a_close_v2.py` had SHA-256 `52bab81dcc588b53e78a83f38e29549b74d8b445ed1c946365b05315c08984b3` before the first run and after the last. It is unchanged since commit `cca9b98`.

## Environment

| Item | Value |
| --- | --- |
| Server | PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) on aarch64, image `postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336` (PPCS's pinned digest). A throwaway container, `chk7-p5a-pg`, on `127.0.0.1:55454`, with a tmpfs data directory, a random password and a random `cluster_name`. Removed after the runs. Not `ppcs-postgres`, and not the 2026-10-18 container `sa-tx-probe` (stopped throughout) |
| Why port 55454 | The script's URL is `postgresql+psycopg://postgres@127.0.0.1:55454/scratch`. Running it unchanged needs that port and database. libpq read the password from a passfile outside the repository (`PGPASSFILE`) |
| Server settings | `max_connections=100`, `log_statement=all`, `log_connections=on`, `log_disconnections=on`, `log_line_prefix='%m [%p] app=%a vxid=%v xid=%x '`. Read back before the runs: `synchronous_commit` on, `default_transaction_isolation` read committed, `statement_timeout` and `idle_in_transaction_session_timeout` 0 |
| Host | macOS arm64, colima (aarch64 VM), `DOCKER_CONTEXT=colima` |
| Python | 3.13.11 (Homebrew) |
| Packages | SQLAlchemy 2.1.6, psycopg 3.3.6, psycopg-binary 3.3.6 (libpq 18.6, reported as `180006`), typing_extensions 4.16.0. Installed with `pip install --only-binary=:all:` into a fresh virtualenv. greenlet is not installed: SQLAlchemy 2.1 does not require it for synchronous use, and the 2026-10-18 virtualenv had greenlet 3.5.6 |
| Installed SQLAlchemy | All 270 files match the wheel's RECORD. The 10 cited modules are byte-identical to tag `rel_2_1_6` (`output/install-check.txt`) |

## Commands

`<venv>`, `<password>` and `<token>` stand for local values. None of them is in any saved file.

```sh
docker run -d --name chk7-p5a-pg -e POSTGRES_PASSWORD=<password> \
  -p 127.0.0.1:55454:5432 --tmpfs /var/lib/postgresql \
  postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336 \
  postgres -c cluster_name=<token> -c max_connections=100 -c log_statement=all \
  -c 'log_line_prefix=%m [%p] app=%a vxid=%v xid=%x ' -c log_connections=on -c log_disconnections=on
docker exec chk7-p5a-pg psql -U postgres -c "create database scratch"
# from the host, through 127.0.0.1:55454/scratch: `show cluster_name` returned <token>

for rep in 1 2 3; do   # each run a separate process
  <venv>/bin/python -I docs/sqlalchemy-transaction-experiments/check/p5a_close_v2.py \
    > output/rep$rep.stdout 2> output/rep$rep.stderr; echo "exit=$?" > output/rep$rep.exit
done
for rep in 1 2 3; do   # no output from diff for any rep; 2 entries each
  diff docs/sqlalchemy-transaction-experiments/check/p5a_close_v2.out output/rep$rep.stdout
  grep -c "Exception during reset or similar" output/rep$rep.stderr
done

docker logs chk7-p5a-pg > output/server.log 2>&1
python -I server_log_cases.py output/server.log > output/server-log-cases.txt
docker exec chk7-p5a-pg psql -U postgres -d scratch -c "select x::text as xid, pg_xact_status(x::text::xid8) \
  as status from unnest('{766,768,770,771,773,775,777,778,780,782,784,785}'::int[]) as x"
docker rm -f chk7-p5a-pg
```

The three runs took place at 2026-10-25 01:21:16 UTC, one after another.

## Comparison with the recorded output

**stdout,** line by line. Each of the 14 lines is the same in the recorded file and in all three runs:

```text
1. commit raised: COMMIT was not sent
1. in_transaction: False | marker: True | marker active: False | psycopg: INTRANS | pg: idle in transaction
1. close returned | pg: idle in transaction
1. pool reset | transaction_was_reset: True | psycopg: INTRANS
1. same dbapi: True | same pid: True | in_transaction: False | psycopg: INTRANS
1. visible: ['doomed', 'next']
2. commit raised: COMMIT was not sent
2. rollback calls before close: 0
2. close returned | rollback calls after close: 0 | pg: idle in transaction
2. same dbapi: True | visible: ['doomed', 'next']
2. rollback calls after later close: 1
3. rollback raised: ROLLBACK was not sent
3. close returned | pg: None
3. same dbapi: False | same pid: False | visible: ['next']
```

**stderr.** The v2 script's stderr was not saved on 2026-10-18. The nearest record is `../e0/run.stderr`, the draft's script on 2.1.5, which has the same two entries. With the path prefixes masked, the two files differ in four lines (`output/stderr-vs-2026-10-18.diff`):

- `pool/base.py`, `_reset`: line 1485 on 2.1.5, line 1492 on 2.1.6, twice. 2.1.6 added seven lines to `_finalize_fairy` (#13699), above `_reset`.
- The script's own frame: line 31 in the draft script, line 38 in `p5a_close_v2.py`, twice. v2 has seven more lines, its `PoolEvents.reset` listener.

## Independent verification

1. **The script's witness.** `visible()` reads through a second engine, on its own connection: `['doomed', 'next']` in case 1, in all three runs.
2. **The server log** (`output/server-log-cases.txt`). In each run, case 1's subject backend sent `BEGIN` and the `doomed` insert. It then sent nothing while `close()` returned it. The next checkout's `next` insert and its `COMMIT` came from the same backend, under the same virtual transaction ID. For example, run 1 is backend 115, vxid `6/3`, xid 766. There is no `ROLLBACK` and no second `BEGIN` between the two inserts. That shared backend and virtual transaction ID, with no transaction end between, is the decisive evidence.
   - In this script the `doomed` line is logged with xid 0, and the `next` line already carries 766. log_statement logs a statement before it runs, and nothing earlier in that transaction assigned an xid.
   - A first insert is not always logged with xid 0: a statement such as `select pg_current_xact_id()` assigns one first.

   Case 2 shows the same pattern (xid 768 in run 1). Case 3's backend sent `BEGIN` and `doomed`, then disconnected with neither `ROLLBACK` nor `COMMIT`. Its `next` came from a new backend.
3. **`psql`** inside the container (`output/psql-xact-status.txt`):
   - the xids logged on the subject `COMMIT` lines are all `committed`: 766, 768, 771, 773, 775, 778, 780, 782 and 785;
   - 770, 777 and 784 are `aborted`. They are candidate xids for case 3's `doomed` transactions, inferred from gaps in the sequence: no log line or captured `backend_xid` identifies them (the witness's `delete from p5a` took 767 and 769 in run 1). Case 3's observed outcome rests on the disconnection without `COMMIT` and on the witness never seeing `doomed`.

## Changes between attempts

- **The script.** It ran exactly three times, unchanged. No run was repeated or discarded.
- **`server_log_cases.py`** was corrected twice before its output was saved:
  - the first version listed each next run's witness under the previous run, because that backend's dialect initialisation precedes its `drop table`;
  - the second listed the `psql` check's session under run 3.

  The saved output comes from the final version. It is identical to the corrected output taken before the `psql` check was run.
- **`check_install.py`** is the inline check that ran, saved unchanged.

## What this establishes, and what it does not

- **Established.** On SQLAlchemy 2.1.6 with psycopg 3.3.6 and PostgreSQL 18.6, `check/p5a_close_v2.py` gives the recorded output, 3 of 3. The second checkout's `COMMIT` commits the transaction whose `commit()` raised, as the server log and `pg_xact_status()` show.
- **Source reading.** The 2.1.6 changes to `Connection.close()` and `_finalize_fairy` (#13699) leave the path P5a takes as it was. Details and lines are in [`upstream-checks.md`](upstream-checks.md).
- **Not run here:**
  - psycopg2, the asyncio engine, `pool_pre_ping`, and the version comparison (`../harness/p2_close.py`) on 2.1.6;
  - the review's harness cases;
  - SQLAlchemy `main` (by source reading it is identical to 2.1.6 for every cited file).
