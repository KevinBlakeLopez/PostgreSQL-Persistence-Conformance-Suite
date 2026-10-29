# Findings

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

Each finding gives its hypothesis, contract, setup, results, controls, root cause, adversarial review and classification. Statements marked *source reading* were not observed at runtime. Every other runtime statement comes from a recorded run under [outputs/](outputs/); [outputs/SUMMARY.md](outputs/SUMMARY.md) lists every repetition. Contract references (C1 to C7, M1) are defined in [candidate-matrix.md](candidate-matrix.md#documented-contracts-used-below).

## Results at a glance

Counts are for Dramatiq 2.2.1 and `master` `08d711a` combined, without any candidate fix. Fix results are under each finding. The classifications were challenged on 2026-10-25 in [adversarial-verification.md](adversarial-verification.md); the qualifiers below come from that.

| ID | Scenario | Broker | Repetitions | Observed outcome | Classification |
| --- | --- | --- | --- | --- | --- |
| F1 (D4) | Actor fails while Redis is down; `Retries` can't enqueue the retry | Redis | 21 fault (16 macOS, 5 Linux); 11 control | Original acked and deleted in 21/21: no retry, no dead letter, no further attempt, nothing after a further restart (8/8). `max_retries=0` dead-letters (3/3). SIGKILL before the ack leaves it recoverable (3/3). No fault: normal retry (5/5). Verification: not lost when Redis received the enqueue but the reply was lost (6/6), or when only the ack failed (6/6). | CONFIRMED DEFECT, narrowed to retry enqueues that never reach Redis |
| F2 (N1) | Redis restarted while a live worker holds not-yet-due delayed messages | Redis | 14 fault (11 macOS, 3 Linux); 6 control | Stranded in the live worker's ack set in 14/14, with a fresh heartbeat. Maintenance on every call did not recover them; they ran only after the worker exited. Controls: no restart runs at ETA (3/3); a crashed worker's messages are recovered (3/3). Verification: a second default-timeout worker did not recover them (3/3); a short-timeout worker sometimes did (1/3); a paused owner lost them to another worker (2/2). | CONFIRMED DEFECT, conditional on the owner staying alive and heartbeating |
| F3 (N2) | Redis write pause (15 s) while the delay-queue consumer holds messages; URL form | Redis | 10 fault (7 macOS, 3 Linux); 3 control | The delay-queue consumer thread died in 10/10; the worker kept running ordinary jobs; later delayed jobs never fetched. 7 s pause: no death (3/3). Verification: also under a network blackhole (3/3); one pause killed both of two workers' consumers (3/3). | CONFIRMED DEFECT |
| F4 (D7) | Redis down at the graceful-shutdown requeue | Redis | 15 fault (11 macOS, 4 Linux); 6 control | `Worker.stop()` raised past its warning branch: exit 1 in 11/11 without AsyncIO, a hang in 4/4 with AsyncIO; `after_worker_shutdown` skipped in 15/15. The message was recovered by maintenance in 15/15. Control (D2): requeued, exit 0 (6/6). Verification: the same without any shutdown barrier, with a `TimeoutError`, and with AsyncIO installed first. | CONFIRMED DEFECT (lower severity) |
| D2 | Graceful shutdown with a prefetched message | Redis | 6 | Requeued onto the queue, exit 0 | EXPECTED BEHAVIOR (control for F4) |
| D3 | Ack outcome uncertainty | Redis | not run | Source: connection errors retried idempotently; `TimeoutError` not retried | DUPLICATE (#894) for the timeout case; otherwise expected at-least-once, not run |
| D6 | Second SIGTERM | Redis | not run | Source and tracker: hang with a non-daemon thread | DUPLICATE (#899) |
| D1, D5, N3-N5 | See candidate matrix | - | not run | - | Not assessed at runtime |

## Common setup

- **Broker.**
  - A private `redis-server` for each repetition, on a study-only loopback port (56391-56398), with `appendonly yes` and `appendfsync always`. Every acknowledged write is on disk before Redis replies, so a restart loses nothing.
  - The "Redis restart" fault is a SIGTERM to that process, which is a graceful shutdown, followed by a restart on the same data directory.
  - The N2 stall is `CLIENT PAUSE <ms> WRITE`: Redis's own pause, the one used by `FAILOVER`.
- **Worker.** The stock CLI: `python -I -u -m dramatiq app --processes 1 --threads 1 --verbose`, in its own process group. Its broker is `RedisBroker(host=..., port=...)`, or `RedisBroker(url=...)` where a variant name ends in `-url`.
  - redis-py 8.1.0 gives the host form 10 retries with jittered backoff (cap 1 s), and the URL form none. Both have a 5 s socket timeout.
- **Middleware.** The default middleware, plus Dramatiq's `CurrentMessage`, plus the study's observation hooks (`reproductions/app.py`).
  - The hooks are installed first, so their `after_*` hooks run after every default middleware. They only report to the witness.
  - D7 adds one exception: a barrier in the public `before_consumer_thread_shutdown` hook, which pauses each consumer thread at the end of its run loop.
- **External witness.** A TCP service in the harness process, outside the worker.
  - It records each actor event (`task_start`, `task_effect`, `task_done`, `task_raise`) and each hook event (`after_enqueue`, `after_ack`, `after_nack`, `after_process_message`), timestamped by the harness's clock.
  - It holds barriers until the harness releases them.
  - `task_effect` is the task's externally visible effect: it reaches the witness only if the actor got that far.
- **Broker state.** Snapshots of every `dramatiq:*` key, read over the harness's own connection at fixed points. A message is located by its Dramatiq id across:
  - payload hashes;
  - queue lists;
  - ack sets;
  - dead-letter sorted sets.
- **Producers.** Messages are enqueued by a separate `RedisBroker` in the harness, with no middleware and maintenance disabled, so the harness never triggers maintenance itself.
- **Network guard.** A `.pth`-loaded guard in every study environment refuses TCP connections to anything but loopback on ports 56391-56398. Another project's Redis listens on this machine's port 6379.

## F1 (D4). A message whose retry cannot be enqueued is acknowledged and deleted

> **Narrowed on 2026-10-25 by the adversarial verification** ([adversarial-verification.md](adversarial-verification.md#f1-a-failed-message-whose-retry-cant-be-enqueued-is-acknowledged-and-deleted)). The loss happens only when the retry enqueue **never reaches Redis**. Two other timings were observed:
> - **Redis accepts the enqueue but the reply is lost.** The retry exists and runs (3/3, URL form), or runs twice when redis-py re-sends the call (3/3, host form).
> - **The retry is enqueued, then the original's ack fails.** Nothing is lost (3/3); the work runs twice if the worker is killed first (3/3).
>
> **Scope.** The finding is stated for the Redis broker only. On RabbitMQ, source reading suggests the original would be redelivered instead.
>
> **Contract.** The strongest one is the retry and dead-letter documentation (C5), with C1 as looser support.
>
> **Branches affected.** A `dramatiq.Retry` exception and the last allowed retry are affected too. Exhausted and `throws` failures are dead-lettered and are not affected.

**Hypothesis.** When an actor fails and the `Retries` middleware's enqueue of the retry fails without reaching Redis, Dramatiq still acknowledges the original. The message is then gone: it is in no queue, delay queue, dead-letter queue or ack set, and no further attempt runs.

**Contract, strongest first.**
- **C5:** "Dramatiq automatically retries failures with exponential backoff"; and only "once a message has exceeded its retry or age limits, it gets moved to the dead letter queue" (`guide.rst:217-218`, `267-268`).
  - Here the actor's retries were not exhausted, and the message was neither retried nor dead-lettered.
  - C7 (the `Retries` docstring) says the same.
- **C1 and C6** ("only ever acknowledged … after they have been successfully processed"; "only ever acked when they're done processing") support this, but loosely. A normal retry also acks a failed original, after enqueueing its replacement.

**Trigger.** Redis is restarted while a failing actor's retry is being enqueued, so the enqueue is refused before any command reaches Redis. Redis stays down for longer than redis-py's retry window: 0 for the URL form, about 3 s of client retries for the host form. The steps:

1. The actor waits at a witness barrier.
2. The harness stops Redis.
3. The harness releases the actor, which raises.
4. In `fault-actor-redis` the actor is not told to fail. It writes its effect to the same Redis, which raises `redis.exceptions.ConnectionError`. This is the correlated production case: an outage that makes the actor fail also blocks its retry.
5. Once the observation hooks report that `after_process_message` has finished, the harness restarts Redis.

**Independent evidence.**

| Variant | Build | Platform | Runs | Retry enqueued | Original | In Redis afterwards | A further attempt | After a final Redis restart |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fault`, host form | 2.2.1 | macOS | 4 | 0/4 | acked in 4/4 | nothing in 4/4 | 0/4 | (check added later) |
| `fault`, host form, `durability` | 2.2.1 | macOS | 3 | 0/3 | acked in 3/3 | nothing in 3/3 | 0/3 | absent in 3/3 |
| `fault`, URL form | 2.2.1 | macOS | 3 | 0/3 | acked in 3/3 | nothing in 3/3 | 0/3 | - |
| `fault-actor-redis` | 2.2.1 | macOS | 3 | 0/3 | acked in 3/3 | nothing in 3/3 | 0/3 | - |
| `fault` | `master` | macOS | 3 | 0/3 | acked in 3/3 | nothing in 3/3 | 0/3 | - |
| `fault` | 2.2.1 | Linux | 3 | 0/3 | acked in 3/3 | nothing in 3/3 | 0/3 | absent in 3/3 |
| `fault-actor-redis` | 2.2.1 | Linux | 1 | 0/1 | acked | nothing | 0/1 | absent |
| `fault` | `master` | Linux | 1 | 0/1 | acked | nothing | 0/1 | absent |
| `control-ok` (no fault) | 2.2.1 | macOS 4, Linux 1 | 5 | 5/5 | acked | nothing (attempt 1 completed) | 5/5 completed | - |
| `control-noretries` (`max_retries=0`) | 2.2.1 | macOS | 3 | - | nacked in 3/3 | in `default.XQ` in 3/3 | - | - |
| `control-kill` (SIGKILL before Redis returns) | 2.2.1 | macOS | 3 | 0/3 | not acked | redelivered to the replacement and completed in 3/3 | 3/3 | - |

In total, the message was lost in 21 of 21 fault runs: 16 on macOS and 5 on Linux, across 2.2.1 and `master`. In all 8 runs that restarted Redis once more afterwards, nothing came back. "Nothing" means no payload, list, ack-set or dead-letter entry for the message. In `fault-actor-redis` the actor's own write failed with `ConnectionError` in every run.

- **While attempt 0 executes,** the message is in the worker's ack set and its payload hash, which is the normal state.
- **In every fault repetition:**
  - The worker logs `Retrying message '…' in N milliseconds.` at INFO, before the enqueue (`retries.py:147-148`).
  - It then logs `[CRITICAL] Unexpected failure in after_process_message of <…Retries…>`, ending in `redis.exceptions.ConnectionError: Error 61 connecting to 127.0.0.1:<port>. Connection refused.`
  - It then logs `Acknowledging message '…'`. The witness records `after_ack` for the original, which Dramatiq emits only after `consumer.ack` returns (`worker.py:417-419`).
  - Redis is now empty except for heartbeats. No retry starts within 20 s, although the configured backoff is 1-2 s.
  - Worker 1 shuts down with exit code 0, and a replacement worker whose maintenance runs on every call receives nothing in 20 s.
- **The retry was never accepted by Redis.** The Redis process was not running when the enqueue was attempted (connection refused), so no command reached it.
- **The ack was accepted and durable.** The worker received confirmation, the payload is deleted in the snapshot, and Redis persisted the deletion with `appendfsync always`.

**Controls.**

| Control | What changes | Observed (see the table) | What it shows |
| --- | --- | --- | --- |
| `control-ok` | No fault | The retry is enqueued to `default.DQ`, attempt 1 runs, both are acked | The retry path works when Redis is up |
| `control-noretries` | `max_retries=0`, same fault | `Retries exceeded`, `message.fail()`, nack retried until Redis is back, message in `default.XQ` | Without a retry, Dramatiq preserves a failed message in the dead-letter queue |
| `control-kill` | Same fault, but the worker is SIGKILLed before Redis returns, so nothing is acked | A replacement with fast maintenance redelivers the original (attempt 0 again) | The message was durable and recoverable; only Dramatiq's ack deletes it |
| URL form | `RedisBroker(url=...)`, no client retries | Same loss | Not specific to the connection form |
| `master` | Default branch `08d711a` | Same loss | Not fixed upstream |

**Root cause (source reading, consistent with every observation).**

1. `Retries.after_process_message` ends with `broker.enqueue(message, delay=delay)` (`middleware/retries.py:147-148`). It logs the retry first.
2. `RedisBroker.enqueue` calls `do_enqueue` without mapping Redis errors (`brokers/redis.py:184`), so a raw `redis.ConnectionError` propagates.
3. `Broker.emit_after` catches every `Exception` from a hook, logs it at CRITICAL, and continues with the next middleware (`broker.py:121-127`).
4. `WorkerThread.process_message` then reaches `finally` (`worker.py:602-607`) and calls `post_process_message`.
   - `message.failed` is False, because `Retries` calls `message.fail()` only for `throws` or exhausted retries (`retries.py:105`, `124`).
   - So the message is acked (`worker.py:409-419`). The ack is retried every 5 s while Redis is down (`worker.py:429-440`), so it eventually succeeds.

The ack is the step that destroys the message: `ack` deletes the payload (`dispatch.lua:191-196`). Neither the swallowing nor the ack is a broker limitation.

**Scope (source reading, not run).**
- `Callbacks` (`on_success`, `on_failure`), `Pipelines` (next step) and `GroupCallbacks` also enqueue from `after_process_message` (`middleware/callbacks.py:47-53`, `pipelines.py:58`, `group_callbacks.py:60`).
- A broker failure there is swallowed the same way and the original is acked, so the continuation is lost.
- `Callbacks` and `Pipelines` are default middleware.
- **RabbitMQ (corrected 2026-10-25).** `RabbitmqBroker.enqueue` retries internally and then raises `ConnectionClosed`, which would be swallowed the same way. But the consequence differs.
  - RabbitMQ acks are bound to the consumer's channel.
  - When an outage drops that connection, RabbitMQ requeues the unacked original itself.
  - The worker's retried ack then meets a new consumer that does not know the tag ("Failed to ack message: not in known tags.").
  - So a broker outage would redeliver the original rather than delete it. F1 on RabbitMQ would need the publish to fail while the consumer's channel stays up and acks.
  - Source reading only; not run.

**Adversarial review.**

1. **Is the behavior documented?** No. The docs say failures are retried, and dead-lettered once their limits are exceeded (C5). The only documented case of a failed message being acked without either is when the `Retries` middleware is removed: "Disabling this middleware will cause messages that fail due to exceptions to be marked 'done' rather than 'failed'". Here it is installed.
2. **Does Dramatiq promise the invariant?** Yes, explicitly through C5. C1 and C6 point the same way, but read literally they don't fit even normal retries, which ack the failed original after enqueueing its replacement.
3. **Is the broker configured correctly?**
   - Persistence is on, with `appendfsync always`.
   - The restart is graceful, and the data directory is reused.
   - `control-kill` shows the message survives the restart when it is not acked.
4. **Is it inherent to at-least-once delivery?** No. At-least-once permits duplicates, not deletion of unprocessed work.
5. **Did the worker acknowledge the message?** Yes, three ways: its log, the `after_ack` hook, and the deleted payload.
6. **Did the broker durably accept the ack?** Yes: the payload is gone, and Redis persists with `appendfsync always`. A further restart brought nothing back in 8/8 runs.
7. **Could the message be recovered after a restart?** Not after the ack, by any Dramatiq mechanism. Before it, yes (`control-kill`).
   - The worker's ERROR line for the failure (`Failed to process message job(...) with unhandled exception.`) names the actor and its arguments.
   - So where logs are kept, someone could rebuild the message by hand. That is manual recovery from an external record, not a Dramatiq mechanism.
8. **Was the failure caused by the application?** The actor's failure was, by design. Losing the message after that failure is Dramatiq's doing. In `fault-actor-redis` the actor's failure is itself caused by the outage.
9. **Was it caused by the broker?** No: the broker was down, which is the trigger, and came back with all data.
10. **Was it caused by test instrumentation?**
    - The observation hooks only report.
    - In `control-ok` the same hooks are present and the retry works.
    - The barrier only fixes the moment the actor raises.
    - No Dramatiq code is modified.
11. **Is it production-reachable?** Yes. It needs a broker outage at the moment a failing actor's retry is enqueued; restarts, failovers and network partitions all qualify. Actors often fail because of the same outage, as in `fault-actor-redis`. Every prefetched message that fails during the outage is lost, not just one.
12. **Does it reproduce on the current stable release?** Yes, 2.2.1 (macOS and Linux).
13. **On the default branch?** Yes, `08d711a`. The files involved are byte-identical to 2.2.1.
14. **Is there an existing issue or PR?** No dedicated issue was found. The behavior is described in comments on PR #545 (closed unmerged 2024-04-29) by user `spumer`:
    - 2023-12-12: "when enqueue to DELAY queue failed we silently ACK message and lose it";
    - 2024-06-15: "As result we have error but no have message in dead letter queue or delay queue".

    They offered to open an issue; none was found. No test covers it.
15. **Would the fix introduce regressions?** See the fix evaluation below, and the adversarial verification. Fix a2 duplicates retries when a reply is lost, and changes what `actor.send()` raises.
16. **(Added 2026-10-25) What if Redis received the enqueue?** Then nothing is lost; see the narrowing note at the top.
    - **Misleading log.** When only the reply is lost (URL form), Dramatiq still logs CRITICAL "Unexpected failure in after_process_message" for a retry that exists (3/3).
    - **Duplicates.** With the host form, redis-py re-sends the call and the retry runs twice (3/3).

**Classification: CONFIRMED DEFECT**, for the Redis broker, when the retry enqueue does not reach Redis. The defect is in Dramatiq: `Retries` together with `Broker.emit_after` and the worker's ack. It is not reported as an issue, but it was described in comments on a closed PR, so it is not new to the maintainers' tracker.

**Fix evaluation.** There are two candidates, both diffs against `08d711a` in `reproductions/fixes/`. The macOS runs:

| Build | Variant | Runs | Observed |
| --- | --- | --- | --- |
| `fix-d4-a1`: fail the message if the retry can't be enqueued | `fault` | 3 | Dead-lettered in 3/3: nacked once Redis is back, and still in `default.XQ` after a final Redis restart |
| `fix-d4-a1` | `fault-actor-redis` | 3 | Dead-lettered in 3/3, still there after a final restart |
| `fix-d4-a1` | `control-ok` | 3 | Retry enqueued and completed in 3/3 |
| `fix-d4-a2`: retry the enqueue while the broker is unreachable | `fault` | 3 | Retry enqueued once Redis is back, then the original acked, then attempt 1 completed, in 3/3. Nothing left after a final restart. |
| `fix-d4-a2` | `fault-actor-redis` | 3 | Same, 3/3 |
| `fix-d4-a2` | `control-ok` | 3 | Retry enqueued and completed in 3/3 |
| `fix-redis-reconnect` (F2-F4 fix, as a negative control) | `fault` | 1 | Message deleted, as unpatched: that fix does not touch this path |

Two more checks:
- **Linux, one run per fix:**
  - `fix-d4-a1` dead-letters the message, and it is still present after a final restart.
  - `fix-d4-a2` enqueues the retry once Redis returns and completes attempt 1; nothing is left.
- **The minimal reproduction** (`outputs/minimal/d4_retry_lost-*.txt`): 2.2.1 and `master` lose the message; `fix-d4-a1` dead-letters it.

Dramatiq's own `tests/test_redis.py`, `tests/test_worker.py` and `tests/middleware/test_retries.py` pass, 43 of 43, for both fixes and for `master` (Linux, `outputs/linux/upstream-tests/`).

Trade-offs, observed and from source:
- **a1.**
  - A message with retries left is dead-lettered during an outage, and needs a manual requeue.
  - It is broker-agnostic: about 10 lines in `retries.py`.
- **a2.**
  - Observed: the worker thread blocks in `Retries` for the length of the outage. In the run inspected, it logged "Failed to enqueue a retry … will be retried in 5 seconds" three times over 30 s.
  - It needs `RedisBroker.enqueue` to map `redis.ConnectionError` to `ConnectionClosed`. **Observed:** during an outage, `actor.send()` then raises `dramatiq.errors.ConnectionClosed`, which is not a `redis.ConnectionError`; unpatched it raises `redis.exceptions.ConnectionError`.
  - **Observed duplicates.** When Redis accepted the enqueue and the reply was lost, a2 enqueued the retry again and it ran twice in 3/3. Unpatched code ran it once under the same fault. At-least-once permits this, but it is a regression.
  - **Observed shutdown behavior.** During a graceful shutdown, a thread blocked here holds up `join_all` until `--worker-shutdown-timeout`. The worker then exits 0 with the original unacked, and a replacement runs it once (3/3).
- **a1, adversarially.** When the nack failed too and the worker was killed, the original stayed recoverable and ran once (3/3). The dead letter holds the payload as originally stored, without this failure's traceback.
- **Both** move the "Retrying message" log after the enqueue succeeds, so the log no longer claims a retry that does not exist.
- **Verdict (2026-10-25).** a1 is the safer minimal correction. a2 keeps retry semantics, at the cost of new duplicates, blocking, and an exception-type change. Neither is a ready PR until the maintainers choose the semantics.

**Remaining uncertainty.**
- RabbitMQ was not tested; see the scope note.
- The `Callbacks` and `Pipelines` variants were not run.
- How often production outages coincide with actor failures is not measured.

## F2 (N1). After a Redis connection error, delayed messages a live worker had prefetched are stranded while that worker lives

> **Qualified on 2026-10-25 by the adversarial verification** ([adversarial-verification.md](adversarial-verification.md#f2-delayed-messages-stranded-in-a-live-workers-ack-set-after-a-reconnect)).
>
> **The precise claim.** The messages stay stranded while the owning worker process lives and keeps calling Redis.
>
> **When they are recovered anyway:**
> - when another worker's maintenance runs, with a heartbeat timeout shorter than the outage, before the owner's first post-outage call (1/3 runs with a 2 s timeout; MONITOR shows worker 2's `fetch` running the maintenance);
> - when the owner stops heartbeating while alive (SIGSTOP longer than the other worker's timeout: recovered, 2/2).
>
> **Under Dramatiq's defaults** (60 s timeout, a 1-in-1,000 maintenance roll), stranding is the expected outcome. A second live worker with maintenance on every call and the default timeout did not recover them (3/3).
>
> **Ownership is confirmed from both sides:**
> - the worker's own memory shows its delay queue dropping from 3 to 0 at the connection error;
> - Redis's MONITOR shows the ack-set entry untouched until another worker's maintenance.
>
> **Contract.** Arguably within the letter of C2's "eventually", so this is classified as a strong implied-invariant violation that contradicts M1.

**Hypothesis.** A connection error in a delay-queue consumer makes Dramatiq drop the delayed messages it held in memory without requeueing them. They remain in the worker's ack set in Redis. Because the worker stays alive and keeps heartbeating, Redis maintenance never returns them, and they run only after the worker process exits.

**Contract.**
- **C2:** after a "network failure", pulled messages "will eventually be re-delivered to it (assuming it recovers) or another worker".
  - Here the worker recovered, and the messages were not re-delivered to it.
  - They do reach another worker after it exits, which arguably satisfies "eventually".
- **M1,** the maintainer's explanation on #527: after a Redis crash, "some time (the heartbeat timeout) has to pass until those messages are put back". Recovery was observed to depend on the owner's exit or loss of heartbeat, not on the timeout passing.
- **The design.** `ConsumerThread.close()` and `Worker.stop()` both return in-memory delayed messages to the broker. The reset discards them on Redis, where nothing else returns them.

**Trigger.** The steps:

1. Three messages are sent with a 25 s delay, and the delay-queue consumer fetches them: they leave `default.DQ` and enter `__acks__.<worker>.default.DQ`.
2. Redis is stopped for 15 s and restarted.
3. The worker stays up throughout.

Delayed messages include scheduled retries: the `Retries` middleware enqueues every retry with a delay. The default delay-queue prefetch is 1,000 per worker thread (`worker.py:96-98`).

**Independent evidence.**

| Variant | Build | Platform | Runs | Ran while worker 1 alive | Still in worker 1's DQ ack set at the last checkpoint | Worker 1 heartbeat age at the checkpoints | Run by a replacement after worker 1 stopped |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fault-aggressive` (maintenance every call, 2 s timeout) | 2.2.1 | macOS | 4 | 0/4 | 4/4, 35 s after ETA | ≤ 587 ms | 4/4 |
| `fault-aggressive`, URL form | 2.2.1 | macOS | 3 | 0/3 | 3/3, 35 s after ETA | ≤ 583 ms | 3/3 |
| `fault-aggressive` | `master` | macOS | 3 | 0/3 | 3/3, 35 s after ETA | ≤ 536 ms | 3/3 |
| `fault-aggressive` | 2.2.1 | Linux | 3 | 0/3 | 3/3, 35 s after ETA | ≤ 655 ms | 3/3 |
| `fault-default` (Dramatiq defaults) | 2.2.1 | macOS | 1 | 0/1 | 1/1, 300 s after ETA | ≤ 688 ms | 1/1 |
| `control-norestart` | 2.2.1 | macOS | 3 | 3/3, at ETA | - | - | - |
| `control-crash` (worker SIGKILLed) | 2.2.1 | macOS | 3 | - | - | - | 3/3 |

The minimal reproduction (`reproductions/minimal/n1_delayed_stranded.py`, output in `outputs/minimal/`) shows the same on 2.2.1. One message was fetched, Redis was down for 10 s, and 30 s after the ETA it had `runs=0`. It was still in the worker's DQ ack set, the heartbeat was 597 ms old, and it was still there after `worker.stop()`.

- **In every fault repetition:**
  - the delay-queue consumer logs `[CRITICAL] Consumer encountered a connection error: Error 61 … Connection refused.` and `Restarting consumer in 3.00 seconds.`
  - Nothing is logged about the delayed messages it held.
  - After Redis returns, until the observation ends, the witness records no execution.
  - The three Redis ids stay in the worker's `default.DQ` ack set, and the `default.DQ` list stays empty.
  - The worker's heartbeat is under 0.7 s old at every checkpoint.
- **This holds with maintenance on every dispatch call and a 2 s heartbeat timeout** (`fault-aggressive`, 35 s past ETA). It also holds with Dramatiq's defaults (`fault-default`, 300 s past ETA).
- **On graceful exit,** worker 1 logs `Worker has been shut down.` and exits 0. The three ids are still in its ack set: nothing requeued them, because they were no longer in its memory.

**Controls.**

| Control | What changes | Observed | What it shows |
| --- | --- | --- | --- |
| `control-norestart` | No fault | All three run at their ETA | The delay path works |
| `control-crash` | The worker is SIGKILLed instead of Redis restarting | A replacement with fast maintenance runs all three | M1 holds for a dead worker |
| Recovery, in every fault run | Worker 1 stopped, then a replacement started | The replacement runs all three within about 0.3 s of booting | The messages were intact; only worker 1's liveness kept them unavailable |
| URL form, `master` | | Same as `fault-aggressive` | |

**Root cause (source reading, consistent with every observation).**

1. `ConsumerThread.run` handles `BrokerConnectionError` with `self.delay_queue = PriorityQueue()` (`worker.py:325-327`, from commit `115627a`, 2017).
2. The restart branch then calls `close()` (`worker.py:337-340`). `close()` requeues the contents of the new, empty queue (`worker.py:486`), so nothing is requeued.
3. The dropped messages stay in `dramatiq:__acks__.<worker_id>.<queue>.DQ`.
4. Every dispatch call by the same worker refreshes its heartbeat (`dispatch.lua:58`), so maintenance (`dispatch.lua:110-132`) never selects it.

The design assumption behind the reset holds only for RabbitMQ. `_RabbitmqConsumer.requeue` documents it: "RabbitMQ automatically re-enqueues unacked messages when consumers disconnect so this is a no-op" (`brokers/rabbitmq.py:574-577`). On RabbitMQ, dropping the in-memory copies avoids duplicates. On Redis, nothing redelivers them while the worker lives.

**Adversarial review.**

1. **Documented?** No. M1 states the opposite expectation.
2. **Is the invariant promised?** C2 promises eventual redelivery after a network failure "assuming it recovers". Here the worker recovered and they were not redelivered to it, or to anyone, while it ran. M1 names the heartbeat timeout; observed recovery depended on the worker exiting instead.
3. **Broker configured correctly?** Yes. The payloads survived and were executed after the worker exited.
4. **At-least-once?** No duplicate is involved. This is unavailability.
5-6. **Acks?** Nothing was acked. The messages stayed in the ack set.
7. **Recoverable after a restart?** Yes, after the *worker* restarts. That is the point: recovery is coupled to worker lifetime.
8-10. **Caused by the application, the broker or the instrumentation?** No to all three. The actor never ran, and `control-norestart` runs the same hooks.
11. **Production-reachable?** Yes, for any Redis outage longer than redis-py's retry window while a worker holds delayed messages: a restart, a failover, or a network loss. Retries are delayed messages, and workers that run for days are common.
12-13. **Reproduces on 2.2.1 and `08d711a`?** Yes. macOS and Linux.
14. **Existing issue?** #527 ("Delayed Jobs aren't run after cycling Redis", closed 2023-02-25):
    - It reports this symptom: delayed jobs never ran, and ran "a few hours later".
    - It was closed with explanation M1, which these runs contradict.
    - No root-cause report or fix was found.
15. **Fix regressions?** Yes, observed. The proposed fix keeps the messages in memory. If another worker's maintenance recovers them while the owner is still alive (its heartbeat expired), they run twice: 2/2 in `sigstop`, against once unpatched. An ownership-checked promotion would prevent this; see the F2-F4 fix evaluation.

**Classification: CONFIRMED DEFECT**, as a clear implementation-invariant violation on the Redis broker, not an explicit documented-contract violation: in-memory work is discarded while the worker continues. The responsible component is `ConsumerThread`'s connection-error path.
- **The condition.** It holds while the owning worker lives and keeps heartbeating, unless another worker's maintenance gets there first (see the note at the top).
- **Prior report.** The symptom was reported in #527 and closed with a different explanation. This is new root-cause evidence for that report, not a new symptom.

**Fix evaluation.** See [F2-F4 fix evaluation](#fix-evaluation-for-f2f4).

**Remaining uncertainty.**
- Main-queue messages are not stranded this way. Messages already in the work queue are processed and acked normally after reconnection (`worker.py:400-452`). The main consumer's `message_cache` is normally empty when a fetch fails.
- A lost fetch reply could strand main-queue messages too (N5, not run).

## F3 (N2). An unmapped Redis error kills the delay-queue consumer thread

**Hypothesis.** When a delay-queue consumer that holds delayed messages meets a Redis error Dramatiq does not map, its error handler's own requeue fails the same way. The exception escapes the thread. That worker then never consumes the delay queue again, while it stays up, keeps heartbeating, and processes ordinary messages.

**Contract.** C2, C5; and the consumer's own design, which restarts after errors ("try to restart it once a second", `worker.py:335-340`).

**Trigger.** Three messages are sent with a 120 s delay and fetched. Then the harness runs `CLIENT PAUSE 15000 WRITE`, Redis's own write pause, used by `FAILOVER`.
- Dispatch calls are Lua scripts without a `no-writes` flag, so they block.
- redis-py's 5 s socket timeout raises `redis.TimeoutError`, which `_RedisConsumer` does not map (#894).
- The URL form is used, which has no client retries. With the host form the stall would have to outlast about 10 × 5 s per call (source reading).
- After the pause, the harness sends two probes: an ordinary message, and a delayed message due in 2 s.

**Independent evidence.**

| Variant | Build | Platform | Runs | Delay-queue consumer thread died | Delayed probe ran | Ordinary probe ran | Held messages still in worker 1's ack set after its clean exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fault`, 15 s pause | 2.2.1 | macOS | 4 | 4/4 | 0/4 (stuck in the `default.DQ` list) | 4/4 | 3/3 recorded (the first run predates the field) |
| `fault`, 15 s pause | `master` | macOS | 3 | 3/3 | 0/3 | 3/3 | 3/3 |
| `fault`, 15 s pause | 2.2.1 | Linux | 3 | 3/3 | 0/3 | 3/3 | 3/3 |
| `control-shortpause`, 7 s | 2.2.1 | macOS | 3 | 0/3 | 3/3 | 3/3 | 0/3 (requeued at shutdown) |

- **In every 15 s repetition:**
  - The delay-queue consumer logs `Consumer encountered an unexpected error.` (`redis.exceptions.TimeoutError`), then `Re-enqueueing [three ids] on queue 'default.DQ'`, then `Exception in thread Thread-3:` with a second `TimeoutError` from `_RedisConsumer.requeue`.
  - The main consumer logs the same error, restarts and recovers.
- **After the pause:**
  - The ordinary probe runs, so the worker is alive.
  - The delayed probe is never fetched: it sits in the `dramatiq:default.DQ` list for 30 s.
  - The three held ids stay in worker 1's ack set.
  - Worker 1's heartbeat is fresh.
- **On SIGTERM,** worker 1 logs `Worker has been shut down.` and exits 0, while the three held messages remain in its ack set.

**Control.** `control-shortpause` (7 s) outlasts one socket timeout but not two. The fetch times out, the requeue in `close()` waits out the rest of the pause and succeeds, and the consumer restarts. Both probes run, and the held messages are requeued and refetched. So the thread dies only when the error handler's own Redis call fails too.

**Root cause (source reading, consistent with the observations).**

1. `_RedisConsumer.__next__` maps only `redis.ConnectionError` (`brokers/redis.py:372-373`). A `TimeoutError` reaches `ConsumerThread.run`'s generic `except Exception` (`worker.py:329-333`), which calls `close()`.
2. `close()` drains the delay queue and calls `_RedisConsumer.requeue` (`worker.py:486`). That does not map Redis errors either (`brokers/redis.py:332`), so `close()`'s `except BrokerConnectionError` (`worker.py:488`) cannot catch the second `TimeoutError`.
3. The exception leaves the `except` block and ends `run()`. Nothing restarts a dead consumer thread.

The same structure applies, on source reading only, when `handle_delayed_messages`'s `self.broker.enqueue(new_message)` (`worker.py:360`) raises an unmapped `redis.ConnectionError` during an outage. That variant was not run.

**Adversarial review, in brief.**
- **Trigger.** It is Redis's own command, with redis-py's default timeout.
- **Instrumentation.** The hooks only report, and the 7 s control runs the same hooks.
- **Reproduces?** Yes, on 2.2.1 and `08d711a`, and on Linux.
- **Existing issue?** #894 (open) and PR #895 (open, unreviewed since 2026-09-07) report that `redis.TimeoutError` is treated as an unexpected error. They say the consumer is "closed and rebuilt a second later". That is true with an empty delay queue, and it is what the 7 s control shows. Thread death is not reported.
  - **PR #895 alone, observed.** It maps `TimeoutError` in `__next__`, `ack` and `nack`, but not in `requeue`. I applied only its `dramatiq/brokers/redis.py` change (head `8dd09c1`) to `master` (variant `fault-url-pr895`, 2 runs).
    - The thread survives: the timeouts are logged as connection errors, and both probes run.
    - The three held delayed messages are stranded instead: still in worker 1's ack set after the pause, and after its clean exit.

    So #895 turns F3 into F2. The build: `gh pr diff 895 --repo Bogdanp/dramatiq | git apply --include='dramatiq/brokers/redis.py'`, applied to `08d711a` at PR head `8dd09c1f59b86268b2ed6cf5f82a35b079029563`.

**Classification: CONFIRMED DEFECT**, related to #894 but not reported. It is a strong implied-invariant violation: the run loop is designed to restart after errors.

**Verified on 2026-10-25** ([adversarial-verification.md](adversarial-verification.md#f3-the-delay-queue-consumer-thread-dies-on-an-unmapped-redis-error)):
- **A real partition does it too.** A network blackhole through a TCP proxy, instead of `CLIENT PAUSE`, killed the thread in 3/3. The worker's own state report showed `default.DQ` `alive: false`, and nothing restarted it.
- **PR #895 alone, observed.** With its `redis.py` change, the thread survives, but the held messages are stranded (F2): 2/2 under `CLIENT PAUSE`, 1/1 under the blackhole. The regression test fails at "the delayed message held during the stall never ran".

## F4 (D7). If Redis is unavailable at the shutdown requeue, `Worker.stop()` aborts; with the AsyncIO middleware the worker never exits

**Hypothesis.** The source suggests `Worker.stop()`'s handler for a failed requeue (`worker.py:176-179`, log a warning and continue) cannot catch the Redis broker's error. Shutdown would then abort, and `after_worker_shutdown` would never run. Recovery of the messages would be left to heartbeat maintenance.

**Contract.**
- C3: "Any tasks still in worker memory at this point are re-queued on the broker."
- C2: eventual redelivery.
- The exit codes table: 0 is a graceful exit, 1 means "killed".

**Trigger.**
1. Three messages are sent. The first runs at a barrier, and the second is prefetched.
2. SIGTERM goes to the main process, and the first job is released and acked.
3. Both consumer threads pause at the end of their loops, in the `before_consumer_thread_shutdown` barrier.
4. Redis is stopped, and the barriers are released, so the requeue meets the outage.

**Independent evidence.**

| Variant | Build | Platform | Runs | Worker 1 exit | `after_worker_shutdown` ran | "Failed to requeue messages" logged | Prefetched message after exit | Run by a replacement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fault` | 2.2.1 | macOS | 4 | 1 in 4/4 | 0/4 | 0/4 | in the dead worker's ack set | 4/4 (fast maintenance) |
| `fault` | `master` | macOS | 3 | 1 in 3/3 | 0/3 | 0/3 | same | 3/3 |
| `fault` | 2.2.1 | Linux | 3 | 1 in 3/3 | 0/3 | 0/3 | same | 3/3 |
| `fault-defaultrecovery` | 2.2.1 | macOS | 1 | 1 | 0/1 | 0/1 | same | 1/1, 293 s after the replacement booted (default maintenance) |
| `fault-asyncio` | 2.2.1 | macOS | 3 | hung in 3/3 (SIGKILL after 60 s) | 0/3 | 0/3 | same | 3/3 |
| `fault-asyncio` | 2.2.1 | Linux | 1 | hung | 0/1 | 0/1 | same | 1/1 |
| `control` (Redis up, the D2 case) | 2.2.1 | macOS | 3 | 0 in 3/3 | 3/3 | - | requeued onto `dramatiq:default` | 3/3 |
| `control-asyncio` | 2.2.1 | macOS | 3 | 0 in 3/3 | 3/3 | - | requeued | 3/3 |

- **The traceback.** `Re-enqueueing ['…'] on queue 'default'` is followed by `Process Process-1:` and a traceback through `cli.py:478` → `worker.py:177` → `worker.py:461` → `brokers/redis.py:332`, ending in `redis.exceptions.ConnectionError`.
- **What is missing.** `Failed to requeue messages` is never logged, `Worker has been shut down.` is never logged, and `after_worker_shutdown` never runs.
- **The exit code** is 1.
- **The message is not lost.** The prefetched message is in the dead worker's ack set, with a stale heartbeat. A replacement with fast maintenance runs it immediately. With default maintenance it ran 293 s after the replacement booted (one run).
- **With the AsyncIO middleware** (`fault-asyncio`), the worker process prints the same traceback and never exits; the main process waits for it. Three processes were still running 60 s later, until SIGKILL. `control-asyncio` (Redis up) exits 0.

**Control.** `control` (Redis up, the D2 case) requeues the prefetched message onto `dramatiq:default`, logs `Worker has been shut down.`, and exits 0. A replacement runs it at once.

**Root cause.**
- `_RedisConsumer.requeue` raises a raw `redis.ConnectionError` (`brokers/redis.py:332`), so `except BrokerConnectionError` at `worker.py:178` does not match it.
- The exception leaves `Worker.stop()` before it closes the consumers and emits `after_worker_shutdown` (`worker.py:182-188`).
- The AsyncIO middleware stops its event-loop thread only in that hook (`middleware/asyncio.py:36-38`). That thread is not a daemon (#899), so the interpreter waits for it forever.

**Adversarial review, in brief.**
- **Recovery is as documented.** The message is redelivered after the heartbeat timeout (C1, C2), so recovery itself is EXPECTED BEHAVIOR.
- **What is wrong is the shutdown path:**
  - the documented handler cannot run on Redis;
  - a broker outage during shutdown exits with the "killed" code;
  - with AsyncIO, the worker hangs.
- **It is not #899.** #899 is the same thread reached by a second signal, and its fix (#900, `os._exit` on the second signal) would not help here, because there is only one signal.
- **The preliminary review's premise** ("logs a warning … continues closing consumers and completing shutdown") does not hold on Redis.

**Classification: CONFIRMED DEFECT, lower severity.** No message is lost. The hang depends on the AsyncIO middleware.

**Verified on 2026-10-25** ([adversarial-verification.md](adversarial-verification.md#f4-shutdown-requeue-failure-aborts-workerstop-asyncio-hang)):
- **No shutdown barrier needed.** With Redis already down when SIGTERM arrives, the worker exits 1 (2/2), or hangs with AsyncIO (3/3).
- **Either exception type.** A `TimeoutError` (`CLIENT PAUSE` at the requeue, URL form) does the same: exit 1 (2/2), or a hang with AsyncIO.
- **Only the event-loop thread holds the process.** Without AsyncIO, only `MainThread` is non-daemon at the end. With it, `MainThread` and `Thread-2` (the event loop) are, and the process hangs.
- **The exit code is a policy question.** The reconnect fix makes the documented warning branch reachable, and exits 0. Whether a shutdown that left work for heartbeat recovery should exit 0 or non-zero is for the maintainers to decide. The part that matters for correctness is finishing shutdown, which ends the hang.

## Fix evaluation for F2-F4

The candidate is `reproductions/fixes/fix-redis-reconnect.diff`, against `08d711a`: 3 files, +33/-4. It has four parts:

1. **A consumer attribute.** `Consumer.redelivers_unacked_on_disconnect`, True by default, which keeps today's behavior for RabbitMQ and third-party brokers. `_RedisConsumer` sets it to False. `ConsumerThread.run` discards the in-memory delay queue after a `BrokerConnectionError` only when it is True.
2. **Error mapping.** `_RedisConsumer.requeue` maps `redis.ConnectionError` and `redis.TimeoutError` to `ConnectionClosed`. That makes `Worker.stop()`'s documented warning branch, and `close()`'s handler, reachable on Redis.
3. **`close()` keeps what it can't requeue.** If `close()` fails to requeue the delay queue, it puts those messages back instead of dropping them.
4. **A failed promotion is put back.** A delayed message whose promotion (`enqueue`) fails goes back on the delay queue before the error propagates.

macOS runs:

| Variant | Runs | Observed |
| --- | --- | --- |
| N1 `fault-aggressive` | 3 (+1 ended by a harness race, see outputs/README.md) | All three delayed jobs ran on worker 1, at their ETA after Redis came back, in 3/3. Nothing was left for the replacement. |
| N1 `control-norestart` | 1 | Ran at ETA |
| N2 `fault` (15 s pause) | 3 | No thread death in 3/3. The delayed probe ran in 3/3. The held messages were kept and requeued at shutdown (0 left in the ack set). |
| N2 `control-shortpause` | 1 | As unpatched |
| D7 `fault` | 3 | Exit 0, `Failed to requeue messages on queue 'default'` logged, `after_worker_shutdown` ran, in 3/3. The message was recovered by the replacement in 3/3. |
| D7 `fault-asyncio` | 3 | Exit 0 in 3/3, no hang |
| D7 `control` | 1 | Exit 0, requeued |
| D4 `control-ok` | 1 | Retry works |
| D4 `fault` | 1 | Message still deleted (F1 needs its own fix) |

Linux, one run each:
- N1 `fault-aggressive`: all three ran on worker 1.
- N2 `fault`: no thread death, and the delayed probe ran.
- D7 `fault-asyncio`: exit 0, the warning logged, and `after_worker_shutdown` ran.

The minimal F2 reproduction runs its delayed message on this build (`runs=1`, no ack set left; `outputs/minimal/n1_delayed_stranded-fix-redis-reconnect.txt`). Dramatiq's own Redis, worker and retry tests pass, 43 of 43 (Linux).

**Comparison with the open PR #895,** observed: its mapping alone turns F3's thread death into F2's stranding. See F3.

Trade-offs (source reading):
- **A new attribute** on the public `Consumer` class.
- **A small duplicate window.** Messages kept across a reconnect are promoted with the new consumer. A lost reply to an applied promotion could duplicate one, the same window as the open #431.
  - Observed 2026-10-25: one duplicate in both builds. With the fix it came 2.7 s later; unpatched, 37 s later, after the worker exited.
- **(Observed 2026-10-25) A duplicate when ownership expires while the owner is alive.** If another worker's maintenance recovers the messages, for example because the owner paused longer than that worker's heartbeat timeout, then the owner still holds its copies and promotes them too.
  - Each ran twice in 2/2 `sigstop` runs, against once unpatched.
  - An ownership-checked promotion would remove this: a Lua command that promotes only while the id is still in the caller's ack set, as proposed in PR #859 for #431.
  - Until then, this fix is **not ready to propose as is**.
- **The D7 change alters an exit code.** With the warning branch reachable, shutdown during an outage exits 0 instead of 1. That matches the existing code's intent, but changes what a process supervisor sees.
- **The handling for `TimeoutError` from `__next__`, `ack` and `nack`** (PR #895's subject) is left to #895.

## Candidates not run

D1, D3, D5, D6, N3, N4 and N5 were assessed from source and the issue tracker only. The reasons are in [candidate-matrix.md](candidate-matrix.md).

## Production relevance (2026-10-26)

F1, F2, F3, and F4 are rated in [`../unfiled-findings-production-relevance/README.md`](../unfiled-findings-production-relevance/README.md), section "Dramatiq".

Judgment that day: F2 is moderate, conditional on a Redis restart while a live worker holds delayed messages. dramatiq#527 (2023) reports that symptom. F1 is low to moderate. F3 and F4 are low. F4 does not lose the message.

F2 was queued 2026-10-27 as DM2. The draft is [`upstream/dramatiq-delayed-stranded-draft.md`](upstream/dramatiq-delayed-stranded-draft.md), written 2026-10-28. It is not approved to post. F1, F3, and F4 are not in that item.
