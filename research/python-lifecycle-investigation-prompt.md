# Research Assignment: Python Application Shutdown and Task Lifecycle Correctness

## Role

You are a senior Python runtime, concurrency, and backend reliability engineer conducting an independent upstream contribution investigation.

Your objective is to identify production-reachable correctness defects in Python application shutdown, cancellation, and asynchronous task lifecycle management.

You are not being asked to build a new framework, implement speculative fixes, or create a large conformance suite.

You are being asked to discover whether widely used Python libraries violate important correctness guarantees under realistic operating conditions.

The investigation should be rigorous enough that a finding could support an upstream bug report or pull request.

## 1. Background

The investigator has already developed the PostgreSQL Persistence Conformance Suite (PPCS), which identified consequential transaction correctness failures across multiple programming languages and frameworks.

PPCS established an effective investigative methodology:

1. Identify an explicit or reasonably expected correctness invariant.
2. Find the component responsible for maintaining it.
3. Construct a minimal, reproducible failure scenario.
4. Establish independent evidence of the actual outcome.
5. Include positive and negative controls.
6. Repeat experiments to distinguish deterministic defects from timing artifacts.
7. Inspect the responsible implementation.
8. Distinguish documented behavior, genuine defects, unsupported patterns, and unavoidable uncertainty.
9. Check current releases, upstream branches, existing issues, and tests.
10. Propose the smallest defensible correction.

Apply this methodology to Python application shutdown and task lifecycle behavior.

Do not duplicate PPCS's database transaction investigations.

The focus here is asynchronous task ownership, cancellation, shutdown ordering, resource cleanup, and completion reporting.

## 2. Primary Research Question

Can a widely used Python application framework, server, or task execution library report successful shutdown or task completion while violating an important lifecycle guarantee?

Investigate failures such as:

- Tasks silently abandoned during shutdown.
- Background work lost without an observable failure.
- Graceful shutdown completing while owned tasks remain active.
- Tasks continuing to execute after their owning application has shut down.
- Resource cleanup skipped because cancellation interrupts a finally block.
- Task exceptions becoming unobservable during shutdown.
- Shutdown deadlines being ignored or incorrectly enforced.
- Task groups hanging indefinitely after cancellation.
- Shutdown hooks executing in an order that violates documented guarantees.
- Application startup or shutdown failures leaving resources partially initialized.
- Framework-managed background tasks being cancelled without the documented cleanup behavior.
- Task cancellation being interpreted as successful task completion.

Do not assume every undesirable outcome is a framework defect.

For example, a process killed with SIGKILL cannot guarantee completion of in-memory tasks. A client disconnect does not necessarily imply cancellation of server-side work.

The investigation must identify which component actually owns the guarantee.

## 3. Scope and Candidate Technologies

Prioritize the following:

### Tier 1: Application frameworks and ASGI lifecycle

- FastAPI
- Starlette
- Uvicorn
- Hypercorn

Investigate:

- ASGI lifespan startup and shutdown.
- Graceful shutdown behavior.
- In-flight requests.
- Framework-managed background tasks.
- Shutdown timeouts.
- Cancellation propagation.
- Exception visibility.

### Tier 2: Async concurrency infrastructure

- Python asyncio
- AnyIO
- Trio

Investigate:

- TaskGroup lifecycle.
- Cancellation scopes.
- Shielded cleanup.
- Nested cancellation.
- Exception propagation.
- Resource ownership.
- Task cancellation during context-manager exit.

### Tier 3: Background execution

Consider:

- ARQ
- Dramatiq
- Celery

Prioritize asyncio-native systems where possible.

Investigate worker shutdown, acknowledgement, retries, task completion state, and cancellation.

Do not attempt to cover every framework.

Choose the smallest number of subjects needed to establish a meaningful finding.

## 4. Time Budget

Target approximately 4–8 hours of active agent-assisted investigation for the initial phase.

This is a research time box, not permission to sacrifice rigor.

Suggested allocation:

| Phase | Target |
| --- | --- |
| Current-state research and candidate selection | 45–60 minutes |
| Source and contract analysis | 45–60 minutes |
| Minimal reproduction development | 90–150 minutes |
| Repetition, controls, and independent verification | 60–90 minutes |
| Upstream comparison and report | 45–60 minutes |

If a promising finding requires additional work, document the required follow-up rather than expanding indefinitely.

Do not create a comprehensive test harness during this phase.

## 5. Candidate Failure Scenarios

Investigate and rank the following scenarios before implementing experiments.

### S1: Graceful shutdown falsely reports completion

An application receives SIGTERM.

The server initiates graceful shutdown.

One or more application-owned tasks remain active, incomplete, or unobserved.

The server reports successful shutdown.

Questions:

- Does the framework promise to wait for these tasks?
- Are the tasks actually owned by the framework?
- Does the shutdown timeout change the contract?
- Are failures observable?
- Does the server terminate successfully despite incomplete work?

### S2: Background task loss during shutdown

A request schedules background work.

The HTTP response is sent.

Shutdown begins before the background work completes.

Determine whether the task:

- Completes.
- Is cancelled.
- Is abandoned.
- Is retried.
- Produces an observable failure.

A task that is documented as best-effort is not automatically defective when lost.

Prioritize contradictions between documented behavior and observed outcomes.

### S3: Cancellation interrupts cleanup

A coroutine acquires a resource:

```python
resource = await acquire_resource()
try:
    await perform_work(resource)
finally:
    await release_resource(resource)
```

Cancellation occurs during cleanup.

Investigate whether the resource is released.

Distinguish:

- Native asyncio cancellation.
- AnyIO cancellation scopes.
- Trio cancellation.
- Shielded and unshielded cleanup.
- Framework-owned and application-owned resources.

Do not report expected cancellation behavior as a defect.

Look for frameworks that promise cleanup but fail to implement the required shielding or lifecycle management.

### S4: Shutdown hangs indefinitely

A framework initiates graceful shutdown with a configured deadline.

A task ignores cancellation, enters an unexpected state, or waits on a resource.

Determine whether the framework:

- Enforces the deadline.
- Exits.
- Hangs indefinitely.
- Reports a timeout.
- Leaves resources active.

Test whether the behavior is specific to a particular task state.

### S5: Startup failure leaves resources active

Application startup initializes multiple resources.

A later initialization step fails.

Determine whether earlier resources are cleaned up.

Investigate nested lifespan context managers, task groups, and application startup hooks.

A particularly valuable defect would involve a framework claiming to manage startup/shutdown cleanup while failing to release an already-acquired resource.

### S6: Task exceptions disappear during shutdown

A background task raises an exception during shutdown.

Determine whether:

- The exception is propagated.
- The exception is logged.
- Shutdown reports failure.
- The task is marked successful.
- The exception is silently discarded.

Distinguish an application-created detached task from a framework-managed task.

### S7: Cancellation race with task completion

Cancellation arrives immediately before or after a task completes.

Determine whether the public API reports:

- Success.
- Cancellation.
- Failure.
- An unknown outcome.

Focus on cases where the framework makes a demonstrably false claim.

Do not confuse an uncertain external side effect with an incorrectly implemented task lifecycle.

## 6. Candidate Selection

Before writing experiments, create a short candidate matrix.

For each candidate, record:

| Field | Required information |
| --- | --- |
| Framework | Project and version |
| API | Specific lifecycle or shutdown API |
| Invariant | Exact documented or implementation-level guarantee |
| Trigger | Realistic production condition |
| Suspected failure | What could go wrong |
| Severity | Data loss, resource leak, false success, hang, etc. |
| Existing coverage | Relevant tests and upstream issues |
| Reproduction cost | Estimated effort |
| Ownership | Which project could fix it |
| Confidence | Evidence versus hypothesis |

Prioritize candidates using:

1. Severity.
2. Production reachability.
3. Clarity of the contract.
4. Independent observability.
5. Reproduction feasibility.
6. Upstream ownership.
7. Likelihood that the issue is not already known.

Do not prioritize novelty over severity, but do not rediscover already documented behavior and present it as a new defect.

Select the top two or three candidates for experiments.

## 7. Experimental Requirements

For every investigated candidate:

### A. Use current software

Identify:

- Latest stable release.
- Installed version.
- Relevant default-branch commit.
- Python version.
- Operating system.
- Async event-loop implementation.

Check whether the suspected defect already has a fix upstream.

### B. Establish the contract

Find the relevant:

- Public documentation.
- API docstring.
- Source implementation.
- Existing regression tests.
- Maintainer statements, where available.

Quote the smallest relevant passage.

If no explicit guarantee exists, classify the suspected invariant as an expectation rather than a documented contract.

### C. Use realistic triggers

Prefer:

- SIGTERM.
- Application shutdown.
- HTTP client disconnects.
- Task cancellation.
- Configured timeouts.
- Startup exceptions.
- Real resource cleanup.
- Concurrent requests.
- Normal background task scheduling.

Avoid artificial monkeypatching unless needed to isolate a specific mechanism.

If fault injection is necessary, label it explicitly.

### D. Establish independent evidence

Do not rely solely on the framework's own success or failure reporting.

Examples:

- A separate process observing whether a task completed.
- An append-only event log.
- A file descriptor or socket remaining open.
- A subprocess reporting its exit status.
- An external HTTP test client.
- A controlled synchronization barrier.
- A witness process that survives application shutdown.

Use synchronization barriers rather than arbitrary sleeps wherever possible.

### E. Repeat the experiment

Run each meaningful case at least three times.

Record:

- Exact command.
- Environment.
- Framework version.
- Exit status.
- Relevant logs.
- Observed task state.
- Independent witness result.
- Timing information.
- Whether the result was deterministic.

For timing-sensitive failures, three repetitions are only a minimum. Increase repetitions when needed.

### F. Include controls

At minimum:

1. A normal successful lifecycle.
2. The suspected failure scenario.
3. A corrected or explicitly protected variant, where feasible.

For example, compare unshielded cleanup against properly shielded cleanup.

A control must actually exercise the mechanism being investigated.

## 8. Adversarial Review

Before classifying anything as a defect, challenge it.

Ask:

1. Is the behavior explicitly documented?
2. Is the task actually owned by the framework?
3. Did the application misuse the API?
4. Does the configured shutdown timeout permit abandonment?
5. Is the observed result an unavoidable consequence of process termination?
6. Did the test itself introduce the failure?
7. Is the outcome externally observable?
8. Is the finding reproducible without relying on arbitrary scheduling luck?
9. Is the issue already reported?
10. Does the current default branch already fix it?
11. Would the proposed fix break legitimate behavior?
12. Does the suspected problem belong to Python, the concurrency library, the ASGI server, or the application?

Do not classify a behavior as a framework defect merely because a different framework handles it better.

## 9. Finding Classifications

Use these exact classifications:

**CONFIRMED DEFECT**

Reproducible behavior contradicts a documented guarantee or clear implementation invariant, and the responsible component is identified.

**CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN**

The behavior is reproducible, but whether it violates the public API contract requires maintainer clarification.

**PRODUCTION RISK, APPLICATION RESPONSIBILITY**

The scenario is dangerous but the framework does not promise to prevent it.

**EXPECTED BEHAVIOR**

The observed behavior is consistent with documented semantics.

**INCONCLUSIVE**

Evidence is insufficient, inconsistent, or dependent on uncontrolled timing.

**ALREADY FIXED**

The problem reproduces on an older release but not on the current default branch or available fixed release.

**DUPLICATE**

The same underlying defect is already tracked upstream.

Do not inflate the number of findings by reporting multiple manifestations of the same root cause as separate defects.

## 10. Upstream Contribution Assessment

For every confirmed or potentially confirmed defect, determine:

- Responsible upstream repository.
- Exact source location.
- Existing issue or pull request.
- Current maintainer activity.
- Contribution policy.
- Whether AI-generated issue text is permitted.
- Minimal correction.
- Required regression test.
- Compatibility risks.
- Whether an issue, discussion, or PR is the appropriate first step.

Do not file anything automatically.

Do not post comments or create pull requests.

Prepare an evidence package suitable for human review.

If the project requires human-authored submissions, respect that requirement.

## 11. Deliverables

Create a self-contained research directory:

```
research/python-lifecycle-correctness/
    README.md
    candidate-matrix.md
    findings.md
    upstream-opportunities.md
    reproductions/
    outputs/
```

### README.md

Explain:

- Research objective.
- Scope.
- Tested versions.
- Execution instructions.
- Evidence classification.
- Main conclusions.

### candidate-matrix.md

Include every candidate considered, including rejected candidates.

Record why each was selected or rejected.

### findings.md

For each experiment:

- Hypothesis.
- Contract.
- Setup.
- Reproduction.
- Independent evidence.
- Controls.
- Results.
- Source analysis.
- Adversarial review.
- Classification.

### upstream-opportunities.md

Rank genuine contribution opportunities by:

1. Severity.
2. Production reachability.
3. Confidence.
4. Fix feasibility.
5. Upstream receptiveness.
6. Expected impact per engineering hour.

For each opportunity, estimate the remaining effort to prepare an upstream-quality submission.

### reproductions/

Store minimal executable programs.

Prefer small standalone examples over a shared testing framework.

### outputs/

Store raw output from every meaningful experiment.

Do not overwrite evidence from previous runs.

## 12. Repository Safety

This research may be conducted inside the existing PPCS repository, but it must remain logically independent of PPCS's PostgreSQL experiments.

Do not:

- Modify existing PPCS adapters.
- Modify PPCS specifications.
- Change existing recorded results.
- Reconfigure the PPCS PostgreSQL container.
- Modify existing production-failure investigations.
- Introduce new dependencies into PPCS's primary environment.
- Rewrite existing research documents.
- Commit or push changes without explicit approval.
- Contact upstream maintainers without explicit approval.

Use isolated virtual environments and temporary infrastructure.

Inspect the repository's AGENTS.md and applicable local instructions before beginning.

If the repository contains uncommitted changes from another agent, leave them untouched.

## 13. Stop Conditions

Stop the initial investigation when any of the following occurs:

1. Two independently reproduced, potentially significant defects have been established.
2. One high-severity defect has been established with strong evidence and a clear upstream owner.
3. The time budget is exhausted.
4. The remaining candidates are already documented, fixed, or insufficiently promising.

Do not continue experimenting merely to produce more findings.

A rigorous negative result is acceptable.

If no significant defect is discovered, explain why and identify the most promising remaining hypothesis.

## 14. Final Report

At completion, provide:

### Executive summary

No more than 500 words.

### Findings table

| ID | Project | Failure | Severity | Evidence | Classification | Upstream status |
| --- | --- | --- | --- | --- | --- | --- |

### Most significant finding

Explain:

- What happens.
- Why it matters.
- How realistic the trigger is.
- Which guarantee is violated.
- What independent evidence proves the outcome.
- Which component owns the problem.

### Upstream opportunities

Rank the best one to three contributions.

### Engineering effort

Estimate:

- Time already spent.
- Time required for additional verification.
- Time required for a minimal fix.
- Time required for regression tests.
- Time required to prepare an upstream submission.

### Recommended next action

Choose exactly one:

- File an issue after human review.
- Prepare a minimal PR.
- Run one additional targeted experiment.
- Investigate a different candidate.
- Stop because no sufficiently significant defect was found.

## 15. Governing Principle

The objective is not to find bugs at any cost. It is to determine whether Python's application lifecycle infrastructure makes correctness guarantees that its implementations fail to uphold.

A finding is valuable only when its evidence, production relevance, and ownership survive adversarial scrutiny.

Do not confuse:

- Cancellation with rollback.
- Task cancellation with task termination.
- Request completion with background-work completion.
- Graceful shutdown with guaranteed delivery.
- Process termination with successful cleanup.
- An attempted operation with a completed operation.
- An uncertain outcome with a definite failure.

Apply the same discipline that made PPCS's findings meaningful.

Begin by reviewing current documentation, source code, upstream issues, and regression tests. Produce the candidate matrix before implementing experiments.

Do not ask for permission to perform read-only research or isolated local experiments. Stop for approval before changing shared repository infrastructure, committing changes, or making upstream submissions.
