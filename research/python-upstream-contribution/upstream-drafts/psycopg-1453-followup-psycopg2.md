# Draft: psycopg, follow-up on psycopg/psycopg#1453 (psycopg2)

**Dropped 2026-10-27. Do not post.** `dvarrazzo` replied and closed #1453 the same minute (state reason `completed`): https://github.com/psycopg/psycopg/issues/1453#issuecomment-6443758485 The check below said that a close as intended behaviour is recorded and not argued. The text under the rule is the comment that was not sent.

Prepared 2026-10-26. Written by: Claude Opus 5.5 (max).

This was the planned follow-up for tracker item PY-1b in [`../../python-upstream-contribution-tracker.md`](../../python-upstream-contribution-tracker.md). #1453 was filed by `KevinBlakeLopez` on 2026-10-21, and the PY-1b comment was posted on 2026-10-24 ([its draft](psycopg-1453-comment.md)). It reports CHK-9's result: psycopg2 behaves the same.

Everything between the two rules below is the comment that was not sent. The rest of this file is internal.

**When.** The roadmap (§14) allowed one polite follow-up only if the thread was still silent. It is not. Do not adapt this into a reply.

**Before posting:**

1. Get approval of the exact text and of the destination (`AGENTS.md` rule 9).
2. Re-check #1453. If a maintainer has replied, adapt this or drop it. If the issue was closed as intended behaviour, record that, and do not argue.
3. Re-check that psycopg2 2.9.13 is still the latest release. If not, re-run CHK-9's psycopg2 arms on the new one first.
4. Re-check psycopg2's tracker for a report of the same behaviour.

**Checks done 2026-10-26 (UTC).**

- psycopg2's tracker, searched for `commit rollback aborted` and `commit ROLLBACK command status`: no report of this. The nearest is psycopg2#1213 (2020): `tpc_prepare()` gets the same `ROLLBACK` tag for `PREPARE TRANSACTION`; its reporter closed it after noting that drivers for other languages do not handle it either.
- psycopg has none of `CONTRIBUTING.md`, `.github/CONTRIBUTING.md`, `docs/CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` or `.github/CODE_OF_CONDUCT.md`, and a code search for `LLM` returned nothing.

**Evidence.** [CHK-9](../chk-9-psycopg2-false-commit/README.md): arms `p2-raw-commit`, `p2-raw-with` and `p2-raw-sql-commit`, the SQLAlchemy arms, and the control. The comment links that folder instead of embedding a program.

**Deliberately left out:**

- CHK-10's asyncpg results: asyncpg is a different project (PY-2, asyncpg#1400).
- SQLAlchemy's asyncio engine on psycopg 3 (CHK-10 `pa-*`), which reaches `AsyncConnection.commit()`. It belongs to #1453, but it was observed only through SQLAlchemy. A direct `AsyncConnection` run would come first, if the maintainer asks about the async path.

**Length.** 15 lines, 166 words without the link.

---

psycopg2 does the same, in case that bears on the decision.

psycopg2 2.9.13 (psycopg2-binary, libpq 17.0.11), PostgreSQL 18.6, three repetitions, all the same:

- after a caught `UniqueViolation`, `conn.commit()` returned normally, and so did a `with conn:` block. `conn.info.transaction_status` was `TRANSACTION_STATUS_INERROR` just before the commit, and `TRANSACTION_STATUS_IDLE` after;
- `cursor.execute("COMMIT")` in the same situation left `cursor.statusmessage` as `ROLLBACK`;
- from a separate connection, `pg_xact_status()` of the transaction's ID was `aborted`, and the row inserted before the error was gone.

SQLAlchemy on psycopg2 passes this on. With SQLAlchemy 2.1.6, `Connection.commit()`, `engine.begin()`, `Session.commit()` and `sessionmaker.begin()` returned normally after the same caught error, and the ORM ran its `after_commit` hooks. A control without the failing insert committed. A failed ORM flush is the exception: SQLAlchemy raises `PendingRollbackError` and rolls back.

psycopg2#1213 (2020) describes the same `ROLLBACK` tag for `PREPARE TRANSACTION` in `tpc_prepare()`. Its reporter closed it without a change.

Program, outputs and server log: https://github.com/KevinBlakeLopez/PostgreSQL-Persistence-Conformance-Suite/tree/main/research/python-upstream-contribution/chk-9-psycopg2-false-commit

I haven't opened a psycopg2 issue. If you would rather track it there, I can.

---
