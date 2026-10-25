Written by: GPT-6 / Codex (effort setting not exposed)
Date: 2026-10-24 (America/Los_Angeles)

# Verdicts

| Text | Verdict | Basis |
| --- | --- | --- |
| PY-1b, follow-up to psycopg #1453 | **READY WITH CHANGES** — INFERRED judgment | The recorded status/outcome mismatch is supported. The assertion about missing tests is wrong, and the savepoint description needs correction. |
| PY-2, new asyncpg issue | **READY WITH CHANGES** — INFERRED judgment | The standalone evidence is strong. Existing timeout tests contradict the claimed coverage gap and materially strengthen the compatibility objection. Correct that before filing. |

**VERIFIED — scope.** Only the content between each draft's final two standalone `---` lines was treated as publishable, plus PY-2's proposed title. The checkout is `main` at `905e797e610335c4dd3fd513dfb34181231f9a43`; neither draft differs from that commit. There were already six modified tracked files and unrelated untracked files. This review does not edit them, the drafts, or existing evidence. No upstream mutation or harness execution was performed.

**Reading convention.** VERIFIED means checked against the cited artifact or source, not a fresh reproduction of its historical execution. INFERRED labels interpretation, risk, objections, and recommendations. NOT CHECKED labels an omitted check. Ledger statuses WRONG, MISLEADING, OVERSTATED, and UNVERIFIED describe the draft claim; each explanation identifies whether the review's basis is verified, inferred, or unavailable. A label applies to its paragraph or table row. Proposed replacement text is a recommendation, not an assertion that it has been posted or executed.

# Findings, in severity order

## 1. High: both claims about absent tests are contradicted by upstream tests

**VERIFIED — PY-1b quotation:** “I found no test of `transaction()` that catches a database error inside the block” (draft line 83).

**VERIFIED — counterexample.** At the cited default-branch commit, [`tests/test_pipeline.py:506–511`](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/tests/test_pipeline.py#L506-L511), `test_outer_transaction_error` enters `conn.transaction()`, then uses `pytest.raises((e.UndefinedColumn, e.OperationalError))` around a pipeline containing `select error`. The error is caught *inside* the transaction block. The async copy is [`tests/test_pipeline_async.py:507–512`](https://github.com/psycopg/psycopg/blob/99356800e90aa0e7b604f652d714ef0f33422b47/tests/test_pipeline_async.py#L507-L512). These are positive counterexamples to the literal claim even though this experiment excluded pipeline mode. The nested-savepoint pipeline tests also catch a database exception inside an outer transaction (`test_pipeline.py:260–273`, async `:257–270`).

**INFERRED — maintainer reading.** “The author searched for Python `except` statements and missed our exception-catching test helpers. Why trust the coverage and compatibility analysis?” The false negative does not disprove the non-pipeline `tx.status` observation. Whether these pipeline tests would fail under any particular proposed fix is NOT CHECKED.

**INFERRED — smallest PY-1b replacement, for that sentence:**

> The pipeline tests `test_outer_transaction_error` and its async copy already catch a database error inside `transaction()` and expect normal exit. I have not run pipeline mode here. The non-pipeline example above additionally checks `tx.status` against PostgreSQL's outcome.

**VERIFIED — PY-2 quotation:** “Today that code gets a silent rollback. I found no test in `tests/` that does this.” (line 317). Its internal notes say “No asyncpg test commits after a caught database error” (line 60).

**VERIFIED — counterexample.** [`tests/test_timeout.py:104–113`](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/tests/test_timeout.py#L104-L113), inside `test_timeout_06`, catches a timeout, then catches `asyncpg.InFailedSQLTransactionError` with `self.assertRaises` *inside* `async with self.con.transaction()`. The outer block has no expected exception. The test then checks a usable connection with `SELECT 1`. The same test has other internally caught timeout arms (`:77–102`); `test_timeout_04` also catches a cursor timeout inside a transaction (`:60–66`). This is existing source-level coverage of normal exit after a caught error in an aborted transaction.

**INFERRED — compatibility implication.** A change that raises when this outer `COMMIT` receives `ROLLBACK` is likely to require changes to existing timeout-test expectations. This is stronger than a hypothetical concern about unknown applications. It does not establish that maintainers consciously chose rollback-as-success, nor that those tests currently pass on the review environment; neither was run.

**INFERRED — smallest PY-2 replacement for the entire compatibility bullet:**

> Raising here changes existing behaviour. In particular, `test_timeout_06` catches `InFailedSQLTransactionError` inside a transaction and expects the block to exit normally ([test_timeout.py:104–113](https://github.com/MagicStack/asyncpg/blob/13b01910da3fe01b8241c31cc86eccb1301a2d39/tests/test_timeout.py#L104-L113)). Would you want the transaction API to raise on a `ROLLBACK` command status, or retain the current completion semantics?

**VERIFIED — cause of the missed evidence.** The drafts' internal notes describe AST scans for `try/except`. A fresh scan reproduces their narrow results: psycopg's two `except` handlers inside direct transaction contexts catch `ZeroDivisionError`; asyncpg has no such exception handlers and one explicit test `.commit()` call. A broader scan of `pytest.raises` and `self.assertRaises`, including transaction aliases, finds the counterexamples above. `checks.py` and `checks.txt` record both forms. An AST scan for `Try` nodes alone cannot establish the advertised absence of tests.

## 2. Medium: reproduction setup understates an unconditional initial database drop

**VERIFIED — quotations.** PY-1b's script says “Creates database audit_psycopg_tx, drops it at the end.” PY-2 says “The program creates `asyncpg_commit_rollback` and drops it at the end.” Both scripts first run `DROP DATABASE IF EXISTS ... WITH (FORCE)` against the server selected by `DATABASE_URL` (psycopg evidence program `:80–86`; asyncpg evidence program `:135–138`). There is no check that an existing database with that fixed name belongs to the reproduction.

**INFERRED — maintainer reading.** The prose suggests a newly created scratch database, while executing the program can first remove an existing same-named database and terminate its connections. This is a concrete property of the posted code, not an observed data-loss incident. A clear execution precondition fixes the disclosure without altering the preserved program.

**INFERRED — smallest replacement/addition before each program:**

> Run this only against a disposable local PostgreSQL server. The script first drops any existing database named `audit_psycopg_tx` with `FORCE`, recreates it, and drops it at the end. `DATABASE_URL` must permit that database creation and removal; the script connects to `postgres` for those operations.

**INFERRED — for PY-2, substitute** `asyncpg_commit_rollback` **and use:** “The script uses the database in `DATABASE_URL` for those administrative operations.” Its `database=None` admin connection uses the supplied DSN rather than explicitly selecting `postgres`.

## 3. Medium: the asyncpg example command is usage notation inside a shell code block

**VERIFIED — quotation:** `DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python asyncpg_commit_rollback.py [asyncio|uvloop]` (PY-2 line 97).

**VERIFIED — problem.** An unquoted `|` is a shell pipeline operator. A shell does not pass `[asyncio|uvloop]` as a choice to Python. A harmless zsh demonstration using `printf` in place of the program exits 127 with `bad pattern: [asyncio` and `command not found: uvloop]`; no database or Python reproduction was executed (`checks.txt`). The program actually accepts the literal argument `asyncio` or `uvloop`, with asyncio as the default.

**INFERRED — maintainer reading.** “The advertised reproduction command cannot be pasted.” This is avoidable even if a reader recognizes conventional usage notation.

**INFERRED — smallest replacement outside the preserved script:**

```sh
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python -I asyncpg_commit_rollback.py asyncio
DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python -I asyncpg_commit_rollback.py uvloop
```

**INFERRED — optional setup addition.** State that the script must be saved as the named file and run in a virtualenv containing `asyncpg==0.32.0` and `uvloop==0.23.0`. PY-1b would benefit from one external execution sentence giving its filename, `psycopg[binary]==3.3.6`, and database privileges. No script edit or new experiment is needed to add accurate surrounding instructions.

## 4. Low: psycopg's savepoint bullet describes the catch at the wrong scope

**VERIFIED — quotation:** “the control, where an inner `conn.transaction()` (a savepoint) catches the same error, committed” (PY-1b line 72).

**VERIFIED — problem.** In the executed program, `except errors.UniqueViolation` is *outside* the inner `with` and inside the outer `with` (`psycopg_transaction_block.py:48–56`). This lets the error reach the inner context manager so it can roll back the savepoint. The program's printed heading repeats the loose wording, but its code shows the actual scope.

**INFERRED — maintainer reading.** A reader copying the prose as a recipe could catch inside the savepoint block, preventing that block from taking its exception-exit recovery path. The distinction matters to the control's interpretation.

**INFERRED — replacement bullet:**

> the savepoint control caught the error outside an inner `conn.transaction()` block, while still inside the outer block; the outer transaction committed and its row was visible.

**INFERRED — keep the historical program/output unchanged.** Correct the surrounding description; do not rewrite its recorded heading and call the output byte-identical.

## 5. Low: the downstream bullet generalizes beyond the identified runs

**VERIFIED — quotation:** “Tortoise ORM's `in_transaction()` and SQLAlchemy's asyncpg dialect commit through `Transaction.commit()`, so they also return normally in this situation.” (PY-2 line 315).

**VERIFIED — narrower evidence.** Tortoise 1.1.9 on asyncpg 0.32.0 has three matching TX-01A records, including `COMMIT; -> ROLLBACK`; SQLAlchemy Core 2.1.5 on asyncpg 0.32.0 has three matching `engine.begin()` records in P1 arm E. The installed source inspected for these versions calls `Transaction.commit()` (Tortoise `backends/asyncpg/client.py:197–203`; SQLAlchemy `dialects/postgresql/asyncpg.py:902–908,919–926`). These observations support the named versions and entry points, not every framework configuration or ORM error path.

**INFERRED — maintainer reading.** The unversioned “so” can sound like an untested deduction about all downstream transactions. Lead with the measured cases or cut the bullet.

**INFERRED — replacement:**

> I also observed normal exit after a caught `23505` through Tortoise 1.1.9's `in_transaction()` and SQLAlchemy Core 2.1.5's `engine.begin()`, both using asyncpg 0.32.0. Their commit paths call `Transaction.commit()`.

## 6. Low: asyncpg's full output violates the requested folding style

**VERIFIED — problem.** PY-2 closes its program `<details>` at line 274, then leaves the complete 19-line output at `:278–298` expanded. The house style explicitly puts long output in `<details>`. Its “Actual” section already communicates the result without the full output.

**INFERRED — maintainer reading.** A reader must scan a long issue before reaching expected behaviour and the source explanation. The result is understandable without expanding the code or output, so folding the output loses nothing essential.

**INFERRED — smallest structural replacement:** put the existing output paragraph and exact code fence inside `<details><summary>Complete asyncio output</summary> ... </details>`. Keep “The uvloop runs differ only in the event-loop line and the transaction IDs” outside or in that summary. Do not change the output bytes.

# Claim ledger

**VERIFIED — evidence keys and scope.** Local paths below are relative to the repository root. `P` means `research/python-upstream-contribution/upstream-drafts/psycopg-1453-comment.md`; `A` means the sibling `asyncpg-commit-rollback.md`. `PE` means `research/python-ecosystem-contribution-audit/`; `CE` means `research/python-upstream-contribution/chk-2-asyncpg/`; `G` means `research/python-production-failure-gap-analysis/`. `PS` is upstream psycopg at `99356800e90aa0e7b604f652d714ef0f33422b47`; `AS` is upstream asyncpg at `13b01910da3fe01b8241c31cc86eccb1301a2d39`. Their full SHAs were independently fetched from the GitHub commits API. All source line references in this ledger refer to those pins. `upstream-checks.json` preserves selected API fields, every search result, and relevant pinned source excerpts.

## PY-1b

| ID / location | Factual claim | Status | Evidence and qualification |
| --- | --- | --- | --- |
| P01 `:66` | `Connection.transaction()` is a second public API | VERIFIED | PS `psycopg/psycopg/connection.py`, `Connection.transaction`; PS `transaction.py:258–274`. |
| P02 `:66` | Existing #1453 does not cover it | VERIFIED | Fresh issue body from REST API covers `Connection.commit()`, cursor COMMIT, and downstream callers; no transaction-context/status example. `upstream-checks.json`, `psycopg-1453`. |
| P03 `:68` | UniqueViolation is caught inside the outer block, which ends normally | VERIFIED | PE program `:48–64`; PE output `:7–60`, three subject arms. |
| P04 `:68` | psycopg 3.3.6, PostgreSQL 18.6 | VERIFIED, recorded | PE output `:2–3`. No fresh runtime reproduction. |
| P05 `:68` | Three repetitions agree | VERIFIED | PE output `:7–60`; same caught/recovered properties in all three. One process, fresh connection for each arm, not three independent processes (program `:41–42,104–110`). |
| P06 `:70` | No exit exception; `tx.status == 'committed'` | VERIFIED, recorded | PE output caught arms `:10–11,28–29,46–47`; property is printed as `.status.value`, not a bare string attribute (program `:72`). |
| P07 `:71` | Separate connection reads transaction fate | VERIFIED | PE program `:31–38,66`; `autocommit=True` default at `:23`. |
| P08 `:71` | Captured ID belongs to the transaction being tested | VERIFIED, method | Marker INSERT and `pg_current_xact_id()` use the subject connection before the failing statement (`:48–50`). Interpretation of resulting fate is discussed below. |
| P09 `:71` | Fate aborted, preceding row absent | VERIFIED, recorded | PE output caught arms `:13–14,31–32,49–50`. |
| P10 `:71` | Subject is idle; last statement COMMIT | VERIFIED, recorded | PE output `:15,33,51`; subject remains open until after observer reads (program `:65–67`). This is last-statement evidence, not the reply tag. |
| P11 `:72` | Savepoint control commits with visible marker | VERIFIED, recorded | PE output `:16–24,34–42,52–60`; normal control `:4–6`. |
| P12 `:72` | Inner block “catches” the error | MISLEADING | VERIFIED catch is outside inner context, PE program `:52–56`; finding 4. |
| P13 `:76` | Quoted block contract | VERIFIED | PS `docs/basic/transactions.rst:161–162`; words verbatim after joining source line wraps. |
| P14 `:76` | First documentation link points to its supporting lines at the pin | VERIFIED | Exact URL pin resolves to PS; `?plain=1#L158-L162` includes the quoted text. |
| P15 `:77` | “allowing you to check the final outcome ... transaction status” quotation | VERIFIED | PS `docs/basic/transactions.rst:348–350`; wording verbatim as rendered, with RST `` `!with` `` represented as Markdown `` `with` `` and line wraps joined. Not byte-identical raw RST markup. |
| P16 `:77` | Second documentation link supports that quote | VERIFIED | Exact PS URL `?plain=1#L347-L350`. |
| P17 `:79` | Block should raise or status should differ | Not a factual claim | INFERRED desired API semantics; maintainer decision, not established by the measurement. |
| P18 `:81` | A change confined to Connection.commit would miss this path | VERIFIED, source | PS `transaction.py:133–140,180–190` calls `_exec_command` directly; BaseConnection `_commit_gen` is distinct at `_connection_base.py:577–595`. A shared-helper change could cover both; the word “alone” matters. |
| P19 `:81` | BaseTransaction sets COMMITTED before sending COMMIT and discards result | VERIFIED, source | PS `transaction.py:134–140`; outer command selected at `:188–190`. |
| P20 `:81` | Source link identifies these lines | VERIFIED | Exact PS URL `transaction.py#L133-L140` includes status assignment and direct execution; COMMIT command selection is elsewhere (`:180–190`). |
| P21 `:83` | `test_auto_transaction_fail` async and sync copies call commit after an error | VERIFIED | PS `tests/test_connection_async.py:401–421`; sync `tests/test_connection.py:405–425`, commit at 422. |
| P22 `:83` | Test expects normal return, IDLE, no row | VERIFIED, source | Async `:418–421`, sync `:422–425`. A newly raising call would violate these written expectations; tests were not executed. |
| P23 `:83` | Current behaviour “may be intended” | Not a factual claim | INFERRED, appropriately qualified inference from tests. No maintainer decision on #1453 yet. |
| P24 `:83` | No transaction-block test catches database errors inside | WRONG | VERIFIED counterexamples PS `tests/test_pipeline.py:506–511`, async `:507–512`; finding 1. |
| P25 `:83` | Linked async test range is correct | VERIFIED | Exact PS URL `tests/test_connection_async.py#L401-L421`; correct function and relevant assertions. |
| P26 `:85` | AsyncTransaction shares BaseTransaction._commit_gen | VERIFIED, source | PS `transaction.py:277`, class inheritance; no overriding commit generator. |
| P27 `:85` | Async, pipeline, and COMMIT-raises not run | VERIFIED within supplied recording | PE program is sync, has no pipeline or deferred-constraint arm. NOT CHECKED whether the author performed additional unrecorded work. |
| P28 `:87` | PR/test offer depends on maintainers deciding | VERIFIED, text | Explicit conditional wording. No claim about a completed PR. |
| P29 program/output | Embedded program/output are complete and unchanged | VERIFIED | Byte comparison, 4,571 / 2,189 bytes; SHA-256 values below and `checks.txt`. Output has 60 lines. |
| P30 program header/output | Python 3.13.11; binary psycopg; libpq 180006 | VERIFIED, recorded | PE output `:1–3`; program `:82–84`. Numeric libpq 180006 means 18.6, not 18.0.6. |
| P31 program docstring | Creates scratch DB, drops it at end | MISLEADING by omission | VERIFIED creation/final drop plus initial forced drop, program `:85–86,112–114`; finding 2. Cleanup on arbitrary exceptions is not guaranteed. |
| P32 output | Caught arms INERROR → IDLE; recovered INTRANS → IDLE; normal control visible | VERIFIED, recorded | PE output all three repetitions plus `:4–6`. These are connection/transaction fields, not proof that every earlier operation succeeded. |

## PY-2

| ID / location | Factual claim | Status | Evidence and qualification |
| --- | --- | --- | --- |
| A01 title | Transaction.commit returns normally when COMMIT is answered ROLLBACK | VERIFIED, recorded + source inference | CE explicit arms return None with aborted fates; raw arms expose ROLLBACK; AS `transaction.py:175–192` discards `execute` status. Direct trace for the same explicit CHK-2 command is not recorded. Tortoise supplies a separate same-path tag trace. |
| A02 `:78` | asyncpg 0.32.0 | VERIFIED, recorded | Six CE output headers and pip-freeze. |
| A03 `:78` | transaction.py unchanged on master | VERIFIED | Fresh default-branch SHA is AS; release v0.32.0 archive's transaction.py matches master byte-for-byte, SHA `b8026893a4a1c7bf8a76de65e0d5fe189b4bc552523d74ce254af219d6c8546f`. |
| A04 `:79` | PostgreSQL 18.6 | VERIFIED, recorded | All six output headers; CE server.log line 50. |
| A05 `:79–81` | Exact Docker image attribution; original local container/non-SaaS setup | UNVERIFIED independently | CE README Environment records the image, port and setup; supplied log identifies PostgreSQL version but no retained `docker inspect` independently proves image digest or endpoint exclusivity. No contrary evidence found. |
| A06 `:82` | Python 3.13.11 | VERIFIED, recorded | Six CE output headers and pip-freeze. |
| A07 `:83` | arm64/macOS platform | VERIFIED in part | Output headers say Darwin arm64. Exact “macOS 26.6.2” is UNVERIFIED independently: present in README, no separate OS-version capture supplied. |
| A08 `:84` | No pgbouncer | UNVERIFIED independently | Consistent with recorded direct container setup; no independent connection-route capture. Not contradicted. |
| A09 `:85–86` | pip wheel installation; no local Cython build | UNVERIFIED independently | pip-freeze records exact versions and wheel-only install command, but does not itself prove that command's historical execution or wheel provenance. No install transcript inspected. |
| A10 `:87–88` | Three asyncio and three uvloop 0.23.0 runs, same results | VERIFIED, recorded | Six CE output files; uvloop version in three headers, pip-freeze `:4`. Full bodies match after masking first header and transaction IDs (`checks.txt`). |
| A11 `:88` | uvloop hyperlink | VERIFIED, destination identity | Template's canonical `https://github.com/magicstack/uvloop`; fresh public repository API response identifies MagicStack/uvloop. It is not a pinned code citation. |
| A12 `:90` | Every “statement fails inside a transaction” leads to whole-transaction abort | OVERSTATED if read without context | VERIFIED reproduction is a server UniqueViolation without savepoint recovery. Client errors and savepoint recovery are different; draft's own control demonstrates recovery. INFERRED optional tightening: “After the caught UniqueViolation in the reproduction below, without savepoint recovery...” |
| A13 `:90` | Managed context exits normally; explicit commit returns None | VERIFIED, recorded | CE asyncio.rep1.out `:3–9`, same in remaining five outputs. |
| A14 `:90` | Later rollback says already committed | VERIFIED, verbatim | CE output `:10`; AS `transaction.py:153–157,194–195,222–227` guards before issuing SQL. Measured on explicit transaction only. |
| A15 `:90` | Earlier row is gone | VERIFIED, recorded | CE output `:6,11,15`; all six runs. |
| A16 `:90` | Raw execute COMMIT returns ROLLBACK on same server | VERIFIED, recorded | CE output `:12–15`, same program DSN and fresh connection for each arm. Not the managed transaction's own return trace. |
| A17 `:94` | Requires database creation; creates/drops named database | MISLEADING by omission | VERIFIED CE program `:27–30,135–138,149–152`: also forcibly drops existing database first; finding 2. |
| A18 `:94` | Each arm own connection; separate witness reads fate, row, last statement | VERIFIED, method | CE program `:27–30,55–64,67–128,146–149`. Probe uses asyncpg too; psql is additional independent corroboration. |
| A19 `:97` | Shown command is runnable as written | WRONG as a pasteable shell command | VERIFIED `|` parsed as pipeline and bracket syntax fails in zsh; finding 3. It is recognizable usage notation, not executable instructions. |
| A20 program | Program is exact executed evidence | VERIFIED artifact identity | 5,987 bytes; SHA below; CE program and embedded Python identical. Historical execution itself not re-run. |
| A21 `:276` | uvloop differs only in event-loop line and transaction IDs | VERIFIED | All six bodies normalized independently; first line includes uvloop's version too, covered by “event-loop line”. |
| A22 output `:279–280` | Event loop asyncio.unix_events._UnixSelectorEventLoop; server Debian version | VERIFIED, recorded | Exact CE asyncio.rep1.out `:1–2`. |
| A23 output `:281–284` | Managed caught23505, normal exit, xid757 aborted, no marker, idle, COMMIT; | VERIFIED, recorded | Exact CE asyncio.rep1.out `:3–6`; psql row for 757; server.log `:78–92`. |
| A24 output `:285–289` | Explicit caught23505, return None, rollback InterfaceError, xid758 aborted, no marker, idle, COMMIT; | VERIFIED, recorded | CE asyncio.rep1.out `:7–11`; psql 758; server.log `:93–107`. |
| A25 output `:290–293` | Raw caught23505, status ROLLBACK, xid759 aborted, absent marker, idle, COMMIT | VERIFIED, recorded | CE asyncio.rep1.out `:12–15`; psql 759; server.log `:108–122`. |
| A26 output `:294–297` | Control catches outside savepoint, exits normally, xid760 committed, marker visible, idle, COMMIT; | VERIFIED, recorded | CE asyncio.rep1.out `:16–19`; psql 760; server.log `:123–138`. |
| A27 `:302` | Both APIs should raise and avoid committed state | Not a factual claim | INFERRED desired contract change. Existing test expectations make maintainer agreement substantive, not a formality. |
| A28 `:306` | Both normal; later rollback says committed; PostgreSQL aborted; control committed | VERIFIED, recorded | CE outputs; later rollback was performed only on explicit arm. It was not performed on managed arm. |
| A29 `:310` | __commit drops execute result, then sets COMMITTED | VERIFIED, source | AS `asyncpg/transaction.py:186–192`, exact linked range. Nested branch uses RELEASE SAVEPOINT (`:181–184`); proposed fix must distinguish that branch. |
| A30 `:310` | execute return is command status | VERIFIED, source | AS `connection.py:348`; quoted “Status of the last SQL command” is verbatim. No-argument execute returns `_protocol.query` result (`:351–355`). |
| A31 `:310` | Both pinned source links identify supporting lines | VERIFIED | Full AS SHA in both URLs; transaction range and docstring line correct in independently downloaded archive. |
| A32 `:310` | Raw arm makes “the same execute() call directly” | VERIFIED with qualification | Same public method and equivalent COMMIT operation. Raw query is `COMMIT`, transaction API query is `COMMIT;`; different connections. Status on API path is a source/semantics inference, not a direct CHK-2 tag capture. |
| A33 `:314` | Other SQLSTATEs are direct asyncpg statements, caught inside managed transaction | VERIFIED | G p6_other_sqlstates.py `:183–223`; timeout at `:189–191`, real lock cycle `:192–197`, REPEATABLE READ update conflict `:198–203,212`. No SQLAlchemy intermediary in these arms. |
| A34 `:314` | 57014,40P01,40001 each tested three times; normal exit | VERIFIED, recorded | G output/p6.jsonl `:19–27`; exact caught code, normal API outcome, aborted fate, marker false in all nine rows. |
| A35 `:314` | Serialization failures were REPEATABLE READ | VERIFIED, method | G p6_other_sqlstates.py `:212`; p6 output shows repeatable_read transaction repr in `:25–27`. No claim about COMMIT-time SERIALIZABLE failures is warranted. |
| A36 `:314` | Each P6 session's last logged statement COMMIT | VERIFIED against supplied summary | G output/p6.server-log-endings.txt `:19–27` has COMMIT for all nine. NOT CHECKED raw P6 server log: not among supplied G output files. The script closes sessions before witness activity check, explaining null backend_after. |
| A37 `:315` | Tortoise and SQLAlchemy call asyncpg Transaction.commit | VERIFIED for inspected versions | Installed Tortoise source `:197–203`; SQLAlchemy source `:902–908,919–926`; recorded versions Tortoise 1.1.9, SQLAlchemy 2.1.5. |
| A38 `:315` | They also return normally “in this situation” | OVERSTATED without version/path bounds | VERIFIED narrower Tortoise TX-01A, 3/3; G P1 arm E, 3/3. INFERRED generalization to every downstream entry point is unwarranted; finding 5. |
| A39 `:316` | psycopg Connection.commit has same behavior; #1453 is relevant | VERIFIED, recorded and live | Original reproduction .txt and live issue body agree. Explicit cross-repository shorthand resolves to psycopg/psycopg #1453, not MagicStack/asyncpg #1453. |
| A40 `:317` | Raising changes behavior for swallowed-error callers | VERIFIED as a source-level contract difference | Current __commit returns normally unless execute raises; new raise would change that path. Actual effect on external applications is INFERRED, not measured. |
| A41 `:317` | No tests cover this normal exit after caught error | WRONG | VERIFIED AS test_timeout.py `:104–113`, also `:60–66,77–102`; finding 1. |
| A42 `:319` | PR offer is conditional on acceptance | VERIFIED, text | “If raising here is acceptable”; no implementation promised as already complete. |

# Evidence integrity and method attack

## Byte identity

**VERIFIED — all four embedded artifacts match byte-for-byte, including final newlines.** `checks.py` extracts only the posted regions, matches fenced blocks, and compares bytes; these are the recomputed hashes:

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| PE psycopg_transaction_block.py | 4571 | `951bcb4917cd777486591391f7be3f075d913f0070946d83c1e11de5cb39148b` |
| PE psycopg_transaction_block.txt | 2189 | `079ce18aacc8e1a07a6b26c708b66dbeb21532a80a88895442c270299579c296` |
| CE asyncpg_commit_rollback.py | 5987 | `891ffa6a9efc9332f5d3991f904fec5379bd760dc0fc4fe36baca06cd0b0c104` |
| CE output/asyncio.rep1.out | 1233 | `4cf47347fec1779ad6ea73b434f3343c7765d5e929e3f37cbde3f34bd54b1bac` |

**VERIFIED — supporting hashes.** All six CE output hashes match the full hashes in its README. Recomputed server.log, psql-xact-status.txt, server_log_sessions.py, server-log-sessions.txt, and pip-freeze.txt hashes match the README's full hashes. The existing cross-check was executed with Python 3.14.2 `-I` and returned 0, reproducing its saved output. A separately written parser in `checks.py` also matched all 24 distinct transaction IDs to the subject PID/application name, duplicate-key error, transaction-control statements, and psql fate: 18 aborted and six committed. This is verification of retained recordings, not a newly observed server.

**VERIFIED — two internal-note errors, outside posted text.** CE README's abbreviated uvloop.rep1 hash ends `…2ea`, but its full hash and the actual file end `…954b`. P's notes call numeric libpq `180006` “18.0.6”; PS `pq/misc.py:177–189` formats it as 18.6. Neither incorrect rendering occurs in the posted prose/output. Preserve the evidence files; any later correction should be confined to those descriptions.

## Could the observation method explain away the result?

| Attack | Assessment | Evidence / limitation |
| --- | --- | --- |
| Wrong transaction ID, an observer's ID, or an autocommitted marker | VERIFIED method rejects this explanation for the shown paths | Both programs insert marker and capture ID using subject connection within explicit outer transaction. Asyncpg logs independently associate IDs757–810 with the corresponding subject sessions. The witness never supplies the subject xid. |
| IDs reused or historical status too old | INFERRED not a plausible explanation in these recordings | IDs are distinct and checked immediately; CE psql rechecks them shortly after the runs. No wraparound/truncation symptoms are recorded. Other cluster conditions are NOT CHECKED. |
| Witness has stale snapshot or sees another database | VERIFIED code avoids persistent witness transactions; INFERRED the recordings are coherent | Psycopg creates fresh autocommit observers; asyncpg witness executes each statement outside an explicit transaction. Both use the same DSN/DB selection as subjects. Control marker visibility and matching log/PID/xid data counter a stale-snapshot explanation. They do not independently authenticate the original DSN/server topology. |
| Both driver and witness share the same faulty driver | VERIFIED limitation, with additional corroboration | Asyncpg witness uses asyncpg, but psql independently records all 24 fates. Psycopg has no psql/server-log corroboration for this exact block run; its three observer fields and driver states are internally consistent. |
| pg_stat_activity.query proves the command reply | VERIFIED: it does not | It is last-statement text, not a command tag or commit receipt. CE server log also logs statements, not CommandComplete responses. Fates and markers establish rollback; raw arm exposes tag on a different transaction. |
| Connection.close silently rolled back before the check | VERIFIED false for primary PE/CE programs | Each reports fate/visibility while the subject is still open, and closes afterward. Explicit asyncpg rollback fails locally before executing any SQL; CE log has no rollback statement for that arm. |
| Savepoint control measures only a rolled-back subtransaction | VERIFIED false for captured control ID | ID captured after outer marker INSERT and before inner savepoint; outer marker survives. Error escapes inner context before being caught, allowing rollback-to-savepoint. Control does not establish behavior for catching inside that inner block. |
| Duplicate key did not actually happen | VERIFIED recordings contradict this | Primary stdout records caught23505; CE server log records duplicate-key error for all 24 subject sessions. Normal and savepoint controls show marker persistence under successful completion. |
| A separate failure, trigger, or independent deletion erased markers | INFERRED no supporting evidence | Setup creates only plain item/uniq tables, no triggers. Fates corroborate marker absence. Environment outside supplied setup was not independently recreated. |
| P6 close() could be responsible for abort | VERIFIED limitation of P6 ordering, not primary CE | P6 closes subject before observing, and raw log is absent here. The retained ending summary says COMMIT, which supports the claimed path, but is weaker evidence than CE's retained full log. Do not present P6 as an independent managed-command-tag capture. |

**INFERRED — method conclusion.** There is no verified alternative explanation that defeats the primary observed mismatch. The clear division is: normal return and status/error-message observations are recorded; aborted fate and marker visibility are recorded independently of those API signals; actual command-tag attribution to the managed CHK-2 call is inferred from source, the raw arm, and separate downstream tracing. Neither draft should imply a protocol trace of its own managed COMMIT.

# Fresh upstream checks

**VERIFIED — access and current state.** Initial sandbox DNS lookup failed. Approved read-only `curl` requests subsequently worked. Sources were fetched with unauthenticated GitHub REST requests and GitHub Discussions HTML; default-branch and release archives were read locally. No GitHub login, token, GraphQL mutation, or publishing operation was used.

| Check | Result | Evidence |
| --- | --- | --- |
| psycopg default branch | VERIFIED `master`, `99356800e90aa0e7b604f652d714ef0f33422b47` | REST repository metadata and commits/master; all four posted pinned source ranges checked. |
| asyncpg default branch | VERIFIED `master`, `13b01910da3fe01b8241c31cc86eccb1301a2d39` | REST metadata and commits/master; both posted pinned source ranges checked. |
| Release/default-branch transaction code | VERIFIED identical for psycopg 3.3.6 and asyncpg v0.32.0 | Byte comparison of release/default archives; asyncpg hash above. This checks transaction.py, not every project file. |
| Latest PyPI versions | VERIFIED psycopg 3.3.6 and asyncpg 0.32.0 at check time | `https://pypi.org/pypi/psycopg/json`, asyncpg equivalent. No newer release requiring investigation was found. |
| #1453 | VERIFIED open; zero comments, zero timeline entries | Fresh issue, comments and timeline REST responses. Created 2026-10-22T00:52:41Z, which is 2026-10-21 in the user's timezone; no date discrepancy. |
| #1453 duplication/response gate | VERIFIED no maintainer response or transaction-context discussion in current body | Fresh body and empty comment/timeline responses; original local issue body agrees. |
| Psycopg guidance | VERIFIED root README Hacking section gives local setup, pytest, pre-commit, conventional commits | Root README at PS. No issue template, CONTRIBUTING, SECURITY, code-of-conduct or AI policy found in root/.github/docs scope. This is a bounded absence claim. |
| Asyncpg issue template | VERIFIED fields match `.github/ISSUE_TEMPLATE.md` | AS template questions copied faithfully. Template requests clear reproduction instructions. |
| Asyncpg other guidance/policies | VERIFIED no CONTRIBUTING/SECURITY/code-of-conduct/AI policy found in root/.github/docs scope | Inventory and text search of archived files. README contains pip installation guidance. No contrary policy found. |
| Organization defaults | VERIFIED public REST requests for psycopg/.github and MagicStack/.github return404 | This establishes no publicly accessible defaults repo through these endpoints, not that no private repo/policy exists. |

## Duplicate queries and results

**VERIFIED — search method.** Each REST search used `/search/issues?per_page=100&q=<encoded query>`, without an open/closed or created-date restriction; this covers issues and PRs. All results fit one page and returned `incomplete_results:false`. `upstream-checks.json` records every returned number, title, state, and URL. Counts below are matching search results, not counts of duplicates.

| Query | Results | Review interpretation |
| --- | ---: | --- |
| `repo:psycopg/psycopg commit rollback` | VERIFIED 40 | INFERRED nearest are #1453,#969,#967,#1184; cancellation #1451/PR#1454 is a different entry path. |
| `repo:psycopg/psycopg transaction status` | VERIFIED 36 | INFERRED#1184/#969 concern adding status;#1283/#1284 concern lost connections, not caught23505 + normal COMMIT. |
| `repo:psycopg/psycopg caught` | VERIFIED 25 | INFERRED#967/#969 are relevant history, not a separate report of this reproduction. |
| `repo:psycopg/psycopg "command tag"` | VERIFIED 2 | VERIFIED#1453 and #1062 (cursor statusmessage documentation). |
| `repo:MagicStack/asyncpg commit rollback` | VERIFIED 16 | INFERRED nearest #508,#1386,PR#1387,PR#1399; no matching report found. |
| `repo:MagicStack/asyncpg "already committed"` | VERIFIED 0 | INFERRED no duplicate found by this phrasing. |
| `repo:MagicStack/asyncpg caught` | VERIFIED 19 | INFERRED#508 nearest, concerning deferred constraint timing. |
| `repo:MagicStack/asyncpg aborted` | VERIFIED 9 | INFERRED#1130 asks for public state;#1399 concerns failed BEGIN. |
| `repo:MagicStack/asyncpg "silent"` | VERIFIED 24 | INFERRED no same-mechanism report found among results. |
| `repo:MagicStack/asyncpg "commit status"` | VERIFIED 0 | INFERRED no duplicate found by this phrasing. |

**VERIFIED — Discussions searches.** GitHub Discussions HTML queries used `discussions_q=commit`, `rollback`, and `transaction status` for psycopg (24,14,5 listed results), and `commit`, `rollback`, `aborted` for asyncpg (1,1,0). Saved result titles/links are in `upstream-checks.json`. No next-page link was present in the returned search pages. This is a search-index check, not a complete read of every historical discussion or comment.

**VERIFIED — nearby Discussions read.** Psycopg #826 concerns an implicitly open outer transaction;#923 asks about cursor/autocommit status;#330 concerns wrapper/logging migration;#28 asks about transaction blocks versus cursor contexts. Asyncpg #881 inserts through the pool rather than the acquired connection, acknowledged in its answer. They differ from the posted scripts, which operate on the same subject connection within an explicitly managed transaction.

**VERIFIED — nearby issue/PR bodies read.** Psycopg #967's maintainer answer describes exception-driven rollback, and #969 asks to retain commit/rollback path state. Asyncpg #1130 is an open public-state feature request;#508 is closed and concerns a COMMIT-time deferred constraint exception;#281 is a closed decorator-wrapper question. Asyncpg #1386 and open PRs #1387/#1399 address failed BEGIN registration, not dropped COMMIT result status. Their inspected bodies do not supply a fix for this report.

**INFERRED — duplicate verdict.** A follow-up on #1453 is the appropriate psycopg venue. No matching asyncpg issue, PR, or Discussion was found in this fresh search. This is not proof none exists, and source-level tests are not equivalent to an already filed issue.

# Maintainer rehearsal

| Text / strongest objection | Does the draft answer it? | Judgment and smallest improvement |
| --- | --- | --- |
| PY-1b: “You swallowed the error; rollback or use a savepoint.” | VERIFIED draft shows a savepoint control and quotes outcome/status docs. | INFERRED substantially answered: ask about accurate final status, avoid asserting that catching alone is supported recovery. Fix the control's catch scope. |
| PY-1b: “Normal commit after an error is intentional; tests rely on it.” | VERIFIED draft acknowledges commit() test, but wrongly denies transaction() catch tests. | INFERRED incompletely answered; finding1 is essential. The status promise remains the strongest distinction even if maintainers preserve normal exit. |
| PY-1b: “Already tracked by #1453/#969; is this worth another thread?” | VERIFIED this is a comment by original author;#1453 lacks this API/status example. | INFERRED venue and additive evidence are appropriate. Keep separate code paths and concise conditional offer. No new psycopg issue. |
| PY-2: “This is PostgreSQL's normal behavior and application misuse.” | VERIFIED raw arm reports ROLLBACK, control shows legitimate savepoint recovery, and rollback() error identifies asyncpg state. | INFERRED reasonable case for discussing transaction-state reporting, but docs promise only “commit changes”; raising is a proposed policy change, not an established contract violation. |
| PY-2: “A new exception breaks timeout/cancellation users and our tests.” | VERIFIED draft admits generic compatibility risk but denies existing tests. | INFERRED currently invites an avoidable argument. Cite test_timeout_06 and ask maintainers which semantics they want. Do not prescribe an exception class. |
| PY-2: “Cannot reproduce; your witness shares asyncpg or this is another connection.” | VERIFIED exact standalone script, six outputs, independent psql and full server log; each subject uses its own connection consistently. | INFERRED method is strong. Repair pasteable command, disclose setup requirements, keep provenance distinctions. A new experiment would strengthen portability, not repair the already verified script identity. |

# Fitness and open questions

**VERIFIED — venue and tone.** PY-1b is a follow-up to an existing issue by its original author; PY-2 follows the asyncpg template. Both PR offers are conditional. Neither post claims a measured production frequency, a tested fix, or tested pipeline behavior. The expanded psycopg text contains its central result, documentation, compatibility note, and limits before the folded program. Asyncpg contains its result before the program, but its expanded output is a house-style exception (finding6).

**VERIFIED — outgoing-content scan.** Neither posted region contains a real password, token, absolute local filesystem path, private document URL, or personal narrative. Database usernames, localhost ports, scratch database names and `...` password placeholder are not actual credentials. The psycopg docstring does contain the unexplained internal acronym “PPCS”; it is a project reference, not confidential context. Relative script filenames are reproduction filenames, not inaccessible local evidence links. The draft's internal author/status notes are outside the posted boundary.

**INFERRED — answer (a): keep the psycopg program verbatim.** The docstring and throwaway port do not invalidate reproduction, and changing them adds no scientific value. Add clear runnable instructions outside the code if needed. If the author elects to remove “Diagnostic, not a PPCS case”, save a new script, rerun it and publish its matching output; do not silently tidy a block still described as the executed program. There is no need to delay this comment solely for a cosmetic rerun.

**INFERRED — answer (b): drop the asyncpg other-SQLSTATE bullet from the first issue.** Its direct-asyncpg claims are supported by nine retained P6 rows, so it is not a false claim. However, its separate program is not included, its original raw server log is not supplied here, and the detailed timeout/serialization discussion distracts from the one complete reproduction and the newly found timeout-test compatibility question. Retain those recordings for a requested follow-up. If kept, say only “In separate direct asyncpg runs, I observed the same normal block exit and aborted fate for ...”; do not imply the included program tests those conditions.

**INFERRED — answer (c): other cuts.** Remove both false no-tests sentences, replacing them with the positive compatibility evidence in finding1. Fold asyncpg's full output. The downstream bullet is optional; either cut it or use finding5's measured/versioned form. Keep the psycopg compatibility qualification, both documentation quotations, both untested-mode caveats, raw/savepoint controls, and conditional PR offers. Optionally narrow asyncpg's introductory generalization to the reproduced UniqueViolation case. The decided exclusions of SQLAlchemy-observed extra SQLSTATEs from PY-1b and separate SQLAlchemy/Tortoise reports remain respected.

# Re-runs, commands, and unchecked items

**NOT CHECKED — no fresh database experiment.** Neither the six-run asyncpg program nor the psycopg database program was re-executed. `postgres` and `initdb` were absent from PATH. I chose not to provision a database or use external Docker infrastructure for this optional step. No database server was contacted, started, stopped, or deleted by the review. There is consequently no new server version, event-loop result, platform variation, or runtime discrepancy to report.

**VERIFIED — artifact checks executed.** Review checks used Python 3.14.2 with `-I`, macOS tooling, without installing packages. This is the reviewer interpreter, not a replacement for the original Python 3.13.11 runtime. `checks.py` is the exact independent analysis script; `checks.txt` its output. The retained existing `server_log_sessions.py` was also run read-only, and its output is `server-log-recheck.txt`. Neither script connects to a database. `commands.txt` gives reproduction commands for these review checks and read-only acquisition methods; `request-manifest.json` gives the exact HTTP endpoints/queries.

**NOT CHECKED — execution and portability limits.** No upstream tests were run. No new fix was implemented. Python 3.13.11, the original exact macOS minor release, original wheel installation provenance, original Docker image identity, and original routing/no-pgbouncer claims were not independently reconstructed. No other PostgreSQL version, Linux client, pool, pgbouncer, pipeline, AsyncConnection.transaction, COMMIT-time deferred failure, or managed-command protocol trace was tested. P6's raw log was not available in the listed evidence; its retained ending summary was checked as a summary. No git history walk was performed to independently re-prove the internal “unchanged since 2023-05-30” date; current master/release equality was verified instead. The internal maintainer-activity/reply-speed narrative was not re-audited because it is outside the posted text.

**NOT CHECKED — search/policy limits.** Discussions search and public source-tree scans cannot establish absence across private policies, deleted/unindexed content, external organization websites, or all possible vocabulary. No authenticated search was used. The GitHub web-reader tool could not fetch #1453, but REST succeeded, so this did not prevent the current-state check. No rendering inside GitHub's logged-in issue composer was attempted; structure was inspected as Markdown/HTML source.
