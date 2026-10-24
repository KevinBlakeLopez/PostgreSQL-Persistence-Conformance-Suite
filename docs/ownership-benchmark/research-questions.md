# Ownership benchmark research questions

Status: draft, revised after the 2026-10-23 design review. Not frozen, not a result, and not authorization to implement. What the review decided and what is still open are at the end of this document. The mission and the approval gates are in [`../research-master-plan.md`](../research-master-plan.md). The method is in [`methodology-plan.md`](methodology-plan.md). The workload is in [`application-evolution-spec.md`](application-evolution-spec.md).

## Question

Under the methodology plan's protocol, which persistence architecture is lower on each recorded cost field, and which has fewer observed correctness failures on each recorded correctness field, across stages V1–V7?

In that protocol, the benchmark authors the acceptance tests. The agent may read them and must not modify, skip, or replace them. LLM-assisted test-driven development (LLMTDD) means that protocol in these documents.

The benchmark exists to answer that question empirically. It does not exist to confirm a preferred ranking.

### What the program's terms record

The program was first stated as the combined cost of implementation, verification, debugging, maintenance, upgrades, and correctness risk over an application's lifetime. Those terms name fields. They are not added together.

| Term | Recorded as |
| --- | --- |
| Implementation | The V1 cost record |
| Verification | The count of failing authoritative-suite runs |
| Debugging | Corrective iterations and human repair time, published as two numbers |
| Maintenance | The cost record of each later feature stage, V2–V6 |
| Upgrades | The V7 cost record |
| Correctness | Each correctness result, including the three parts of the transaction task |

Correctness risk is not a field. The study records observed failures. Production incident rates stay unmeasured. "Lifetime" means stages V1–V7, not a calendar period.

## Architectures

The comparison is among kinds of abstraction, not among every library that exists:

| Kind | What it adds | Initial Python technology |
| --- | --- | --- |
| Explicit SQL | A driver and SQL the application writes | psycopg |
| Query abstraction | Typed or compositional SQL without a unit-of-work lifecycle | SQLAlchemy Core |
| Full ORM | Identity map, unit of work, relationship management, and lifecycle events | SQLAlchemy ORM |

Later cohorts, each requiring its own approval, are described in the methodology plan. Django, JDBC, jOOQ, Hibernate, Npgsql, Dapper, Entity Framework Core, and the Node libraries already studied by PPCS are possible later members. They are not the first sample.

## Hypothesis

**UNVALIDATED RESEARCH HYPOTHESIS — NOT AN EMPIRICAL RESULT.**

Under LLMTDD, explicit SQL or a relatively thin query abstraction may reduce long-term ownership cost because less persistence behavior is hidden and fewer library-specific concepts have to be relearned at each change. A sophisticated ORM may cost less when relationships, in-memory state, and lifecycle rules carry the application.

The provisional Node.js ranking in the master plan is one statement of the thin-abstraction side of that hypothesis. It is primarily a Node.js comparison. It is not a universal ranking, it does not measure ten-year cost, it may overweight dependency stability, it may undervalue ORM productivity, and it does not measure coding agents or generalization to Python, the JVM, or .NET.

The benchmark must be able to reverse that ranking. A higher place in the table is not a target score. An architecture is not given an easier workload because the hypothesis expects it to win.

## What a trajectory measures

Each architecture receives the same requirements and evolves through the same stages, starting from its own previous implementation. The measured quantities are:

- initial implementation effort
- schema creation and migration
- preservation of behavior already shipped
- transactional consistency when requirements change
- relationship and invariant changes
- concurrency and conflicting updates
- tenant-isolation mistakes
- query composition, aggregation correctness, and escape hatches
- bulk lifecycle work, retention, and archival
- the cost of a real dependency upgrade
- correctness failures, including the PPCS-derived transaction task
- agent time, tokens, API cost where it is available, corrective iterations, and human time

Persistence-code complexity and SQL visibility are not scored fields. Neither has a defined observation. They stay off the scored fields until a later freeze defines one.

Schema design is not measured either. The spec fixes the tables and columns the acceptance tests read. Implementations may add tables and columns of their own.

Human help is recorded on its own line. Repairing one architecture and leaving another failed is a protocol violation, not a result.

## What a trajectory does not measure

- Raw database throughput, except where a reporting stage has an explicit performance requirement.
- A universal ranking of ORMs.
- Whether a framework's conformance failure means agents are worse at that framework. Those are different measurements. The methodology plan keeps them apart.
- Production incident rates.
- Ten-year cost from a single laboratory trajectory. The stages are a designed sample of ownership work, not a calendar decade.
- Results for any model or agent other than the one recorded. A different model is a different experiment.

## How PPCS fits

PPCS answers a correctness question about frameworks. This benchmark answers an ownership question about architectures under LLMTDD. One scored task is taken from PPCS's production-reachability pattern so that a false commit report can appear in the ownership record. It adds three correctness records beside the others. There is no overall score for it to set.

Framework behavior, agent-written application behavior, the documented contract, the database outcome, and connection safety are separate fields. A known PPCS FAIL can show up because the agent used the framework as documented. That outcome is attributed to the framework contract unless the agent's code departed from the specified API.

## What would count as evidence

A useful result is a set of repeated trajectories, with frozen requirements, frozen tests, recorded agent configuration, and preserved patches, from which a reader can see:

- where the architectures differed in cost
- where they differed in correctness
- how large the differences were relative to the run-to-run spread
- which differences survived a change of stage
- which differences persisted across models, where more than one model was run
- which differences are exploratory

One trajectory is an anecdote. The pilot is a method check. Confirmatory claims wait until the repetition and analysis rules in the methodology plan are met.

## Weights

No cost or correctness component has a weight. That covers agent time, tokens, API cost, corrective iterations, failing suite runs, human review time, human repair time, and the functional, invariant, concurrency, migration, outcome-reporting, connection-reuse, and savepoint-recovery results. There is no published total, no tie-break, and no utility function.

A weight chosen to favor the hypothesis would decide the study in advance. The master plan's Node order, from SQL plus node-postgres through Prisma, is not a prior and not a rubric. A result that reverses it is a successful experiment if the method is sound. A later pre-registration may define a combination only by a rule justified independently of that table.

Pre-registered confirmatory comparisons are differences on single fields, read against the run-to-run spread. Analyses added after seeing the data are exploratory.

## Decisions

The 2026-10-23 design review decided:

- This question is the next program after PPCS closeout. That does not approve the pilot. PPCS stays in maintenance.
- The Python cohort is the right first sample.
- No component has a weight, as stated above.
- The question, the scoring split, and the non-claims are accepted with the revision now in this document.
- The agent-configuration, repetition, randomization, human-intervention, and cost fields are accepted with the definitions now in the methodology plan.
- The Python cohort and the deferred cohorts are accepted with the adherence rule now in the methodology plan. The question it left open is decided below.

Later on 2026-10-23 the maintainer decided:

- The acceptance tests read the database through tables and columns the spec fixes. Implementations may add tables and columns, and the tests do not read those.
- The acceptance tests call a fixed Python service interface: named functions with defined result types, called in the test process. A later cohort in another language needs its own suite.
- The pilot runs the transaction task. V1 or V2 gains one uniqueness rule, fixed in the spec as a constraint the authoritative tests violate. The rule is chosen with the product rules.
- The authoritative suite asserts nothing in the transaction task's scripted scenarios. All of part A's signals are recorded, including what the operation told its caller. The product's own handling of the uniqueness rule is tested like any other feature.
- Audit is dropped. No later measurement needed it. Claims belong directly to an organization, and V5 reports per organization.
- The workload is a neutral claims-and-evidence review workflow. Claims replace GRC controls, and events replace audit events. It is shaped so that one implementation, forked after the study, can become a tool for this research program. The methodology plan holds the rules that keep that reuse out of the experiment.
- A claim can have several evidence items. Each carries an external reference unique within its claim, and that constraint is the pilot's uniqueness rule. V5 counts evidence items by the approval state of their current revision.
- A user belongs to one organization. V4's isolation is keyed to the user's organization.
- All three arms manage the schema with Alembic. Core and the ORM may autogenerate migrations from the tables they declare. The psycopg arm writes its migrations by hand in explicit SQL, and its application code never imports SQLAlchemy. Migration scripts are outside the adherence rule.
- All three arms and the service interface are synchronous. Async is a possible later variable, not part of the first comparison.
- Each arm uses its usual connection pool, with identical settings fixed by the spec.
- The adherence line sits at the Session. In the ORM arm, anything run through the Session against mapped classes is the assigned API. Core statements on plain tables or textual SQL through the Session are recorded escape hatches. Bypassing the Session is a departure. The Core arm follows the same line at its Connection.
- A revision has three approval states. It is approved when it has at least one assigned reviewer and all of them approved, rejected when any assigned reviewer rejected, and pending otherwise, including with no reviewers.
- In V6, a revision is under review while a reviewer counted for it has not decided on it, and events about it are kept with it. The current revision is never archived. Because V3 assigns reviewers to the evidence item, a replaced revision counts only reviewers assigned before it was replaced; otherwise one new assignment would keep an item's whole history from ever being archived (refined 2026-10-24, while writing the V6 contract).
- V4's tests watch the wire. A proxy between the application and PostgreSQL records the rows each query returns, and a test fails if a row of another organization reaches the application. A deliberately unscoped implementation is the proxy's control.
- V5's report runs against fixtures of 30 and 300 evidence items, each matched in a second organization. It must send the same number of statements for both, counted by the proxy. There is no time limit.
- V7 moves the whole persistence stack (psycopg, its pool, SQLAlchemy, and Alembic, wherever installed) across one 24-month calendar window. V1–V6 and the pilot pin the versions current at the window's start. V7 moves to the versions current at its end.
- The transaction task runs only on V1's external-reference rule. It is not repeated on V3's decision constraint. The cumulative tests re-run it at every later stage.
- Every table carries `organization_id`, kept equal to the claim's (and the author's) by composite foreign keys. Each architecture can then use its natural scoping tool: a condition on each query, or the ORM's automatic filter. PostgreSQL row-level security is not used, because it would enforce isolation the same way in every arm and erase the difference V4 measures.
- The V1 and V2 test contract is written in [`test-contract.md`](test-contract.md), reviewed on 2026-10-24. Revisions conflict on a stale base, the current revision is a pointer with a composite foreign key, identifiers are `bigint` identity columns, PostgreSQL sets the timestamps, the result types come from a benchmark-provided package, and atomicity is checked with a trigger the test arms.
- V6 marks archived revisions and events with an `archived_at` column. A revision is immutable in its content, author, and creation time; archival is the only change to a revision or an event. An event is archived only together with its revision.
- The V3–V7 sketch in `test-contract.md` is reviewed. V3 adds a `decision_recorded` event, a record of another organization reads as not found in V4, and the V5 report leaves archived rows out.
- The V3 contract is written and reviewed. Any user of the organization may assign reviewers, and an author may review their own item. A duplicate assignment fails with `CONFLICT`, a decision by an unassigned user fails with `NOT_FOUND`, and a decision may be recorded on any revision of the item.
- The V4 contract is written and reviewed. V4 adds `list_claims`. Organization B's rows get identifiers of at least 9,000,000,000 and a per-run token in every text value, and checks run in one direction only. In an organization-wide read, any of B's values crossing to the application fails. In a call that names a record, they are recorded per call, because loading the named record and checking its organization in code is a legitimate way to refuse it. The transaction probes are outside V4's checks.
- The V5 contract is written and reviewed. `report` returns the claims with current evidence, the evidence items in each approval state with all three states always present, and each item's latest event time. Each fixture is a fresh database built through the service, with claims that have no evidence. Expected values come from the fixture's plan and the test's own SQL. The proxy counts every statement of one `report` call, on a pool of one connection after a discarded first call.
- The V6 contract is written and reviewed. An event is archived together with its revision, whatever its own age, and never on its own. Any user of the organization may set the retention policy. `run_archival` runs in one transaction, archives nothing without a policy, and is an organization-wide read. Archived revisions read as not found for decisions and approval state, and revision views gain `archived_at`. The tests age rows by moving their timestamps back, with a 30-day policy and rows aged 60 days.

V1–V7 are necessary as a set of stages. As written they are not sufficient to freeze. They are not replaced or extended to cover the gaps. The acceptance tests and the transaction task are not ready either. The design stays unfrozen until the items below are written.

## Open before freeze

These remain before the design can be frozen. Each is also marked where it applies.

1. **The service interface and the assertions for V7.** V1 to V6 are written in [`test-contract.md`](test-contract.md), including what "successful" and "failed" mean, the V2 invariants, and the pool settings.
2. **Unscored measures.** A definition of persistence-code complexity or of SQL visibility, if either is ever scored.
3. **The fixed tables and columns for V7.** V1 to V6 are written in [`test-contract.md`](test-contract.md).

The confirmatory repetition count, the prompt text, and the numeric execution caps wait for pilot approval. That deferral is part of the plan. It is not a gap in the design.

Two decisions about models wait until the pilot has measured what a trajectory costs: whether the confirmatory run uses two models of different capability, and whether the frozen benchmark is re-run on later model generations. See "Models over time" in the methodology plan.
