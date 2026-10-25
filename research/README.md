# Research directory

Written by: Claude Opus 5.5 (low). Map as of 2026-10-25.

Investigations here sit outside the PPCS harness (`AGENTS.md` rule 11). None of them changes an adapter, the harness, a specification, a catalog or a recorded result. [`docs/research-status.md`](../docs/research-status.md) stays the inventory of what is done and what is uncommitted. This file only says what each folder is and where its upstream state is recorded.

## PostgreSQL studies

| Folder | Question | Upstream state |
| --- | --- | --- |
| [`production-reachability/`](production-reachability/) | Can ordinary application code observe a successful completion of a transaction PostgreSQL rolled back? | [`docs/upstream-submissions.md`](../docs/upstream-submissions.md) |
| [`transaction-outcome-propagation/`](transaction-outcome-propagation/) | Where a PostgreSQL transaction outcome is still visible, and which later layer drops or rewrites it | Nothing filed. `templates/upstream-issue.md` is a template, not a draft. |
| [`connection-pool-session-state/`](connection-pool-session-state/) | Can a pool hand a session to the next borrower while it keeps state its documented reset should have removed? | Nothing filed. Two drafts in `upstream-drafts/` await approval of their wording. |
| [`python-ecosystem-contribution-audit/`](python-ecosystem-contribution-audit/), with [`python-ecosystem-contribution-audit.md`](python-ecosystem-contribution-audit.md) | What PPCS already establishes about Django, SQLAlchemy, psycopg, asyncpg and Tortoise ORM, and what remains to contribute upstream | [`python-upstream-contribution-tracker.md`](python-upstream-contribution-tracker.md) |
| [`python-production-failure-gap-analysis/`](python-production-failure-gap-analysis/), with [`python-production-failure-gap-analysis.md`](python-production-failure-gap-analysis.md) | Python production persistence failures PPCS does not yet cover, and the probes behind the ranking | Same tracker |
| [`python-upstream-contribution/`](python-upstream-contribution/), with the [roadmap](python-upstream-contribution-roadmap.md) and [tracker](python-upstream-contribution-tracker.md) | Checks and drafts for individual Python upstream items | The tracker |

## Other databases

| Folder | Question |
| --- | --- |
| [`sqlite-phase0/`](sqlite-phase0/) | SQLite transaction semantics through Python's `sqlite3`, and where the PostgreSQL cases do and do not carry over |
| [`sqlite-transaction-state-divergence/`](sqlite-transaction-state-divergence/) | When SQLite ends a transaction by itself, do SQLAlchemy, Django and `sqlite3` notice, keep later work out of it, and avoid reporting success? Nothing filed; `upstream/` holds a SQLAlchemy facts package and a CPython draft |

The MySQL baseline and the Drizzle follow-ups are under [`investigations/`](../investigations/).

## Application lifecycle studies

These apply the PPCS method to servers and task queues. They are not database studies: Dramatiq is studied on Redis only.

| Folder | Question | Upstream state |
| --- | --- | --- |
| [`python-lifecycle-correctness/`](python-lifecycle-correctness/), brief [`python-lifecycle-investigation-prompt.md`](python-lifecycle-investigation-prompt.md) | Do Python servers report a clean shutdown while abandoning owned work or cutting off cleanup? | F1 posted as Kludex/uvicorn discussion #3232 (2026-10-25). Nothing else. |
| [`python-dramatiq-lifecycle/`](python-dramatiq-lifecycle/), brief [`python-dramatiq-investigation-prompt.md`](python-dramatiq-investigation-prompt.md) | Does Dramatiq acknowledge, strand or lose messages during worker and broker failures, against its documented guarantees? | Nothing posted. `upstream-opportunities.md` describes two reports. |
