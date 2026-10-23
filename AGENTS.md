# Agent operating instructions

These instructions apply to coding agents working in the PostgreSQL Persistence Conformance Suite repository. They sit alongside [`CONTRIBUTING.md`](CONTRIBUTING.md). Adapter changes follow `CONTRIBUTING.md` and `docs/protocol.md`. Research sequencing follows `docs/research-master-plan.md`, `docs/research-roadmap.md`, and `docs/research-status.md`.

If a task and these documents disagree about scope, the task wins only for what it explicitly assigns. A planning task does not authorize the implementation it describes. A documentation task does not authorize a commit, an upstream post, or a new experiment.

## Read first

Before editing, read:

1. `docs/research-status.md`, for what is actually done and what is uncommitted.
2. `docs/research-master-plan.md`, for the two programs and the approval gates.
3. The research or adapter document that covers the files you will touch.

`docs/research-status.md` is the inventory to update when a milestone changes. Do not copy a running status log into the master plan.

## Rules

### 1. Inspect before acting

Read the master plan and the relevant research documentation before starting work. Check `git status` before editing shared files. Uncommitted work may belong to another effort. Do not revert, reformat, or "finish" it unless the task says so.

### 2. Respect milestone boundaries

The roadmap describes future work. It is not permission to begin that work. A milestone can start when its dependencies are met and the task or the maintainer has authorized it.

### 3. Preserve evidence

Do not modify recorded experimental results to match an expected outcome. Case JSON, run summaries, companion evidence, and quoted logs stay as recorded. A documentation fix that corrects a status label is allowed. A documentation fix that rewrites a measurement is not.

### 4. Distinguish evidence from hypotheses

Label observed findings, interpretations, and untested assumptions as what they are. The ten-year ownership ranking is an unvalidated hypothesis. A harness PASS on family `PR-01` means the evidence is complete. It does not mean the framework reported the commit correctly. Drafts are not filings. Submitted pull requests are not merged fixes.

### 5. Avoid unnecessary expansion

Do not add adapters, frameworks, dependencies, databases, or services without a defined research question. Do not add a scenario to enlarge a matrix. Hibernate, Drizzle, Prisma, MySQL, and SQLite are not implied next steps.

### 6. Preserve reproducibility

Record exact versions, environment details, execution commands, and verification results when you run something. Prefer the repository's existing runner and disposable server. Do not point the suite at a database you care about.

### 7. Maintain independent verification

Do not treat a framework return value as the database outcome. Check PostgreSQL from the runner's observer or from another connection. For SQLite and MySQL companion runners, use the independent check those runners already record.

### 8. Separate correctness dimensions

Transaction reporting, lifecycle callbacks, the database outcome, connection reuse, application misuse, and framework-contract questions are separate. A later transaction committing does not show that the earlier one committed. A single pass/fail score is not a substitute for those fields.

### 9. Respect upstream approval boundaries

Do not file issues, submit pull requests, contact maintainers, or publish findings outside this repository without explicit approval of the exact content. Ready drafts in `research/production-reachability/upstream-drafts/` stay drafts until that approval. The Knex draft that restates knex#6547 must not be filed again. Do not open a second pgjdbc issue for the rollback command tag.

### 10. Avoid speculative implementation

If the assignment is a planning task, produce the planning artifacts. Do not implement the plan, build the benchmark, add the Observatory, or run a new study because the plan describes them.

### 11. Prefer minimal changes

Preserve existing architecture and conventions. The PostgreSQL harness is not a multi-database framework. Companion investigations under `investigations/` and `research/` stay outside `specifications/` and `harness/` unless an approved decision says otherwise.

### 12. Report uncertainty

Do not invent results, citations, issue statuses, version behavior, or experimental conclusions. If the tracker and a case file disagree, report both. If GitHub was not re-checked, say so. Runtime claims about third-party libraries need a recorded run, or they need to be labeled as source reading.

### 13. Avoid unnecessary Git operations

Do not commit, push, rebase, reset, or discard changes unless explicitly instructed. Do not stage `.pnpm-store/`, virtual environments, `__pycache__/`, or `.ppcs-instance.json`. Do not amend or force-push as part of an unrequested cleanup.

### 14. Check active work

Before editing shared files or starting a substantial workstream, inspect repository status and `docs/research-status.md`. The production-reachability study and the Hibernate adapter have lived as uncommitted work. Treat unexpected diffs as someone else's work until the status document or the task says otherwise.

## PPCS evidence conventions

Follow `docs/methodology.md` and `CONTRIBUTING.md`.

- Native mode is the framework's ordinary API. A mitigation is a separate hardened or configured mode.
- Do not change an invariant so that a framework passes.
- `UNSUPPORTED` is for a missing capability or a hazard that cannot arise by design. An unimplemented case is `NOT_RUN`.
- Category C and D faults are client-side. Do not describe them as production frequency or as network failures.
- A FAIL is a counterexample to a PPCS invariant under recorded conditions. Defect judgments belong to the framework's maintainers.

## Benchmark conventions

The ownership benchmark is Program B. Until the status document says the pilot is authorized:

- Do not create the application, the experiment harness, or acceptance-test code.
- Do not start a trajectory.
- Do not tune requirements so that a preferred architecture wins.
- Do not collapse the transaction task's three scores into one grade.

When a trajectory is authorized, agents under test do not edit the authoritative tests. Agents maintaining the harness do not edit recorded trajectories.

## Approval gates

Maintainer approval is required before filing upstream issues, submitting pull requests, publishing externally, starting the ownership-benchmark implementation, adding a database, adding a substantial adapter family, changing the evidence model, building the Observatory, expanding the benchmark to a new language, or destroying repository history or recorded evidence.

Approval of edits to the planning documents is not approval of those actions.
