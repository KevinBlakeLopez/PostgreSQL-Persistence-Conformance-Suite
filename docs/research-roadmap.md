# Research roadmap

Inspected 2026-10-21. Updated 2026-10-23 for M0 preservation and filing status. The order of later milestones is unchanged. This is the order of work. The mission and the boundaries are in [`research-master-plan.md`](research-master-plan.md). What is actually done is in [`research-status.md`](research-status.md).

A milestone in this file is not permission to start it. Start work only when the status document says that milestone is authorized, or when the maintainer assigns it.

## How dependencies work

A **dependency** is work that has to be finished before the next milestone can start. A **parallel activity** can proceed while that milestone is open, because it does not change the same evidence or the same decision.

## Milestone M0 — Preserve the production-reachability closeout

**Status.** Preserved on `main` at `36dd52f`. The runs, the `PR-01` catalog, the classifier, and the drafts are committed. See the status document. S1 and PI1 remain unfiled.

**Question already under study.** After an application catches a real PostgreSQL unique violation and lets a supported transaction API finish, what does the application observe, what did PostgreSQL commit, and can the connection be reused?

**Exit criteria.**

- Experimental results are reproducible from the preserved scripts, versions, and evidence.
- Versions are pinned or recorded on the run.
- An independent database outcome is preserved.
- Application-visible success signals are preserved.
- Connection reuse is recorded separately from the commit report.
- Savepoint recovery is preserved as a control.
- Standalone reproductions exist for the actionable findings.
- Upstream report status matches the tracker, and drafts are labeled as drafts.
- Remaining uncertainties are written down.

**Remaining constraints.**

- Leave case JSON and summaries unchanged. Do not rerun the suite in order to tidy it. The 2026-10-19 harness digest does not match `36dd52f`, because the classifier later gained category E. That is recorded in the status document.
- Do not add Drizzle, Prisma, Hibernate, or another SQLSTATE to this catalog. The study's own report excludes them. Later suite adapters are separate recordings. They are not PR-01 rows.
- Y2, P1, T3, and D1 are filed in the tracker. Do not file S1 or PI1 without approval of the exact text. Do not refile the Knex draft.

**Then.** PPCS maintenance. New suite scenarios need a separate question.

## Milestone M1 — Freeze the ownership-benchmark design

**Depends on.** M0's evidence remaining intact. The preservation commit is done. Upstream replies may still be open. M1 may not change PPCS results.

**Status.** The requirements documents in `docs/ownership-benchmark/` are the draft. They are not a frozen specification, and they are not authorization to implement the pilot.

**Exit criteria.**

- The research question, the scoring split, and the non-claims are accepted by the maintainer.
- The V1–V7 requirements are accepted, including which entity each stage adds and why.
- Acceptance tests are specified independently of any implementation.
- Agent configuration, repetition, randomization, human intervention, and cost fields are specified.
- The Python cohort and the decision to defer JVM, .NET, and a Node ownership cohort are accepted.
- The PPCS-derived transaction task is specified as three separate scores.

**Next action.** Maintainer review of those documents. Revise the draft if the review changes a requirement. Do not start application code during the review.

## Milestone M2 — Python pilot

**Depends on.** M1 frozen, and explicit approval to begin the benchmark program.

**Scope.** psycopg, SQLAlchemy Core, and SQLAlchemy ORM. One transition: V1 to V2 (evidence revision history). The pilot validates the method. It is not a ranking and it does not confirm or refute the Node ownership hypothesis.

**Exit criteria.**

- All three implementations have equivalent V1 behavior before the V2 change.
- Experiment isolation works. A run cannot edit the authoritative tests or see another architecture's solution.
- Evidence capture is reliable enough that a later reader can reproduce the scoring.
- Scoring rules are unambiguous, including the three transaction scores.
- Agent configuration is recorded.
- Results can be checked without trusting the agent's report.
- Cost of a trajectory is known well enough to decide whether V1–V7 repetitions are feasible.

A pilot result that is hard to interpret is a reason to change the method, not a reason to publish a ranking.

## Milestone M3 — Python longitudinal benchmark

**Depends on.** M2 exit criteria met, and a fresh approval if the pilot changed the scoring rules or the workload.

**Sequence.**

1. Freeze the benchmark specification at the pilot's accepted revision.
2. Implement the experiment harness.
3. Establish independently verified V1 implementations, and keep their construction-cost evidence.
4. Execute repeated V1–V7 trajectories from each previous version's actual code.
5. Preserve patches and execution artifacts.
6. Analyze correctness and maintenance cost.
7. Publish the methodology.
8. Publish results and limitations.
9. Name findings that need replication.

**Exit criteria.** A reader who was not present can tell what was required, what each architecture did, what it cost, what was correct, and what the sample cannot support. Cross-language expansion stays closed until this method is stable.

## Milestone M4 — Later expansion

Each item depends on M3, and each needs its own approval. They are not one milestone to start together.

| Item | Starts only when |
| --- | --- |
| JVM cohort (JDBC, Spring JDBC and/or jOOQ, Hibernate/JPA) | The Python method is stable, and the cohort is specified as applications rather than PPCS wrappers |
| .NET cohort (Npgsql, Dapper, EF Core) | The same condition. Not before the method is validated. |
| Django ORM cohort | The plan accounts for the surrounding Django framework |
| Node ownership cohort | A reason exists beyond filling out the eight-row hypothesis |
| Historical upgrade studies | The upgrade protocol from V7 is defined and the version gap is justified |
| GitHub repository mining | A protocol covers the biases listed in the master plan |
| Observatory application | The experiments need shared orchestration, historical analysis, or interactive reports that a CLI cannot provide |
| Another database inside PPCS | The written justification in the master plan is accepted |

## PPCS maintenance (parallel, bounded)

After M0, and also while M0's upstream items are waiting:

- Answer maintainers on issues that are already filed.
- Reproduce a regression they can point at.
- Test a proposed fix against the existing case, in a new run, and keep the old run.
- Refresh a compatibility recording when a pinned version changes, one dependency at a time, compared with `--expect` where the harness digest allows it.
- Correct documentation when the tracker or the evidence changes.

Maintenance does not add an adapter family, a database, or a fault category.

## What may proceed together

- Upstream correspondence on already-filed issues, while the benchmark specification is being reviewed.
- PPCS regression upkeep, while benchmark requirements are being edited.
- Reading the existing Spring and Hibernate material while the Python pilot is in design review. Reading is not implementing a JVM cohort.
- Documentation fixes that do not alter recorded experiments.
- SQLite and MySQL companion reports may be cited. They may not be merged into `harness/`.

## What waits

- Building the V1–V7 harness or the applications before M2 validates the method.
- Building the Observatory before the experiments need it.
- Adding adapters to enlarge a matrix that has no open question.
- Expanding PPCS to MySQL or SQLite while also changing the PostgreSQL evidence model.
- Several benchmark trajectories that use different models, prompts, or tools and are then compared as if they were one experiment.
- Filing the ready drafts, or opening a pull request, without approval of the exact text.
- Treating the Node ownership ranking as a result.

## Dependency sketch

```text
M0  preserve production-reachability evidence and filing status
    |
    +--> PPCS maintenance (ongoing, bounded)
    |
M1  freeze benchmark design  (drafting may overlap the end of M0)
    |
M2  Python pilot, V1 -> V2 only
    |
M3  repeated Python V1 -> V7 trajectories, then publication
    |
M4  JVM, .NET, Django, Node cohort, mining, Observatory, other databases
         each one approved separately
```

M4's branches do not depend on each other. Starting one does not authorize the others.
