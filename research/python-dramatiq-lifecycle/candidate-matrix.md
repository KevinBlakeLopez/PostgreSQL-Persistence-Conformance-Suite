# Candidate matrix

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

This matrix was written before any experiment ran. The selected candidates were later challenged in [adversarial-verification.md](adversarial-verification.md). Every "source reading" entry is an interpretation of the code, not an observation. The experiments that test the selected candidates are in [findings.md](findings.md).

## Versions and sources read

- **Dramatiq.** Release 2.2.1 (PyPI, 2026-09-02) and `master` at `08d711a` (2026-10-13). Between them, `worker.py`, `brokers/redis.py`, `brokers/redis/dispatch.lua`, `middleware/retries.py` and `cli.py` are identical. `broker.py` and `asyncio.py` differ only in typing imports and a `TimeoutError` alias.
- **redis-py.** 8.1.0, the newest version Dramatiq allows (`redis>=4.0,<9.0`).
- **Docs.** The docs source in the repository is identical at the tag and on `master` for every passage quoted below. The only difference is a RabbitMQ paragraph.

## Documented contracts used below

| Ref | Source | Text |
| --- | --- | --- |
| C1 | `docs/source/advanced.rst:171-175` | "Messages that have been pulled by workers but not processed are returned to the broker on graceful shutdown and any messages that are in flight when a worker is terminated are going to be redelivered later. Messages are only ever acknowledged to (removed from) the broker after they have been successfully processed." |
| C2 | `advanced.rst:177-180` | "When a worker goes down while processing messages (eg. due to hardware, power or network failure) then the messages it pulled from the broker will eventually be re-delivered to it (assuming it recovers) or another worker." |
| C3 | `advanced.rst:330-334` | On `INT`/`TERM`: "Consumer threads will stop receiving new work and worker threads will finish processing the work they have in flight before shutting down. Any tasks still in worker memory at this point are re-queued on the broker." |
| C4 | `advanced.rst:336-337` | "If you send a second `INT` or `TERM` signal then the worker processes will be killed immediately." |
| C5 | `guide.rst:214-218`, `264-270` | "Dramatiq automatically retries failures with exponential backoff." Once a message exceeds its retry or age limits, "it gets moved to the dead letter queue where it's kept for up to 7 days". |
| C6 | `motivation.rst:89-92` | "tasks are only ever acked when they're done processing." |
| C7 | `middleware/retries.py`, class docstring | "Middleware that automatically retries failed tasks with exponential backoff." |
| M1 | Maintainer comment on #527 (2023-02-18) | Messages a worker pulled sit in its "acks" set. "When a worker crashes (or Redis crashes, same difference), some time (the heartbeat timeout) has to pass until those messages are put back on their respective queues." |

## Redis broker mechanics (source reading)

These facts recur in the candidates. Paths are relative to the Dramatiq repository.

- **Fetch.** `fetch` pops message ids off `dramatiq:<queue>` and adds each one to `dramatiq:__acks__.<worker_id>.<queue>` in the same Lua call (`dispatch.lua:154-173`).
- **Ack.** `ack` removes the id from that set and deletes the payload (`dispatch.lua:191-196`).
- **Requeue.** `requeue` moves ids from the set back onto the queue (`dispatch.lua:178-187`).
- **Heartbeats.** Every dispatch call refreshes the caller's heartbeat (`dispatch.lua:58`). No separate heartbeat thread exists.
- **Maintenance.** It runs on a random roll: 1,000 in 1,000,000 calls, never on ack or nack (`redis.py:36-41`, `238-242`). It requeues ack sets only for workers whose heartbeat is older than `heartbeat_timeout` (60 s by default), and only for the queue named in that call (`dispatch.lua:110-132`).
  - **Consequence.** The ack set of a worker that is alive and making calls is never recovered by maintenance.
- **Error mapping.** `_RedisConsumer.ack`, `nack` and `__next__` map `redis.ConnectionError` to Dramatiq's `ConnectionClosed`, a `BrokerConnectionError` (`redis.py:306-373`). `_RedisConsumer.requeue` and `RedisBroker.enqueue` map nothing (`redis.py:150-186`, `326-332`).
  - `redis.TimeoutError` is mapped nowhere: it is not a subclass of `redis.ConnectionError` (#894).
- **Hook failures.** `Broker.emit_after` logs any `Exception` raised by a middleware hook at CRITICAL and continues (`broker.py:121-127`).
- **redis-py 8.1.0 defaults.** Observed on constructed connection objects, with no network I/O.
  - `RedisBroker(host=..., port=...)` gives 10 retries with jittered exponential backoff (0.01 s base, 1 s cap).
  - `RedisBroker(url=...)` gives 0 retries.
  - Both have `socket_timeout` = `socket_connect_timeout` = 5 s.

## Summary

| ID | Scenario | Suspected outcome (source reading) | Potential severity | Existing upstream item | Decision |
| --- | --- | --- | --- | --- | --- |
| D4 | Retry publication fails, original then acked | Message deleted with no retry and no dead letter | Permanent loss | Described in comments on closed, unmerged PR #545; no issue | **Selected, priority 1** |
| N1 | Broker connection error while delayed messages are held in memory | Delayed messages stranded in a live worker's ack set until that worker exits | Unbounded delay of scheduled work and retries | #527 (closed 2023; maintainer attributed it to the heartbeat timeout) | **Selected, priority 2** |
| N2 | Unmapped Redis error in the delay-queue consumer | The delay-queue consumer thread dies; that worker never consumes the delay queue again | Delayed work and retries stall until restart | #894 covers the misclassification, not thread death | **Selected as an N1 variant** |
| D7 | Broker unavailable at the shutdown requeue | `Worker.stop()` raises instead of the documented warning path; recovery left to heartbeat maintenance | Delayed redelivery; wrong exit path; possible hang with AsyncIO | None found | **Selected, priority 3** |
| D2 | Graceful shutdown with prefetched messages | Work queue and delay queue requeued; a narrow consumer-cache race is not | Delayed redelivery in a narrow race | Shutdown requeue covered by existing tests | **Control for D7** |
| D3 | Ack outcome uncertainty | Connection errors retried idempotently; `TimeoutError` not retried | Duplicate after restart | #894 / PR #895 (open) | Rejected: covered by #894 |
| D6 | Second termination signal | Exit; hang with a non-daemon thread | Hang | #899, PR #900, #911 (all open) | Rejected: duplicate |
| D1 | Ack before processing completed | No path found | n/a | None | Rejected: no lead |
| D5 | Shutdown interrupts cleanup | Documented wait up to `--worker-shutdown-timeout` | Documented | None | Rejected: documented, configuration-dependent |
| N3 | Callbacks, pipelines and group callbacks enqueue from `after_process_message` | Same swallow-then-ack as D4: the continuation is lost | Lost continuation | None found | Folded into D4 as scope; not tested |
| N4 | Fully busy worker stops heartbeating | Its messages requeued while still running; duplicate execution | Duplicate | #692 (open) | Rejected: at-least-once, existing issue |
| N5 | Fetch reply lost after Redis ran the script | Fetched ids stranded in the live worker's ack set | Like N1 | None found | Rejected for now: needs a protocol proxy; N1 tests the same stranding with a real trigger |

## Candidates

Common to all candidates: broker Redis 8.6.2; Dramatiq 2.2.1 and `master` `08d711a`.

### D4. Retry publication versus original acknowledgement

- **Relevant API:**
  - `Retries.after_process_message` (`middleware/retries.py:97-147`) ends with `broker.enqueue(message, delay=delay)`.
  - `RedisBroker.enqueue` (`brokers/redis.py:150-186`) raises a raw `redis.ConnectionError`.
  - `Broker.emit_after` (`broker.py:121-127`) logs the exception at CRITICAL and continues.
  - `WorkerThread.process_message` (`worker.py:542-613`) reaches its `finally` and calls `post_process_message`.
  - `message.failed` is still False, because `Retries` calls `message.fail()` only on exhaustion. So the message is acked (`worker.py:415-419`), and the ack is retried every 5 s until it succeeds (`worker.py:429-440`).
- **Documented guarantee:** C1, last sentence; C5; C6; C7.
- **Failure trigger:** Redis is unavailable when a failing actor's retry is enqueued, for longer than redis-py's retry window. Examples: a restart, a failover, a network partition. In practice this is correlated with the actor's own failure, since an actor that depends on the same infrastructure fails during the same outage.
- **Expected outcome:** one of these holds:
  - the retry is in the delay queue;
  - the original stays recoverable (not acked);
  - the message is dead-lettered.
- **Suspected outcome:** the retry is never written, and the original is acked once Redis returns. The message is in no queue, delay queue, dead-letter queue or ack set, and no further attempt runs.
- **Severity (potential):** permanent loss of a message configured for retries. The only signal is a CRITICAL log line.
- **Observability:**
  - Redis keys: the payload hash entry is deleted, and the DQ, XQ and ack sets are empty.
  - The external witness records a single attempt.
  - A replacement worker receives nothing.
- **Reproduction cost:** medium. Redis is stopped at a deterministic barrier inside the actor.
- **Existing issue:** described in two comments by user `spumer` on PR #545 (closed unmerged 2024-04-29). They wrote "when enqueue to DELAY queue failed we silently ACK message and lose it", and later "We can open new issue for that". The maintainer's reply predates the second comment and addressed only the PR's nack approach. A search of issue titles and bodies found no dedicated issue and no test.
- **Priority:** 1.

### N1. Delayed messages stranded after a broker connection error

- **Relevant API:**
  - `ConsumerThread.run` (`worker.py:325-327`) does `except BrokerConnectionError: self.delay_queue = PriorityQueue()`. The reset dates from `115627a` (2017-06-24).
  - The restart branch then calls `close()` (`worker.py:337-340`), which requeues the contents of the new, empty delay queue (`worker.py:482-489`).
  - The dropped messages remain in `dramatiq:__acks__.<worker_id>.<queue>.DQ`.
  - The worker's heartbeat keeps being refreshed by its dispatch calls (`dispatch.lua:58`), so maintenance (`dispatch.lua:110-132`) never treats it as dead.
- **Documented guarantee:** C2 ("network failure … will eventually be re-delivered to it (assuming it recovers)"); M1 (the heartbeat timeout).
- **Failure trigger:** Redis becomes unavailable for longer than redis-py's retry window while a worker holds delayed messages that are not yet due, and the worker survives. A restart, failover or network loss would do. "Delayed messages" means `send_with_options(delay=...)` messages and scheduled retries. The delay-queue prefetch defaults to 1,000 × the thread count.
- **Expected outcome (per M1 and C2):** the messages return to the delay queue after the heartbeat timeout and run at or after their ETA.
- **Suspected outcome:** they are dropped from memory and stay in the live worker's ack set. They run only after that worker process exits, plus the heartbeat timeout, plus a maintenance roll.
- **Severity (potential):** scheduled work and retries are delayed for as long as the worker lives. With several workers and a shared outage, this applies to all their prefetched delayed messages.
- **Observability:**
  - Redis: the DQ list is empty, the ids sit in the worker's DQ ack set, and its heartbeat is fresh.
  - The witness records no execution after the ETA.
  - The messages are recovered after the worker stops.
- **Reproduction cost:** low to medium.
- **Existing issue:** #527 (2023-02-18, closed). Same symptom: delayed jobs never ran after "cycling Redis" and ran "a few hours later". The maintainer gave M1 as the cause. No root-cause report was found.
- **Priority:** 2.

### N2. The delay-queue consumer thread dies

- **Relevant API:** two paths in `ConsumerThread`:
  - **The enqueue path.** In `handle_delayed_messages` (`worker.py:346-362`), `self.broker.enqueue(new_message)` raises an unmapped `redis.ConnectionError`. The generic `except Exception` handler (`worker.py:329-333`) calls `close()`. `close()` requeues the delay queue through `_RedisConsumer.requeue`, which raises an unmapped error again, and its own `except BrokerConnectionError` cannot match it. The exception escapes the handler and ends `run()`, and nothing restarts the thread.
  - **The timeout path.** A `redis.TimeoutError` from the fetch (#894) leads to the same handler. If the delay queue is not empty and Redis is still stalled, it ends the same way.
- **Documented guarantee:** C2, C5.
- **Failure trigger:** a Redis outage while a delayed message becomes due, or a Redis stall longer than the 5 s socket timeout while delayed messages are held.
- **Suspected outcome:** that worker never consumes that delay queue again, but the process stays up and keeps heartbeating. The in-memory delayed messages are drained and stranded.
- **Severity (potential):** all delayed work and retries for that queue stall on that worker until it restarts.
- **Observability:**
  - a traceback for the dead thread;
  - delayed messages enqueued later stay in the DQ list;
  - ordinary messages are still processed.
- **Reproduction cost:** medium, because of the timing: which Redis call meets the outage first.
- **Existing issue:** #894 / PR #895 (open) cover the `TimeoutError` misclassification. They say the consumer is "rebuilt a second later", which holds when the delay queue is empty. Thread death is not reported.
- **Priority:** 2b. Run as an N1 variant if the N1 harness allows.

### D7. Broker disconnect during shutdown

- **Relevant API:**
  - `Worker.stop()` (`worker.py:170-180`) wraps `requeue_messages` in `except BrokerConnectionError`.
  - `_RedisConsumer.requeue` (`redis.py:326-332`) raises a raw `redis.ConnectionError`, so that clause cannot match on Redis. `ConsumerThread.close()` (`worker.py:482-489`) has the same mismatch.
  - The AsyncIO middleware stops its event-loop thread only in `after_worker_shutdown` (`middleware/asyncio.py:36-38`). That thread is non-daemon (#899).
- **Documented guarantee:** C3 ("re-queued on the broker"); C2 (eventual redelivery).
- **Failure trigger:** Redis is unavailable at the requeue step of a graceful shutdown.
- **Expected outcome (docs):** the messages are eventually redelivered.
- **Suspected outcome:**
  - `Worker.stop()` raises `redis.ConnectionError`, so the warning branch is never taken;
  - consumers are not closed and `after_worker_shutdown` is not emitted;
  - the worker process exits with a traceback (exit code 1);
  - the messages wait in the dead worker's ack set until a live worker's maintenance (60 s heartbeat timeout plus a 0.1% roll per call) puts them back.
  - With AsyncIO middleware, the process may hang.
- **Severity (potential):** delayed redelivery, which is documented; an unexpected exit path; a possible hang.
- **Observability:** the exit code and logs; ack sets and heartbeats; the witness after a replacement worker starts.
- **Reproduction cost:** low with a deterministic barrier in the public `before_consumer_thread_shutdown` hook.
- **Existing issue:** none found for the requeue failure. #899 covers the non-daemon thread.
- **Priority:** 3. This was the preliminary reviewer's first choice; running it tests their hypothesis.

### D2. Graceful shutdown with prefetched messages (control)

- **Relevant API:** `Worker.stop()` requeues the work queue (`worker.py:170-180`). `ConsumerThread.close()` requeues the delay queue. `_RedisConsumer` has no `close()`, so its `message_cache` is not requeued.
- **Documented guarantee:** C1, C3.
- **Failure trigger:** SIGTERM with one message executing and others prefetched.
- **Expected outcome:** the executing message completes and is acked; the prefetched messages return to the queue.
- **Source reading:** this holds for the work queue and the delay queue. Messages still in the consumer's `message_cache` when the consumer stops are left in the ack set. That window is a few microseconds per message, because the cache drains into the work queue immediately.
- **Existing coverage:** `tests/test_redis.py::test_redis_requeues_unhandled_messages_on_shutdown` and `..._delay_messages_on_shutdown`.
- **Decision:** used as the positive control for D7. The cache race is not pursued.

### D3. Acknowledgement outcome uncertainty

- **Relevant API:**
  - `_RedisConsumer.ack` (`redis.py:306-315`) discards local bookkeeping in `finally`.
  - `ConsumerThread.post_process_message` retries a `BrokerConnectionError` every 5 s, indefinitely.
  - The Lua `ack` is conditional on set membership, so a replay is a no-op.
- **Documented guarantee:** C1, C6; at-least-once.
- **Source reading:**
  - **A lost connection.** Either the ack applied, or it is retried until it does; the replay is idempotent, so both cases converge.
  - **A `redis.TimeoutError`.** It is unmapped and reaches the generic branch, which does not retry. It logs "Although your message has been processed, it will be processed again once this worker is restarted". That prediction matches the source.
- **Existing issue:** #894 / PR #895 (open).
- **Decision:** rejected for experiments. The connection-error path is EXPECTED AT-LEAST-ONCE BEHAVIOR on this reading, and the timeout path is already reported.

### D6. Second termination signal

- **Relevant API:** `cli.worker_process.termhandler` (`cli.py:416-423`) calls `sys.exit(RET_KILLED)`; the main process forwards signals.
- **Documented guarantee:** C4.
- **Source reading:** worker and consumer threads are daemon threads, so the process exits. Messages left in the ack set come back through maintenance (C1, C2). A non-daemon thread, such as the AsyncIO event loop, makes the process hang.
- **Existing issue:** #899 and PR #900 (both open, 2026-09-25); #911 (open, 2026-10-21) restates #899.
- **Decision:** rejected as a duplicate for the hang. Recovery afterwards would be EXPECTED BEHAVIOR.

### D1. Acknowledgement before completed processing

- **Relevant API:** `WorkerThread.process_message` and `post_process_message`.
- **Source reading:**
  - The ack is issued only from the `finally` of `process_message`, after the actor returned or raised and the `after_process_message` hooks ran.
  - After SIGKILL the message stays in the ack set.
  - No path acks before the actor finishes. The nearest real problem is acking after failure handling has silently failed, which is D4.
- **Decision:** rejected, no lead.

### D5. Shutdown interrupts cleanup

- **Relevant API:**
  - `Worker.stop(timeout=--worker-shutdown-timeout)`, 600,000 ms by default;
  - the `ShutdownNotifications` middleware (`notify_shutdown`, opt-in);
  - `TimeLimit`.
- **Documented guarantee:** C3, and the "Message Interrupts" section ("To attempt to requeue the message, raise an exception to indicate failure").
- **Source reading:** shutdown waits for in-flight work up to the timeout. If the work is still running after that, the process exits and the message is redelivered later (C1).
- **Decision:** rejected. Documented and configuration-dependent.

### N3. Lost continuations from Callbacks, Pipelines and GroupCallbacks

- **Relevant API:** `Callbacks`, `Pipelines` and `GroupCallbacks` call `send`/`enqueue` from `after_process_message` (`middleware/callbacks.py:47-53`, `pipelines.py:58`, `group_callbacks.py:60`). `Callbacks` and `Pipelines` are default middleware.
- **Source reading:** these calls are swallowed exactly as in D4, so a pipeline's next step or an `on_failure` callback would be lost while the original is acked.
- **Decision:** recorded as scope of D4, not tested separately.

### N4. A fully busy worker stops heartbeating

- **Source reading:** heartbeats ride on dispatch calls, and a consumer at its prefetch limit makes no fetch calls. A worker whose delay-queue consumer still polls keeps heartbeating, though.
- **Existing issue:** #692 (open), a duplicate execution during a long task that holds the GIL.
- **Decision:** rejected. Duplicate execution is at-least-once, and the issue exists.

### N5. Lost fetch reply

- **Source reading:** if Redis ran `fetch` but the reply was lost, the ids sit in the live worker's ack set without being in memory, so they are stranded as in N1. redis-py's retries (10 with `host=`) could replay the fetch and strand the first batch.
- **Decision:** rejected for now. Reproducing it faithfully needs a reply-dropping proxy (an injected fault), and N1 tests the same stranding mechanism with a real trigger.

## Preliminary review claims, checked against the source

A preliminary read-only review supplied with the brief proposed D7, D4 and D3 in that order, with D2 as a control. Its claims, against the source above:

| Claim | Verdict (source reading) |
| --- | --- |
| `Worker.stop()` catches `BrokerConnectionError` from the shutdown requeue, logs a warning and finishes shutdown | The clause exists (`worker.py:176-179`). On Redis it cannot match, because `_RedisConsumer.requeue` raises a raw `redis.ConnectionError`. To be tested in D7. |
| Redis can recover messages of inactive workers, so a failed requeue is not automatically a defect | Agreed. Maintenance needs a live worker on the same queue, the heartbeat timeout, and a 0.1% roll per call. |
| `RedisConsumer.ack()` discards `queued_message_ids` in `finally`, even on a connection error | Correct (`redis.py:306-315`). |
| The worker retries acknowledgements after recognized connection failures | Correct (`worker.py:400-452`). `redis.TimeoutError` is not recognized (#894). |
| The Lua ack is safe to repeat | Correct: it is conditional on set membership (`dispatch.lua:191-196`). |
| Delayed-message handling publishes, then acknowledges | Correct (`worker.py:346-362`). A failure between the two duplicates the message, as in #431 (open since 2021). A failure of the publish itself strands the original, as in N1 and N2. |
| #899 and #902 exist; a separate report covers `redis.TimeoutError` | All three exist: #899 (with PR #900 and the later #911), #902 (with PR #910), and #894 (with PR #895). |
| The published docs show 2.2.0 while the tracker mentions 2.2.1 | Consistent with #896 ("2.2.1 missing from docs", open). PyPI's latest is 2.2.1. |
| Ranking D7 > D4 > D3 | Reordered to D4 > N1/N2 > D7, for three reasons. D4 has a direct path to permanent loss and a prior description. N1 contradicts a maintainer statement. D7's immediate failure is louder than claimed, and its recovery uses the documented heartbeat mechanism. D3 is covered by #894. |

## Experiment selection

1. **D4.** Is a message with retries remaining lost when its retry cannot be enqueued?
2. **N1, with N2 as a variant.** Are prefetched delayed messages recovered after a Redis restart while the worker stays alive?
3. **D7, with D2 as its control.** What happens at the shutdown requeue when Redis is unavailable, and are the messages recovered?

Every experiment uses its own `redis-server` process, with append-only persistence and `appendfsync always`. The reasons and the full environment are in [README.md](README.md).
