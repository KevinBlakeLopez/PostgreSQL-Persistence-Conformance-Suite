# Independent adversarial review of PY-3

Review date: 2026-10-24. Written by: GPT-6 (effort not exposed).

**Verdict: READY WITH CHANGES.** The lost retry write is reproducible. I found no critical or high-severity defect in CHK-5 or the proposed issue. The changes below make the issue meet its evidence-labeling rule and make its setup and comparison precise. They do not require changing the reproducer or its evidence blocks. This is a local review, not authorization to post.

The review date uses America/Los_Angeles; execution was on 2026-10-25 UTC. The runtime identifies this reviewer as GPT-6 but does not expose a reasoning-effort setting.

## Findings ranked by severity

### 1. Medium: explicitly label the source-only claims

**Label: source reading.** Draft line 395 combine observed counts with source analysis without saying which is which. The broad claim that nothing resets `_saved_in_db` on rollback is supported by source inspection, not by six observations of one model. The house rule explicitly asks for that distinction. The code citations themselves are correct.

Evidence: `tortoise/models.py:1180–1199`, `tortoise/backends/base/client.py:371–406`, `tortoise/backends/asyncpg/client.py:208–217`, `tortoise/backends/psycopg/client.py:269–279`, and `tortoise/signals.py:9` at develop `ad0d6ce2b878f6d5188374eabb61d80484aedfa4`. All rollback implementations and all occurrences of `_saved_in_db` were inspected. Refresh reads a row at `models.py:1255` and copies its fields at 1257–1258; it has no flag-reset hook. The signal enumeration has only save/delete signals. The same transaction/backend files are byte-identical at tag 1.1.9.

**Exact replacement for the source/count bullet in Additional context:**

> Source reading: `save()` takes the update path when `_saved_in_db` is true and `pk` is set, and ignores the return value of `execute_update()` ([models.py#L1186-L1192](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1186-L1192)). It then sets `_saved_in_db = True` ([models.py#L1198](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1198)); I found no built-in rollback path that resets it. `force_update=True` checks the count and raises when it is 0 ([models.py#L1180-L1183](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/models.py#L1180-L1183)). Observed in the wrapped runs: `execute_update()` returned 0 for every retry. The server plans showed each retry UPDATE matching 0 rows.

**Label: judgment.** This is an evidence-presentation correction; it does not weaken the demonstrated failure.

**Exact replacement for the environment bullet, to label the develop comparison too:**

> Observed: Tortoise ORM 1.1.9 with asyncpg 0.32.0, and with psycopg 3.3.6 (psycopg_pool 3.3.3), on PostgreSQL 18.6; Python 3.13.11 on macOS arm64. Three runs per backend gave the same result. I ran only the two PostgreSQL backends. Source reading: `Model.save()` is text-identical on develop `ad0d6ce2b878f6d5188374eabb61d80484aedfa4`.

### 2. Low: make the installation reproducible from either backend extra

**Label: observed.** Commands (each environment was created independently with `/opt/homebrew/bin/python3.13 -m venv`):

```sh
<asyncpg-venv>/bin/pip install --only-binary=:all: 'tortoise-orm[asyncpg]==1.1.9'
<psycopg-venv>/bin/pip install --only-binary=:all: 'tortoise-orm[psycopg]==1.1.9'
DATABASE_URL=<my-disposable-server-url> <venv>/bin/python -I tortoise_save_after_rollback.py <backend>
```

Recorded outcomes in `evidence/outputs/install-*.out`:

| Fresh installation | asyncpg command | psycopg command |
| --- | --- | --- |
| asyncpg extra only | exit 0 | exit 1: `ModuleNotFoundError: No module named 'psycopg'` |
| psycopg extra only | exit 1: `ModuleNotFoundError: No module named 'asyncpg'` | exit 1: `ModuleNotFoundError: No module named 'asyncpg'` |

Adding only `asyncpg==0.32.0` to the second environment made its psycopg command exit 0 (`psycopg-extra-plus-witness.out`). The psycopg extra already supplies psycopg-binary and psycopg-pool; there is no missing pool dependency in that extra. Asyncpg is also the script's admin and independent witness driver.

**Label: judgment.** The original sentence is literally accurate: it says asyncpg is needed, plus psycopg and psycopg_pool for the second command. This is a setup ambiguity, not a falsified dependency assertion. Neither backend extra alone runs both commands. The displayed database URL is a connection template; I substituted my authorized throwaway port and credentials rather than connecting to port 5432.

**Exact replacement for draft line 105:**

> Run it against a disposable server. `DATABASE_URL` must be able to create databases: the program first drops any database named `tortoise_save_after_rollback`, creates it, and drops it at the end. Install `tortoise-orm[asyncpg,psycopg]==1.1.9` in a fresh virtualenv; both commands need asyncpg for the admin and observer connections. Substitute that server's URL in the commands below.

### 3. Low: qualify the SQLAlchemy comparison

**Label: observed.** I reran `controls_django_sqlalchemy.py` once. All eight framework/arm combinations persisted one row and committed. Its SQLAlchemy output says:

```text
after the rollback: pk=1, transient=True, pending=False, persistent=False
the second Session committed normally, pk=1
rows with arm='retry': 1
```

**Label: source reading.** `controls_django_sqlalchemy.py:146–168` explicitly uses a new Session, `add(obj)`, and `flush()` for the second top-level attempt. Its nested arms also add the now-transient object again. The original P4 program does the same at `p45_commit_error_and_retry.py:181–193`. No `make_transient()` call is applied as a repair; rollback produces the observed transient state.

**Label: judgment.** This is a fair comparison of framework-native retries using the same Python object. Re-enlisting an object through SQLAlchemy's persistence API is necessary to ask it to persist. It is not an equivalent bare `save()` call, and the comparison does not establish a Tortoise contract. Django is the closer save-to-save counterpart.

**Exact replacement for the comparison bullet:**

> Django 6.1.2 persisted all four retry variants on the same server. SQLAlchemy 2.1.5 also persisted them when the same object was added again after rollback, using a new Session for each top-level attempt.

### 4. Low: describe #2293 as a proposal and date the #1212 caution

**Label: observed.** Read-only `gh api` responses show #2293 is open and unmerged, #1212 is open with zero comments, and develop is still `ad0d6ce2b878f6d5188374eabb61d80484aedfa4`. The search for PRs merged after 2026-10-25 01:30 UTC returned `"total_count":0`. Raw responses remain in the temporary directory's `github/` directory.

**Label: source reading.** [PR #2293's diff](https://github.com/tortoise/tortoise-orm/pull/2293/files), `tortoise/backends/base/client.py`, initializes a root callback frame, pushes a frame on nested entry, discards it on rollback, and merges it on release. The analogy to per-savepoint bookkeeping is fair. It is proposed callback bookkeeping, not an existing model-instance rollback facility. [#1212](https://github.com/tortoise/tortoise-orm/issues/1212) reports a zero count after fetching a MySQL instance on Tortoise 0.18.1/0.19.2. Its cause and applicability to current MySQL remain unverified. I did not run MySQL.

**Label: judgment.** Both references are useful constraints on a proposed fix. Avoid suggesting that the open PR has shipped or that #1212 proves current backend count semantics. Changing callback-list lifetime and tracking model objects have different identity, lifetime and memory considerations.

**Exact replacement for option 1:**

> Reset `_saved_in_db` for instances inserted in a transaction or savepoint when that scope rolls back. The savepoint arms require tracking by savepoint level, since the outer transaction still commits. Source reading: open PR #2293 proposes per-scope tracking for `on_commit()` callbacks.

**Exact replacement for option 2:**

> When a default-path UPDATE matches no row, raise as `force_update=True` does, or fall back to an INSERT as Django does. Source reading: `execute_update()` also returns 0 when it sends no statement ([executor.py#L489-L490](https://github.com/tortoise/tortoise-orm/blob/ad0d6ce2b878f6d5188374eabb61d80484aedfa4/tortoise/backends/base/executor.py#L489-L490)). #1212 reports a zero count for fetched MySQL rows on 0.18.1/0.19.2; I have not checked that on current MySQL.

### 5. Low, internal notes: narrow the negative test claim and clarify the force_update tests

**Label: source reading.** My independent AST inventory finds 1,969 test functions on develop and 1,916 on tag 1.1.9. It scans `pytest.raises`, `assertRaises`, `assertRaisesRegex`, `suppress`, and try/except. There are 22 directly transactional catch constructs in each revision. That number alone is not a complete call-graph analysis: `test_transaction_decorator_fail` calls an `@atomic()` helper, and `test_update_or_create_repeated_deletions_terminate` catches an exception from a helper that opens a transaction.

I read those helpers, the transaction-related test modules, root `conftest.py`, the PostgreSQL fixtures, and test cleanup utilities. Root `conftest.py:69–103` and PostgreSQL `conftest.py:52–72` roll back at teardown; they do not save the test's instance after teardown. I found no save/delete/refresh retry of the same inserted instance after a caught rollback. Reads of retained IDs do exist (`tests/test_transactions.py:110`, also an existing object at 329); “no test reuses an instance” is too broad if read literally. The race-winner deletion tests at `tests/test_concurrency.py:132–213` return a deleted instance through a helper, but `Model.update_or_create()` rereads a fresh instance at `models.py:1370–1383`; that is not a retry of the deleted instance.

`test_force_update_raise` sets `id=tournament_model.id + 100`; `test_noid_force_update_raise` sets `id=noid_model.id + 100`. They exercise an assigned primary key with no corresponding row, not an unset key. Develop lines are 539–542 and 851–854; tag lines are 511–514 and 823–826. The draft's develop line references are correct.

**Exact replacement for the internal test-absence bullet:**

> Source reading on develop `ad0d6ce2b`: I found no test that calls `save()`, `delete()`, or `refresh_from_db()` on the same inserted instance after its transaction or savepoint has rolled back. The inspection included exception contexts, transaction decorators, helpers and fixture teardown. Some tests read retained IDs after rollback.

**Exact replacement for the internal force_update bullet:**

> Source reading: `test_force_update_raise` and `test_noid_force_update_raise` (`tests/test_model_methods.py:539–542` and `851–854` on develop) set a primary key for which no row exists and expect `IntegrityError` from `save(force_update=True)`.

**Label: judgment.** Keep these claims internal. A static inspection should be described as what the reviewer found, rather than proof about every possible fixture/helper execution.

### 6. Low, CHK-5 wording: scope the plan-row and XID interpretation

**Label: observed.** My own parser, without running the author's `server_log_check.py`, produced:

```text
printed IDs 144 PSQL IDs 144 PSQL mismatches []
transaction-ending statement mismatches []
UPDATE child scan row/loop counts Counter({('0.00', '1'): 72})
fates Counter({'committed': 84, 'aborted': 60})
```

These are independent consistency checks of the preserved original evidence, not fresh queries to its removed server. My fresh server's psql result was `PSQL 102 transaction IDs; mismatches []`.

**Label: source reading.** PostgreSQL 18.6's [plan documentation](https://github.com/postgres/postgres/blob/REL_18_6/doc/src/sgml/perform.sgml#L1025-L1039) distinguishes the modification node from its input, and its [auto_explain documentation](https://github.com/postgres/postgres/blob/REL_18_6/doc/src/sgml/auto-explain.sgml#L85-L105) explains `log_analyze`. The child Index Scan with `actual rows=0.00 loops=1` validly counts matched tuples in this simple primary-key UPDATE. Reading the top Update node's zero output would be incorrect; an UPDATE without RETURNING can have that output even when rows change. Trigger suppression, concurrent rechecks, conflict handling and loop counts complicate generalization to other plans.

**Label: judgment.** The original CHK-5 interpretation is sound for these statements. Its wording about every INSERT's input being rows inserted is broader than necessary. Likewise, a zero XID at statement start is not evidence of the eventual outcome. Here the zero also appears in the post-execution plan log, before the explicit XID probe. That corroborates no heap-row update in this fixture. It is auxiliary evidence, not a substitute for plan rows, rowcount and witness visibility. Sequence allocation is another reason not to call it a universal detector of database side effects.

**Exact replacement for README independent-verification point 4:**

> **`auto_explain`, with `log_analyze`.** For these simple, trigger-free INSERTs and UPDATEs, the modification node's child reports the tuples supplied to it. The UPDATE child scans each report `actual rows=0.00 loops=1`, establishing zero matching rows in this fixture. Triggers, conflict handling and repeated loops require separate interpretation.

**Exact replacement for README's XID paragraph:**

> **One more server-side signal, for the plain retries.** In all 24 `retry` and `retry-changed` transactions, the log prefix's `xid` remained 0 in the post-execution `auto_explain` plan entry, before `pg_current_xact_id()` assigned an ID. For these trigger-free UPDATEs, that corroborates that no heap row was updated. A zero XID at statement start alone would not establish this. The savepoint arms and `force_update` had an ID assigned earlier, so this signal does not apply to them.

## Runtime and evidence checks that passed

**Label: observed.** `run.py reproduce` ran the unchanged program three times per backend, all exit 0. Each output comparison printed `MATCH recorded after masking IDs: True`. Only the numbers inside `pg_xact_status(...)` were masked; versions, platform, server version, primary keys, results and exception text matched unchanged. The script SHA-256 before/after is the README's `632ef90d3671d0c4ada653c9ee8c06795058cf5d81907db25836d967e9a154a3`.

The fresh logs show, on both backends:

| Arm | Retry SQL | Matched rows | Transaction fate | Witness rows |
| --- | --- | --- | --- | --- |
| retry, retry-changed | UPDATE by the rolled-back id; no INSERT | 0 | committed | 0 |
| savepoint, savepoint-changed | ROLLBACK TO, then UPDATE by that id | 0 | outer committed | 0 |
| control | INSERT | one input tuple | committed | 1 |
| force_update | UPDATE, then ROLLBACK | 0 | aborted | 0 |

The first attempts in the top-level retry and force_update arms aborted. Psycopg also releases the rolled-back savepoint. Each row above holds in all three required repetitions per backend. Full statements, parameters and plans are preserved in `evidence/server.full.log`; my own transaction-oriented reading is `evidence/independent-log-review.txt`.

I reran the optional wrapper once per backend: each printed five `[wrapped] execute_update() returned 0 to save()` lines. I reran the optional Django/SQLAlchemy controls once, not three times. I did not rerun the author's `server_log_check.py`.

Removing both XID assignment and fate probes retained all row-count, state and exception outcomes on both backends. A further asyncpg run used a one-connection pool and also omitted XID probes; its stdout was byte-identical to the no-XID default-pool run. These exploratory sensitivity runs are separate from the six unchanged reproductions.

**Label: observed.** `integrity.py` checked the README's 30 unique SHA-256 values:

- All 23 available evidence-file hashes match.
- All five installed Tortoise source files match their recorded hashes and tag 1.1.9 byte for byte.
- Docker's RepoDigests confirms the pinned PostgreSQL digest.
- The original full-server-log digest cannot be checked because that file was deliberately not retained. The retained extract has its own matching hash.

The three issue `<details>` blocks match exactly: script `632ef90d…`, stdout `b1db438a…`, log excerpt `c5a867dc…`. For the third block the exact construction is original lines 16–25, the displayed `…\n` separator, and original lines 39–50. All included log lines are byte-identical; the ellipsis is an intentional omission marker.

**Label: observed.** Inspection of the exact 26 file blobs written by commits `972e82a`, `d92490e`, and `4442ae2` found no credential values, tokens, or personal home paths. Automated path/token/credential checks printed `COMMITTED_BLOBS 26 SCAN_HITS []`; I also reviewed password/token references manually. They are placeholders, parameter names or descriptions. The machine-specific `/opt/homebrew/bin/python3.13` executable path occurs in `output/pip-freeze.txt:20`; it is expected environment provenance, not a personal home path. This audit concerns these three commits' files, not every historical file in PPCS.

## Source-link audit

**Label: source reading.** The two downloaded archives are develop at the exact requested SHA and tag 1.1.9. `Model.save()` is text-identical between them; the full models.py file differs. The executor, base client, transactions.py and both PostgreSQL clients are byte-identical.

| Claim / linked region | develop | tag 1.1.9 | Result |
| --- | --- | --- | --- |
| default update path ignores count | models.py 1186–1192 | 1182–1188 | exact |
| force_update checks zero / raises quoted error | models.py 1180–1183 | 1176–1179 | exact |
| saved flag assigned True | models.py 1198 | 1194 | exact |
| no effective fields returns 0 | base/executor.py 489–490 | same | exact |
| ordinary UPDATE sends all eligible fields, no dirty check | base/executor.py 460–505 | same | exact |
| asyncpg UPDATE command count | asyncpg/client.py 137–143 | same | exact |
| psycopg cursor count | psycopg/client.py 178 | same | exact |
| nested context uses rollback/release | base/client.py 388–406 | same | exact |

There is only one `def execute_update` implementation in the entire Tortoise package in each archive; no backend overrides it. A model with no eligible non-PK fields, generated-only fields, explicit empty `update_fields`, or only `DatabaseDefault` values can reach its early return. The issue's ordinary Item model has both arm and value, so neither changed-field nor unchanged-field retry can take that no-SQL path.

The flag's false assignments are in construction/clone/create paths (`models.py:750,950,999,1406` on develop), not in transaction cleanup. No backend transaction code refers to `_saved_in_db`. There is no built-in rollback signal or refresh hook that falsifies the draft's narrow source claim. Application-defined overrides and arbitrary user signals remain outside this claim.

## Upstream and policy audit

**Label: observed.** All upstream access used `gh` reads. Thirteen search API queries were paced three seconds apart, with unquoted terms and `per_page=100`; they returned 45 distinct items. Terms: `rollback save`, `rollback instance`, `saved_in_db`, `savepoint save`, `retry insert`, `save silently`, `zero rows`, `force_update rollback`, `save after rollback`, `is:pr rollback`, plus created/merged/updated checks after 2026-10-25 01:30 UTC. No search response was truncated by the 100-item limit. Query strings and responses remain in the temporary `github/` directory.

**Label: judgment.** No duplicate of the specific retained-instance / rolled-back INSERT / zero-row UPDATE mechanism was found. This is a finite search, not proof that none exists. I independently read the relevant returned bodies, including the vague #1501, the generated-only SQLite INSERT #2344, identity-map request #791, cancellation #1152, and reconnect #1793; those have different mechanisms or insufficient diagnostic detail.

**Label: source reading.** The four specifically requested characterizations hold:

- [#1212](https://github.com/tortoise/tortoise-orm/issues/1212): the fetched MySQL row/zero-count report described above; no comments or established current cause.
- [#2293](https://github.com/tortoise/tortoise-orm/pull/2293): open callback-frame proposal. The maintainer's review was an issue comment on October 5, not a submitted GitHub review; the author replied October 5 and followed up October 7. The internal notes' summary is substantively fair, though its “author replied on October 7” elides the earlier substantive reply.
- [#242](https://github.com/tortoise/tortoise-orm/issues/242): generated integer-PK constructor confusion; a collaborator suggested raising/warning for zero affected rows. Comments document a 0.15.0 constructor validation fix and the reporter closing the issue. No server trace establishes that issue's SQL mechanism. Keeping it out of the issue is reasonable.
- [#1094](https://github.com/tortoise/tortoise-orm/issues/1094): active-transaction pool reset warnings and reports of missing saves; no retained-instance rollback diagnosis was established. Do not treat it as the same finding.

**Label: observed.** The after-cutoff created, merged and updated searches each returned `"total_count":0`; develop commits since that cutoff returned `[]`. GitHub's latest-release response is tag `1.1.9`, published `2026-10-14T05:48:41Z`. This establishes GitHub state at my read times, subject to normal search-index delay.

**Label: source reading.** I inspected the archived repository's contribution guide, code of conduct, issue template and PR template, and searched repository Markdown/RST policy text for AI/LLM/generative/Copilot/ChatGPT references. No explicit AI policy was found. The organization `.github` repository metadata and tree reads both returned HTTP 404. That means it was unavailable to this authenticated client; it does not prove that no private organization policy exists. #2293's voluntary AI disclosure is not an organization policy.

## Sentence-by-sentence issue assessment

**Labels are explicit in the last column.** Line numbers refer to the reviewed draft. Headings and table labels make no independent factual claims.

| Draft text | Assessment | Label / evidence |
| --- | --- | --- |
| Title | Precisely describes the observed failure; retain it. “Lost write” need not appear. | judgment; six fresh runs |
| 88, first sentence: INSERT rolls back, pk and flag retained | supported for the tested model and exception path | observed; all six outputs |
| 88, retry UPDATE / zero match / normal return / commit / no write | all separately established; it is not a failed-commit finding | observed; plans, psql, witness |
| 88, field change does not help | value=2 retry has the same outcome | observed; changed arms |
| 90, savepoint behavior | rollback-to followed by zero-row UPDATE and outer commit | observed; both nested arms |
| 94, new instance per arm and independent observation | true; observer is independent of the subject transaction, though it uses asyncpg | source reading; script 57–138, 164–176 |
| 96–103, six-row results table | matches every fresh required run | observed |
| 105, database lifecycle and prerequisites | correct lifecycle; improve install specificity per finding 2 | source reading + observed |
| 108–109, commands | correct after installing dependencies and substituting a reachable authorized database URL | observed; install matrix and fresh runs |
| all three evidence blocks | exact sources as detailed above | observed; integrity.py |
| Expected behavior, first two sentences | legitimate requested behavior, not an already documented universal contract; context scopes it to these retries | judgment |
| Expected behavior, force_update sentence | exact in both backends | observed |
| environment / repetitions / backend scope | all reproduce; develop identity is source reading, not a runtime test of develop | observed + source reading |
| update-path / flag / no-reset / force_update explanation | accurate; add labels per finding 1 | source reading |
| wrapper and auto_explain sentence | original evidence and fresh wrapper/plans agree | observed |
| Django / SQLAlchemy comparison | result true; clarify re-add and Session boundary per finding 3 | observed + judgment |
| closing support question | gives maintainers a clear contract decision; retain | judgment |
| options 1 and 2 | reasonable directions, not demonstrated complete fixes; qualify references per finding 4 | judgment + source reading |
| conditional PR offer | appropriate, bounded to plain/savepoint regression tests | judgment |

**Label: judgment.** A maintainer can identify what to reproduce and what decision is requested. The issue is at the upper end of the house length target: 28 nonempty visible source lines and 601 words after removing details and link targets, approximately 58 lines at 100 columns. That is a heuristic, not a measured GitHub rendered height; viewport width changes wrapping. Long code, output and logs are correctly collapsed. There are no tangential PY-8/PY-19 findings. The approved asyncpg draft has the same essential structure: concrete reproduction, independent outcome, source explanation, compatibility question, conditional offer. Retain the title, expected-behavior question and conditional offer. The replacements above remain concise enough for this format.

## P4 comparison and limits

**Label: observed.** All three P45 recordings are byte-identical (SHA-256 `1e2aa3ce36c87560fb75f27a7d5e8550dcd77f266d7a4869a053e1dd28f6af65`); each reports Tortoise retry normal/0 rows, Django 1 row and SQLAlchemy 1 row. I read the original program and all three outputs; I did not execute that older combined P4/P5 probe.

**Label: source reading.** P4 uses asyncpg with `minsize=1&maxsize=1`, one text field and a shared database; it also exercises an unrelated earlier commit-time FK failure. CHK-5 uses defaults, two ordinary fields, a dedicated database, and explicit transaction-ID instrumentation. Both use the same instance after a caught AppError. Different pool size does not repair that instance's flag. My no-XID one-connection sensitivity run supports that distinction directly.

**Label: judgment.** XID capture changes transaction-ID allocation and therefore observability; it can make an otherwise XID-less no-op transaction have a durable status entry. It does not repair the instance or change the row result in the tested sensitivity arms. The fresh no-XID runs support that claim; they do not establish general absence of instrumentation effects under concurrency.

## What I could not check

- **Observed limitation:** the original full server log is absent, so its hash, omitted non-subject sessions and historical container removal cannot be independently recovered. Its preserved subject extract, psql result and file hashes agree, and my own full log is retained.
- **Observed limitation:** the organization `.github` repository returns 404; any inaccessible policy remains unknown.
- **Judgment / scope:** duplicate absence is bounded by the searches performed and search-index freshness. I did not reproduce every one of the author's 28 queries.
- **Scope:** no Tortoise test suite, non-PostgreSQL backend, concurrent writers, alternate primary-key type, atomic-decorator runtime, update_fields/bulk APIs or patch implementation was run. Develop behavior was source-checked against the installed release, not installed and executed separately.
- **Scope:** the optional controls and wrapper were rerun once per relevant program/backend, not with the author's three repetitions. The six required unchanged reproductions were all performed.
- **Observed limitation:** no browser-rendered GitHub length measurement was taken. The stated line count is the documented wrapping approximation.

No tracked file was edited, staged or committed, and nothing was posted, commented, reacted to or otherwise written upstream. The only repository additions are this new review directory and its contents. My throwaway container was removed; see FRESH-RUN.md. Complete created-path inventory: CREATED-PATHS.txt.

**Observed execution-constraint deviation:** pip’s default shared cache was enabled during the escalated installations. It created two virtualenv-specific self-check files and refreshed shared metadata outside the requested write roots. `CACHE-SIDE-EFFECTS.md` records the exact paths and attribution limits. Shared cache entries were left intact to protect other sessions.
