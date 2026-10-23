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

## How PPCS fits

PPCS answers a correctness question about frameworks. This benchmark answers an ownership question about architectures under LLMTDD. One scored task is taken from PPCS's production-reachability pattern so that a false commit report can appear in the ownership record. It adds three correctness records beside the others. There is no overall score for it to set.

Framework behavior, agent-written application behavior, the documented contract, the database outcome, and connection safety are separate fields. A known PPCS FAIL can show up because the agent used the framework as documented. That outcome is attributed to the framework contract unless the agent's code departed from the specified API.

## What would count as evidence

A useful result is a set of repeated trajectories, with frozen requirements, frozen tests, recorded agent configuration, and preserved patches, from which a reader can see:

- where the architectures differed in cost
- where they differed in correctness
- how large the differences were relative to the run-to-run spread
- which differences survived a change of stage
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
- The Python cohort and the deferred cohorts are accepted with the adherence rule now in the methodology plan. One question in that rule is still open: ORM-arm adherence, below.

Later on 2026-10-23 the maintainer decided:

- The acceptance tests read the database through tables and columns the spec fixes. Implementations may add tables and columns, and the tests do not read those.
- The acceptance tests call a fixed Python service interface: named functions with defined result types, called in the test process. A later cohort in another language needs its own suite.
- The pilot runs the transaction task. V1 or V2 gains one uniqueness rule, fixed in the spec as a constraint the authoritative tests violate. The rule is chosen with the product rules.
- The authoritative suite asserts nothing in the transaction task's scripted scenarios. All of part A's signals are recorded, including what the operation told its caller. The product's own handling of the uniqueness rule is tested like any other feature.
- Audit is dropped. No later measurement needed it. Controls belong directly to an organization, and V5 reports per organization.

V1–V7 are necessary as a set of stages. As written they are not sufficient to freeze. They are not replaced or extended to cover the gaps. The acceptance tests and the transaction task are not ready either. The design stays unfrozen until the items below are written.

## Open before freeze

These are the maintainer's to write. The review did not fill them, and this draft does not either. Each is also marked where it applies.

1. **V5 fixture.** Row counts, what makes an N+1 load visible in the query log, and whether there is a performance bound.
2. **V7 comparability.** The from-version and to-version for each arm, what "similar significance" means, and whether the shared driver is inside the upgraded stack.
3. **The pilot's uniqueness rule.** Which rule V1 or V2 gains for the transaction task, chosen with the product rules. Also whether V3's decision constraint hosts a second instance of the task.
4. **The service interface and the assertions.** The interface's functions and result types, and the architecture-neutral assertions. That includes what "successful" and "failed" mean in the V1 invariants, and the V2 invariants. The kind of interface, and how the tests read the database, are decided above.
5. **V4's observation.** How a test sees another organization's rows cross the persistence boundary when the response is correct.
6. **Product rules.** Whether a user belongs to one organization, how many evidence items a control has, what approval means with zero reviewers, and which rows count as under review in V6.
7. **Migration tooling.** Whether a migration tool is part of an arm. psycopg has none, and Alembic is a separate project from SQLAlchemy Core and the ORM.
8. **ORM-arm adherence.** Whether, in the ORM arm, a Core construct or textual SQL used for an ordinary write is a recorded escape hatch or a departure.
9. **Unscored measures.** A definition of persistence-code complexity or of SQL visibility, if either is ever scored.
10. **The fixed tables and columns.** The tables and columns the tests read at each stage, V1 and V2 first. They depend on the pilot's uniqueness rule and the product rules.

The confirmatory repetition count, the prompt text, and the numeric execution caps wait for pilot approval. That deferral is part of the plan. It is not a gap in the design.
