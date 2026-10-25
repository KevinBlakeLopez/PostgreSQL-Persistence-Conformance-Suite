Research Assignment: Dramatiq Worker Lifecycle and Message Delivery Correctness

Role

You are a senior Python distributed-systems engineer investigating production-reachable correctness failures in Dramatiq’s message processing, acknowledgement, retry, and worker shutdown behavior.

Your objective is to determine whether Dramatiq violates documented message-delivery or lifecycle guarantees under realistic failure conditions.

This is an adversarial upstream contribution investigation.

You are not being asked to build a new framework, create a comprehensive conformance suite, or manufacture defects.

Find one consequential, independently reproducible correctness failure—or establish that the investigated guarantees hold.

1. Background

The investigator has developed two related bodies of research.

PostgreSQL Persistence Conformance Suite (PPCS)

PPCS investigates whether database frameworks accurately report transaction outcomes and safely manage connections after failures.

Its methodology emphasizes:

* Explicit correctness invariants.
* Production-reachable triggers.
* Independent observation of actual outcomes.
* Positive and negative controls.
* Repeatable experiments.
* Source-level root-cause analysis.
* Careful separation of confirmed defects from expected behavior.
* Minimal upstream corrections.

Python application lifecycle investigation

A subsequent investigation identified a Uvicorn shutdown-ordering problem.

When the graceful-shutdown timeout expires, Uvicorn cancels request tasks but can initiate application lifespan shutdown while those tasks and their connections remain active.

The investigation demonstrated the problem using an external witness, reproduced it on macOS and Linux, and evaluated both bounded and unbounded candidate fixes.

Apply the same investigative discipline to Dramatiq.

However, Dramatiq is a distributed message-processing system. Its guarantees differ from those of an HTTP server.

Do not assume that task completion, acknowledgement, broker delivery, and successful external side effects are equivalent.

2. Primary Research Question

Can Dramatiq acknowledge, abandon, lose, or incorrectly report the state of a message during realistic worker lifecycle failures in a way that contradicts its documented delivery guarantees?

Prioritize defects that could cause:

1. Permanent loss of recoverable work.
2. Premature acknowledgement of incomplete work.
3. Messages stranded in an unrecoverable broker state.
4. Incorrect retry or redelivery behavior.
5. Silent failure during worker shutdown.
6. Incorrect handling of acknowledgement failures.
7. Worker shutdown reporting success despite violating a documented message-lifecycle invariant.

A successful investigation should establish a specific mismatch between a promised guarantee and an independently observed outcome.

3. Time Budget

Target: six hours of active agent-assisted investigation.

This is a strict initial research budget.

Suggested allocation:

Phase	Budget
Documentation, source, and issue review	45 minutes
Candidate ranking and experiment selection	30 minutes
Minimal environment and external witness	60 minutes
Targeted experiments	120 minutes
Repetition, controls, and root-cause analysis	60 minutes
Final report and upstream assessment	45 minutes

Stop early if one high-impact defect is convincingly established.

If six hours elapse without a significant finding, produce the results and stop.

Do not expand into a broad testing framework.

4. Research Scope

Investigate the current stable Dramatiq release and its upstream default branch where feasible.

Start with one broker.

Prefer Redis for initial experiments if it is easier to provision safely.

However, first inspect the current Dramatiq documentation and implementation.

If RabbitMQ provides a clearer or more consequential acknowledgement invariant, select RabbitMQ instead and explain why.

Do not attempt a full Redis-versus-RabbitMQ comparison during the initial investigation.

Priority A: Graceful shutdown

Investigate worker behavior when SIGTERM arrives while:

* A message is executing.
* A message has been fetched but execution has not started.
* A message is completing.
* A message is being acknowledged.
* A message is being retried.
* A message’s external side effect has completed but its acknowledgement has not.

Determine what happens to every message in each scenario.

Priority B: Broker disconnection

Investigate broker connectivity failures:

* During message execution.
* Immediately before acknowledgement.
* During acknowledgement.
* Immediately after acknowledgement.
* During worker shutdown.
* During retry scheduling.

Distinguish broker-side acceptance from client-side knowledge of acceptance.

Priority C: Worker termination

Investigate:

* SIGTERM.
* A second termination signal.
* Forced process termination.
* Worker restart.
* Worker child-process termination, if applicable.

Do not classify unavoidable loss of in-process state after SIGKILL as a defect unless Dramatiq explicitly promises recovery of that state.

Priority D: Retry and acknowledgement interaction

Investigate whether:

* A failed task can be acknowledged without a durable retry.
* A retry can be scheduled but its original message incorrectly remains active.
* A message can disappear between retry publication and original acknowledgement.
* A failed acknowledgement can produce an incorrect terminal message state.

Account for the broker’s delivery semantics.

5. Candidate Failure Scenarios

Evaluate the following scenarios before writing experiments.

D1: Acknowledgement before completed processing

A worker receives a message.

The task begins executing.

The worker or broker experiences a realistic failure.

Determine whether the message is acknowledged despite the task not completing.

Potential invariant: A message configured for normal retry/redelivery must not be irrecoverably acknowledged before Dramatiq’s documented completion or failure-handling path has run.

Do not assume a task’s external side effect must succeed for the task to count as completed.

D2: Graceful shutdown strands prefetched messages

A worker has multiple messages in memory.

One is executing.

Others are prefetched but have not started.

SIGTERM initiates graceful shutdown.

Determine whether the prefetched messages are:

* Executed.
* Returned to the broker.
* Left pending for recovery.
* Permanently lost.
* Duplicated in a manner consistent with documented delivery semantics.

A shutdown log saying the worker stopped successfully is not sufficient evidence.

Verify broker state and subsequent redelivery.

D3: Acknowledgement outcome uncertainty

A worker finishes executing a message.

It sends an acknowledgement to the broker.

The connection fails before the worker receives confirmation.

Determine:

* Whether the broker accepted the acknowledgement.
* What Dramatiq believes happened.
* Whether the message can be redelivered.
* Whether a duplicate execution is expected.
* Whether Dramatiq reports an outcome more certain than the evidence permits.

This is conceptually similar to the uncertain COMMIT outcome investigated by PPCS.

Do not classify ordinary at-least-once redelivery as a defect.

The important question is whether Dramatiq makes an incorrect claim or mishandles recovery.

D4: Retry publication versus original acknowledgement

A task fails.

Dramatiq decides to retry it.

A failure occurs between creating the retry and acknowledging the original message.

Determine whether the system can enter a state where neither the original nor the retry is recoverable.

Inspect the exact ordering and durability of the relevant broker operations.

If this scenario is already documented or explicitly unsupported, record that.

D5: Shutdown interrupts cleanup

A task acquires an external resource.

Shutdown begins.

The task enters cleanup.

Determine whether Dramatiq:

* Waits for cleanup.
* Interrupts cleanup.
* Requeues the message.
* Acknowledges the message.
* Leaves the message recoverable.

The relevant invariant is not necessarily that cleanup always finishes.

The relevant invariant is whether Dramatiq’s behavior is consistent with its documented delivery and shutdown guarantees.

D6: Second termination signal

A worker receives SIGTERM while processing a message.

Before it finishes, another termination signal arrives.

Determine whether:

* The worker exits.
* The message remains recoverable.
* The broker eventually redelivers it.
* The message is incorrectly acknowledged.
* The worker hangs.

Check the documented meaning of repeated signals before classifying any result.

D7: Broker disconnect during shutdown

The worker begins graceful shutdown.

Dramatiq attempts to return unprocessed messages to the broker.

The broker connection is interrupted.

Determine whether the messages remain recoverable after the broker reconnects and a replacement worker starts.

This is particularly valuable if Dramatiq reports shutdown completion despite failing to restore recoverability.

6. Candidate Selection

Before implementing experiments, create a candidate matrix.

For each candidate, document:

Field	Description
ID	D1–D7
Broker	Redis or RabbitMQ
Dramatiq version	Exact version
Relevant API	Specific worker/broker implementation
Documented guarantee	Exact contract and source
Failure trigger	Realistic production event
Expected outcome	What should happen
Suspected outcome	What might happen
Severity	Potential consequence
Observability	How the outcome can be independently verified
Reproduction cost	Estimated effort
Existing issue	Whether already reported
Priority	Rank

Select the two or three most promising candidates.

Do not implement every scenario automatically.

7. Experimental Architecture

Build the smallest test environment that provides independent evidence.

Use three logically separate components:

Component A: Dramatiq worker

Runs the message-processing application.

May be terminated, restarted, or disconnected.

Its logs are useful but are not authoritative evidence of message completion.

Component B: Broker

Redis or RabbitMQ.

Use an isolated instance with a dedicated namespace, queue, or database.

The broker is the authoritative source for its own message state, subject to the broker’s documented recovery semantics.

Component C: External witness

Runs independently of the Dramatiq worker.

Records externally visible task effects.

Examples:

* A TCP server.
* A small HTTP service.
* An append-only SQLite database.
* An append-only event log.

Prefer an external witness that survives worker termination.

The witness should record:

* Message ID.
* Attempt ID.
* Worker process ID.
* Task-start event.
* Side-effect-start event.
* Side-effect-completion event.
* Cleanup-start event.
* Cleanup-completion event.
* Relevant timestamps.

Do not infer task completion solely from a log message written by the worker.

8. Evidence Requirements

For every experiment, collect:

1. Dramatiq version and commit.
2. Python version.
3. Broker version and configuration.
4. Operating system.
5. Worker command and options.
6. Message ID and attempt ID.
7. Exact failure trigger.
8. Worker exit status.
9. Worker logs.
10. External witness events.
11. Broker state before and after failure.
12. Whether a replacement worker receives the message.
13. Whether a retry occurs.
14. Whether the message is eventually acknowledged.
15. Whether the result is consistent with documented semantics.

Repeat meaningful experiments at least three times.

Increase repetition counts for timing-sensitive scenarios.

Use deterministic synchronization barriers rather than arbitrary sleeps whenever possible.

9. Fault Injection Rules

Prefer realistic failure triggers:

* SIGTERM.
* SIGINT, where supported.
* Worker child-process termination.
* Broker connection interruption.
* Broker restart.
* Worker restart.
* Network connection loss.

If precise fault injection is necessary, it is acceptable to introduce a controlled proxy or test-only instrumentation.

However:

* Label injected faults clearly.
* Do not present a synthetic exception as a production-reachable failure without demonstrating the real trigger.
* Preserve the original protocol behavior except at the intended fault boundary.
* Distinguish a lost broker reply from an operation the broker never received.
* Record whether the broker accepted the operation.

Do not introduce production code changes merely to make the failure reproducible.

10. Controls

Every potentially significant finding must have appropriate controls.

At minimum:

Positive control

Normal task execution and acknowledgement succeed.

Failure control

The worker terminates before completing the task.

Verify the documented recovery behavior.

Recovery control

A replacement worker starts.

Determine whether the message is redelivered or otherwise recoverable.

Configuration control

If the result depends on a Dramatiq option, compare the relevant documented configurations.

Do not compare fundamentally different delivery guarantees and call the difference a defect.

11. Important Semantic Distinctions

Keep these distinctions explicit throughout the investigation.

At-least-once delivery

Duplicate execution can be legitimate.

A duplicate is not automatically a bug.

At-most-once delivery

Some configurations or operations may explicitly trade recoverability for reduced duplication.

Do not impose stronger guarantees than documented.

Successful task execution

A Python function returning normally does not necessarily mean an external side effect completed durably.

Successful acknowledgement

A broker accepting an acknowledgement does not prove that every application side effect completed.

Lost acknowledgement reply

A worker not receiving confirmation does not prove that the broker rejected the acknowledgement.

Worker shutdown

A process exiting successfully does not necessarily guarantee every message was executed.

The relevant question is what Dramatiq actually promises about message recovery.

Broker durability

Dramatiq cannot guarantee recovery beyond the broker’s configured persistence and availability guarantees.

Distinguish Dramatiq defects from broker configuration limitations.

12. Adversarial Review

Before classifying a finding as a defect, answer:

1. Is the behavior documented?
2. Does Dramatiq actually promise the proposed invariant?
3. Is the selected broker configured correctly?
4. Is the behavior inherent to at-least-once delivery?
5. Did the worker acknowledge the message?
6. Did the broker durably accept that acknowledgement?
7. Could the message be recovered after restart?
8. Was the failure caused by the application?
9. Was the failure caused by the broker?
10. Was the failure caused by test instrumentation?
11. Is the scenario production-reachable?
12. Does it reproduce on the current stable release?
13. Does it reproduce on the current upstream default branch?
14. Is there already an upstream issue or PR?
15. Would the proposed fix introduce duplicates, hangs, or other regressions?

Do not promote a hypothesis to a confirmed defect until these questions have been addressed.

13. Finding Classifications

Use these classifications:

CONFIRMED DEFECT

A reproducible violation of a documented guarantee or clear implementation invariant, with an identified responsible component.

CONFIRMED BEHAVIOR, CONTRACT UNCERTAIN

The behavior is reproduced, but whether it violates the public contract requires maintainer clarification.

PRODUCTION RISK, APPLICATION RESPONSIBILITY

A dangerous scenario that the framework does not promise to prevent.

EXPECTED AT-LEAST-ONCE BEHAVIOR

Duplicate execution or redelivery consistent with the documented model.

EXPECTED BEHAVIOR

Other documented behavior.

ALREADY FIXED

Reproduces on an older version but not on the current upstream implementation.

DUPLICATE

Already reported upstream.

INCONCLUSIVE

Insufficient evidence to determine the outcome.

A genuine negative result is acceptable.

14. Source-Level Investigation

For every promising result:

1. Identify the responsible code path.
2. Trace the message lifecycle from receipt to acknowledgement.
3. Identify the precise ordering of broker operations.
4. Determine where shutdown and cancellation interact with that sequence.
5. Identify the public contract.
6. Compare current release and default branch.
7. Inspect existing tests.
8. Search existing issues and PRs.
9. Identify the smallest plausible correction.
10. Evaluate the correction against normal execution and failure recovery.

Do not propose a fix based solely on observed symptoms.

15. Fix Evaluation

If a confirmed defect is found, investigate a minimal correction.

A proposed fix must not:

* Introduce premature acknowledgement.
* Silently discard messages.
* Create an unbounded shutdown hang.
* Break ordinary retries.
* Prevent legitimate redelivery.
* Require stronger broker guarantees than Dramatiq documents.
* Change public semantics without acknowledging the compatibility implications.

Test the proposed correction against the original reproduction and relevant controls.

A working proof-of-concept is sufficient for the initial research phase.

Do not spend the entire budget polishing a PR.

16. Repository and Environment Safety

This investigation may run in a separate checkout or worktree associated with the existing PPCS repository.

However, it must remain independent of PPCS’s PostgreSQL transaction experiments.

Before changing anything:

1. Read AGENTS.md and applicable repository instructions.
2. Run git status.
3. Identify the active branch and existing worktrees.
4. Treat all pre-existing modifications as someone else’s work.
5. Use a dedicated research branch.
6. Use isolated Python environments.
7. Keep broker infrastructure separate from existing services.

Do not start, stop, restart, or modify unrelated containers or services.

If Docker or Colima is not already running, do not start it automatically if doing so could affect another project’s containers.

Use an isolated broker instance only when it can be provisioned safely.

Do not modify existing PPCS adapters, harnesses, specifications, or recorded results.

Do not overwrite research produced by other agents.

Do not commit, push, open issues, create PRs, or contact upstream maintainers without explicit authorization.

17. Research Deliverables

Create:

research/python-dramatiq-lifecycle/
    README.md
    candidate-matrix.md
    findings.md
    upstream-opportunities.md
    reproductions/
    outputs/

README.md

Document:

* Scope.
* Tested versions.
* Selected broker.
* Execution requirements.
* How to reproduce the experiments.
* Main findings.
* Limitations.

candidate-matrix.md

Document all considered scenarios.

Include rejected candidates and reasons for rejection.

findings.md

For each experiment:

* Hypothesis.
* Contract.
* Environment.
* Reproduction.
* Independent evidence.
* Broker-state evidence.
* Controls.
* Results.
* Root-cause analysis.
* Classification.
* Remaining uncertainty.

upstream-opportunities.md

Rank potential contributions by:

1. Production impact.
2. Confidence.
3. Reproducibility.
4. Fix feasibility.
5. Maintainer receptiveness.
6. Engineering effort.

reproductions/

Minimal executable test programs.

outputs/

Raw experimental output, including broker observations.

Preserve failed and inconclusive runs.

Do not report only successful reproductions.

18. Stop Conditions

Stop when:

1. One significant defect has been independently reproduced and its responsible code path identified.
2. Two credible lower-severity defects have been established.
3. Six hours of active investigation have elapsed.
4. Remaining candidates are documented limitations, already fixed, or insufficiently promising.

Do not expand to a second broker unless the first broker’s implementation makes the selected invariant impossible to test meaningfully.

Do not turn this into a general Dramatiq certification project.

19. Final Report

Provide:

Executive summary

Maximum 500 words.

Experiment results

ID	Scenario	Broker	Repetitions	Observed outcome	Classification

Most important finding

Explain:

* What happened.
* Why it matters.
* Which guarantee was violated.
* What independent evidence proves it.
* How realistic the trigger is.
* Which implementation is responsible.

Upstream assessment

Identify:

* Responsible repository.
* Current issue/PR status.
* Minimal proposed correction.
* Regression-test design.
* Compatibility concerns.
* Remaining verification.

Time accounting

Report:

* Active investigation time.
* Infrastructure setup time.
* Experimentation time.
* Verification time.
* Remaining estimated work.

Recommended next action

Choose exactly one:

* Prepare an upstream issue for human approval.
* Prepare a minimal PR for human approval.
* Perform one additional targeted experiment.
* Investigate another candidate.
* Stop because no significant defect was found.

20. Governing Principle

A message-processing system must not claim a stronger completion or delivery outcome than its evidence and documented guarantees support.

Distinguish:

* Task started from task completed.
* Task completed from side effect durably committed.
* Message delivered from message acknowledged.
* Acknowledgement sent from acknowledgement accepted.
* Broker accepted from worker received confirmation.
* Worker exited from all messages recovered.
* Retry scheduled from retry durably available.
* Message temporarily unavailable from message permanently lost.

Apply the same adversarial rigor used in PPCS and the Uvicorn lifecycle investigation.

Begin by reviewing current Dramatiq documentation, source code, existing tests, issues, and PRs. Produce the candidate matrix before implementing experiments.

Do not request approval for read-only research or isolated local experiments.

Stop for approval before making changes to shared infrastructure, committing or pushing research, or contacting upstream maintainers.
