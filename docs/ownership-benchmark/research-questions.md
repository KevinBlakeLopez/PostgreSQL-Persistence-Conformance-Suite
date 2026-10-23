# Ownership benchmark research questions

Status: draft for maintainer review. Not a result, and not authorization to implement. The mission and the approval gates are in [`../research-master-plan.md`](../research-master-plan.md). The method is in [`methodology-plan.md`](methodology-plan.md). The workload is in [`application-evolution-spec.md`](application-evolution-spec.md).

## Question

Under LLM-assisted test-driven development (LLMTDD), which persistence architecture minimizes the combined cost of implementation, verification, debugging, maintenance, upgrades, and correctness risk over an evolving application's lifetime?

The benchmark exists to answer that question empirically. It does not exist to confirm a preferred ranking.

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
- persistence-code complexity
- schema and migration design
- preservation of behavior already shipped
- transactional consistency when requirements change
- relationship and invariant changes
- concurrency and conflicting updates
- tenant-isolation mistakes
- query composition, SQL visibility, aggregation correctness, and escape hatches
- bulk lifecycle work, retention, and archival
- the cost of a real dependency upgrade
- correctness failures, including the PPCS-derived transaction task
- agent time, tokens, API cost where it is available, corrective iterations, and human time

Human help is recorded on its own line. Repairing one architecture and leaving another failed is a protocol violation, not a result.

## What a trajectory does not measure

- Raw database throughput, except where a reporting stage has an explicit performance requirement.
- A universal ranking of ORMs.
- Whether a framework's conformance failure means agents are worse at that framework. Those are different measurements. The methodology plan keeps them apart.
- Production incident rates.
- Ten-year cost from a single laboratory trajectory. The stages are a designed sample of ownership work, not a calendar decade.

## How PPCS fits

PPCS answers a correctness question about frameworks. This benchmark answers an ownership question about architectures under LLMTDD. One scored task is taken from PPCS's production-reachability pattern so that a false commit report can appear in the ownership record. That task is one component. It does not set the overall score.

Framework behavior, agent-written application behavior, the documented contract, the database outcome, and connection safety are separate fields. A known PPCS FAIL can show up because the agent used the framework as documented. That outcome is attributed to the framework contract unless the agent's code departed from the specified API.

## What would count as evidence

A useful result is a set of repeated trajectories, with frozen requirements, frozen tests, recorded agent configuration, and preserved patches, from which a reader can see:

- where the architectures differed in cost
- where they differed in correctness
- how large the differences were relative to the run-to-run spread
- which differences survived a change of stage
- which differences are exploratory

One trajectory is an anecdote. The pilot is a method check. Confirmatory claims wait until the repetition and analysis rules in the methodology plan are met.

## What remains a decision for the maintainer

- Whether this question is the next program after PPCS closeout.
- Whether the Python cohort is the right first sample.
- Whether V1–V7, as specified, are necessary and sufficient.
- The weight, if any, of each cost and correctness component. No weight is assigned in this draft, because a weight chosen to favor the hypothesis would decide the study in advance.
