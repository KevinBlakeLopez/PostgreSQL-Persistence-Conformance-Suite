# Final report: Dramatiq worker lifecycle and message delivery

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

**Revised 2026-10-25** after an adversarial verification in which the investigator tried to falsify its own findings: [adversarial-verification.md](adversarial-verification.md).

Nothing was filed, posted, committed or pushed. Evidence:
- the original study: [findings.md](findings.md), [outputs/SUMMARY.md](outputs/SUMMARY.md);
- the verification: [outputs/verify/SUMMARY.md](outputs/verify/SUMMARY.md).

## Executive summary

**All four findings survived the adversarial review. F1 was narrowed, F2 was qualified, and one fix turned out to introduce duplicates.**

**F1: a failed message can be deleted, on the Redis broker.**
- **Where:** Dramatiq 2.2.1 and `master` (`08d711a`).
- **When:** the actor fails, and the `Retries` middleware's enqueue of the retry fails *before reaching Redis* (refused or reset connection).
- **What happens:**
  - `Broker.emit_after` logs the error at CRITICAL and continues.
  - The worker acknowledges the original once Redis is back, deleting it.
  - There is no retry and no dead letter.
- **Counts:** 21/21 runs on macOS and Linux; a `dramatiq.Retry` exception and the last retry too.
- **The narrowing:**
  - When Redis accepted the enqueue and only the reply was lost, nothing was lost. The retry ran (3/3), though Dramatiq still logged the CRITICAL failure; with redis-py's default client retries it ran twice (3/3).
  - When only the original's ack failed, nothing was lost either (3/3).
- **Contract:** this contradicts the documented retry and dead-letter behavior.
- **Prior trace:** never filed as an issue; it appears only in comments on a closed PR (#545).

**F2: delayed messages are stranded after a reconnect.**
- **What happens:** after a Redis connection error, delayed messages a live worker had fetched, scheduled retries included, are dropped from its memory and left in its Redis ack set.
- **Observed both ways:** Redis's MONITOR log and the worker's own state agree.
- **How long:** they stay stranded while that worker lives and keeps heartbeating. A second live worker with Dramatiq's default settings did not recover them (3/3).
- **When they are recovered anyway:** if another worker's maintenance, with a heartbeat timeout shorter than the outage, wins a race against the owner (1/3 with a 2 s timeout), or if the owner stops heartbeating.
- **Prior trace:** #527 reported the symptom in 2023, and was closed with an explanation the runs contradict.

**F3: the delay-queue consumer thread dies.** A Redis stall or partition longer than two socket timeouts kills it, under a network blackhole too (3/3). One stall killed both workers' consumers. The open PR #895 removes the death but leaves the messages stranded as in F2.

**F4: shutdown aborts or hangs.** When Redis is unavailable at the shutdown requeue, `Worker.stop()` aborts past its documented warning branch. The worker exits 1, or never exits with the AsyncIO middleware. This needed no special harness, and happened with either Redis error type. No message is lost.

**Fixes:**
- **F1:** dead-lettering (a1) is the safe minimal correction. Retrying the enqueue (a2) duplicated retries after lost replies and changed what `actor.send()` raises.
- **F2-F4:** the bundled Redis fix runs a delayed message twice when another worker recovers it while the owner still holds it (2/2). It needs ownership-checked promotion first.
- **Tests:** regression tests built on Dramatiq's own fixtures fail on `master` and pass with each intended fix.

**Decision:** ready for upstream discussion, as two reports (F1; and F2-F4), written by the user with AI assistance disclosed.

## Experiment results

Unpatched Dramatiq 2.2.1 and `master` `08d711a`. The original study made 129 recorded runs (108 macOS, 21 Linux); the verification added more under `outputs/verify/`.

| ID | Scenario | Broker | Repetitions | Observed outcome | Classification |
| --- | --- | --- | --- | --- | --- |
| F1 (D4) | Actor fails; the retry enqueue never reaches Redis (refused) | Redis | 21 fault, 11 control | Original acked and deleted 21/21. `max_retries=0` dead-letters it (3/3); SIGKILL before the ack keeps it (3/3); no fault, normal retry (5/5). | CONFIRMED DEFECT (narrowed) |
| F1 verification | Redis accepts the enqueue, reply lost | Redis | 3 URL form + 3 host form | Not lost. URL form: the retry ran once (3/3), with a misleading CRITICAL log. Host form: redis-py re-sent the call, so the retry ran twice (3/3). | Narrows F1 |
| F1 verification | Retry enqueued, then the original's ack fails | Redis | 3 + 3 | Not lost. Once (3/3); twice if the worker is killed (3/3). | EXPECTED AT-LEAST-ONCE BEHAVIOR |
| F1 verification | `Retry` exception; last retry; exhausted; `throws` | Redis | 3; 3; 1; 1 | Lost (3/3); lost (3/3); dead-lettered; dead-lettered | Scope of F1 |
| F2 (N1) | Redis restarted while a live worker holds delayed messages | Redis | 14 fault, 6 control; verification below | Stranded 14/14 until the worker exited | CONFIRMED DEFECT (qualified) |
| F2 verification | A second live worker on the default 60 s timeout; with a 2 s timeout; owner SIGSTOPped | Redis | 3; 3; 2 | Not recovered (3/3); recovered when the other worker won the race (1/3); recovered (2/2) | Qualifies F2 |
| F3 (N2) | 15 s write pause, or a network blackhole, while the delay-queue consumer holds messages | Redis | 11 pause + 3 blackhole; 3 control | Thread died 14/14; no death with a 7 s pause (3/3). With two workers, one pause killed both delay-queue consumers (3/3). | CONFIRMED DEFECT |
| F4 (D7) | Redis unavailable at the shutdown requeue | Redis | 15 + 11 verification; 6 control | Exit 1, or a hang with AsyncIO, with or without the harness barrier, with a refused connection or a `TimeoutError`, with AsyncIO first or last. Messages recovered in every run. | CONFIRMED DEFECT (lower severity) |
| D2 | Graceful shutdown with a prefetched message | Redis | 6 | Requeued, exit 0 | EXPECTED BEHAVIOR |
| D3 | Ack outcome uncertainty | Redis | not run | Source reading: idempotent ack retries; `TimeoutError` not retried | DUPLICATE (#894) for the timeout case |
| D6 | Second termination signal | Redis | not run | Tracker and source | DUPLICATE (#899) |
| D1, D5 | See the candidate matrix | - | not run | No lead (D1); documented and configuration-dependent (D5) | Not assessed at runtime |

Candidate fixes, challenged:

| Fix | What it fixes (observed) | What it breaks (observed) | Readiness |
| --- | --- | --- | --- |
| `fix-d4-a1`: dead-letter on a failed retry enqueue | F1, 7/7; recoverable even when the nack fails and the worker dies (3/3) | It changes the outcome for a message with retries left, during an outage, to dead-lettered | Ready for a patch discussion |
| `fix-d4-a2`: retry the enqueue | F1, 7/7; bounded by the shutdown timeout (3/3) | The retry ran twice after a lost reply (3/3, against once unpatched); `actor.send()` raises `ConnectionClosed` instead of `redis.ConnectionError`; threads block for the outage | Not ready |
| `fix-redis-reconnect` | F2 (4/4), F3 (4/4), F4 (7/7) | Each delayed message ran twice when another worker recovered it while the owner held it (2/2, against once unpatched) | Not ready: it needs ownership-checked promotion |
| `fix-redis-requeue-mapping` (Part 1 alone: map `requeue` errors, 4 lines) | F4: exit 0 with the documented warning, no AsyncIO hang (1/1 each). F3: no thread death; later delayed jobs run (3/3). | Nothing new. It leaves the held messages stranded as in F2 (3/3), and adds no duplicates. | **Ready for a patch discussion** as an incremental fix |

Regression tests (`reproductions/regression-tests/`, Dramatiq's fixtures, Linux): all four fail on `master` and pass with their intended fix; all three negative controls pass on every tree, including the two fix combinations.

Dramatiq's own suite, minus benchmarks, with a 60 s per-test timeout:
- **`master`:** 5 environment-related failures.
- **The fixes and combinations:** no new failure attributable to them.
- **One timing assertion** failed once on the a1 tree. It passed in 10/10 isolated runs on both `master` and a1, and a1 does not touch that path.

## Most important finding: F1

- **What happened.**
  1. Attempt 0 of a message with retries left raised while Redis was refusing connections.
  2. `Retries` logged "Retrying message … in N milliseconds" and called `broker.enqueue`, which raised `redis.ConnectionError`.
  3. `Broker.emit_after` logged that at CRITICAL and continued.
  4. The worker's `finally` block acknowledged the original. The ack is retried every 5 s, so it succeeded once Redis was back, and the payload was deleted.
- **Why it matters.**
  - Work configured for automatic retries disappears with no automatic recovery.
  - The broker keeps no copy. The worker's ERROR line for the failure names the actor and its arguments, so manual reconstruction from logs is possible where logs are kept.
  - Every prefetched message that fails while Redis refuses connections is affected.
- **Which guarantee is violated.** "Dramatiq automatically retries failures with exponential backoff", with dead-lettering only after "a message has exceeded its retry or age limits" (`docs/source/guide.rst:217-218`, `267-268`). "Messages are only ever acknowledged … after they have been successfully processed" (`advanced.rst:174-175`) supports this, but loosely.
- **Independent evidence.**
  - Redis snapshots: the payload is deleted, and the DQ, XQ and ack sets are empty.
  - **MONITOR** shows Redis never received the retry enqueue, then executed the ack.
  - The external witness: one attempt only.
  - A replacement worker, with maintenance on every call, receives nothing.
  - A further Redis restart from the append-only file brings nothing back.
  - Controls: as above.
- **How realistic the trigger is.**
  - A failing actor coincides with Redis refusing or resetting connections at the retry enqueue: a restart, a failover, or a network drop. The outage must outlast about 3 s of client retries with `RedisBroker(host=...)`; any blip suffices with `url=`.
  - The coincidence is likely when the outage causes the actor's failure (`fault-actor-redis`).
  - A lost reply is not enough: then the retry exists.
- **Responsible implementation.**
  - `middleware/retries.py:147-148`;
  - `brokers/redis.py:184` (an unmapped error);
  - `broker.py:121-127` (`emit_after` swallows);
  - `worker.py:600-607` and `409-419` (ack unless `message.failed`).
- **Broker scope.** Redis. On RabbitMQ, source reading suggests a broker outage would redeliver the original instead; not run.

## Upstream assessment

- **Responsible repository:** `Bogdanp/dramatiq`.
- **Current status** (GitHub API, 2026-10-24; `master` still `08d711a` on 2026-10-25):
  - F1: no issue; comments on closed PR #545.
  - F2: #527, closed 2023.
  - F3: #894 / PR #895, open and unreviewed.
  - F4: #899 / PR #900, open; #911 restates #899.
- **Two reports, not four.** F2-F4 share two root causes:
  - the delay-queue reset, which assumes RabbitMQ semantics;
  - the unmapped `_RedisConsumer.requeue` errors.

  F1 is separate.
- **Minimal corrections:**
  - **F1:** a1 (dead-letter) is the safer choice. a2 is an alternative the maintainers can weigh against its observed duplicates and API change.
  - **F2:** retention plus an ownership-checked promotion, as PR #859 proposed for #431.
  - **F3 and F4:** the `requeue` mapping alone (Part 1), which is safe on its own.
- **Regression tests.** They are ready, use controlled exception injection on Dramatiq's own fixtures, and fail and pass as required. The integration reproductions are kept.
- **Compatibility:**
  - a1 changes such messages' terminal state;
  - a2 changes `actor.send()`'s exception type;
  - the reconnect fix adds a consumer attribute, with a default that keeps today's behavior for RabbitMQ and third-party brokers;
  - the F4 change alters the exit code after a failed shutdown requeue, from 1 to 0, which is a policy choice for the maintainers.
- **Contribution policy.** Bug reports are welcome. PRs need a prior discussion, must be human-authored, and must not list AI tools as authors.
  - Any report should be written and posted by the user, with AI assistance in the investigation stated plainly.
  - A PR should come only from someone who can claim full authorship.
- **Remaining verification (not done):**
  - RabbitMQ;
  - the `Callbacks`/`Pipelines` variants of F1;
  - F3 with the host-form broker and a stall over 110 s;
  - real Sentinel or managed-Redis failover;
  - an ownership-checked promotion implementation.

## Time accounting

Wall-clock, PDT. Phases overlap, because batches ran unattended.

| Session | What | When | Minutes |
| --- | --- | --- | --- |
| Original study, 2026-10-24 | Review, matrix, harness, experiments, fixes, Linux, report | 19:06-20:25 | about 80 of the 360 budgeted |
| Adversarial verification, 2026-10-24 | Fault proxy, MONITOR observer, in-worker state reporter, about 60 verification runs, a regression-test module on 7 source trees, revised documents. Started at 1% battery. | 21:21-22:25 | about 65 wall-clock, much of it unattended batches |

**Remaining estimated work**, not started, each needing the user's go-ahead:

| Task | Estimate |
| --- | --- |
| Report A (F1), written by the user | 30-60 min |
| Report B (F2-F4), written by the user | 45-90 min |
| An ownership-checked promotion prototype, if the maintainers want one | 1-2 h |
| RabbitMQ check of F1 | 1-2 h |

## Final decision

**1. Ready for upstream discussion.** The core findings survived adversarial review. F1 is narrowed, F2 is qualified, and two of the four fixes are not ready.

| Finding | Readiness |
| --- | --- |
| F1 | **Ready for an issue** (Report A). The fix options are ready for a patch discussion inside that issue; no PR. |
| F2 | **Ready for an issue**, combined with F3 and F4 in Report B, citing #527. The fix is not ready until promotion is ownership-checked. |
| F3 | Part of Report B. Also **ready for a comment on #894 / PR #895**: #895 alone leaves the messages stranded. |
| F4 | Part of Report B. Also **ready for a comment on #899**: a second path to the hang, which #900 does not cover. |

## Recommended next action

**Prepare an upstream issue for human approval (Report A, F1).** The user writes and posts it, and says that AI tools were used in the investigation. It should contain:
- `reproductions/minimal/d4_retry_lost.py` and its output on 2.2.1 and `master`;
- the narrowed condition;
- the code path;
- the #545 reference;
- the regression test;
- one question: dead-letter (a1) or retry the enqueue (a2)?
