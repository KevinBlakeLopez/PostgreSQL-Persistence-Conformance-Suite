# Adversarial verification of F1-F4

Investigation date: 2026-10-24 (PDT; 2026-10-25 UTC). Written by: Claude Opus 5.5 (max).

This is the original investigator's own attempt to falsify F1-F4, done at the user's request before anything goes upstream. Labels used below:

- **Observed:** a recorded run under `outputs/verify/`.
- **Source reading:** an interpretation of the code, not observed at runtime.
- **Not run:** a question that remains open.

Status: complete. It began on battery power at 1-10%, so the experiments most likely to change a conclusion were run first.

## What was tested, and with what

- **Dramatiq builds.** 2.2.1 from PyPI, and `master` at `08d711a7611077e3d07ce1006349bc9342ada6e8`. `git ls-remote` on 2026-10-25 at about 04:20 UTC shows that is still the tip of `master`. The files involved are byte-identical in the two builds (SHA-256 in every `result.json`). No other version was tested, and no claim here is about one.
- **Other components.**
  - redis-py 8.1.0.
  - Redis 8.6.2 (Homebrew), `appendonly yes`, `appendfsync always`, on study-only loopback ports.
  - CPython 3.13.11, macOS 26.6.2 arm64.
  - The stock `dramatiq` CLI with `--processes 1 --threads 1`, plus a second concurrent worker where stated.
- **New instrumentation** in `reproductions/`. None of it modifies Dramatiq.
  - **`faultproxy.py`** is a TCP proxy between the worker and Redis. It can:
    - forward one specific Lua dispatch call and drop its reply (Redis accepted it; the reply was lost);
    - close a connection before a call reaches Redis;
    - blackhole all traffic (a partition).
  - **The independent observer** is `redis-cli MONITOR` on the real Redis port, logged to `monitor-*.log` in each run. It shows every dispatch call Redis actually executed, with its command and queue arguments.
  - **A state reporter** (`PPCS_REPORT_STATE=1`) is a thread inside the worker. Once a second it reports each consumer thread's liveness, its in-memory delay-queue size, and the non-daemon threads.
- **The experiments** are `reproductions/verify.py` and `reproductions/run-verify.sh`, with evidence under `outputs/verify/`.

**Re-running it.** Use the environments from the README's "Running it" section, plus one per extra build. `run-verify.sh` expects these venv names: `rel221`, `fix-d4-a1`, `fix-d4-a2`, `fix-redis-reconnect`, `pr895`.

```sh
reproductions/run-verify.sh <venvs dir> priority     # one run of each decisive variant
reproductions/run-verify.sh <venvs dir> rest         # repetitions and the rest
<venv>/bin/python -I reproductions/verify.py f2 --variant sigstop --reps 2 --ports 56396,56397
<venv>/bin/python -I reproductions/verify_summary.py  # writes outputs/verify/SUMMARY.md
```

Variant names are listed in `VARIANTS` at the bottom of `verify.py`. Proxy variants need a third port, for example `--ports 56391,56392,56393`.

**Regression tests and Dramatiq's suite** run in a disposable `python:3.13-slim` container with the study mounted at `/study`:

```sh
/study/reproductions/linux/setup-regression.sh
/study/reproductions/linux/run-regression.sh
/study/reproductions/linux/run-suites.sh master fix-d4-a1 ...
```

The PR #895 tree is `master` plus `git apply --include='dramatiq/brokers/redis.py'` of `gh pr diff 895`, at head `8dd09c1`.

## Summary table

| Finding | Original claim | Strongest attempted falsification | Result | Revised confidence | Remaining uncertainty |
| --- | --- | --- | --- | --- | --- |
| F1 | A failed message whose retry can't be enqueued is acked and deleted (Redis) | <ul><li>Let Redis accept the enqueue and drop only the reply (proxy).</li><li>Fail only the ack after a successful enqueue, with and without a worker kill.</li><li>The other `Retries` branches.</li><li>MONITOR as an independent observer.</li></ul> | **Narrowed.** Lost only when the enqueue never reaches Redis (21/21). <ul><li>Lost reply: the retry exists (3/3 URL form; runs twice 3/3 host form).</li><li>Ack failure: no loss (3/3; twice if killed, 3/3).</li><li>`Retry` and the last retry are lost; exhausted and `throws` are dead-lettered.</li></ul> | High, for the narrowed claim | RabbitMQ (source reading only); `Callbacks`/`Pipelines`; how often the timing occurs in production |
| F2 | Delayed messages a live worker fetched are stranded after a reconnect until it exits | <ul><li>Ownership seen from both sides (MONITOR, the worker's own memory).</li><li>A second live worker.</li><li>The owner's heartbeat expiring (SIGSTOP).</li><li>A short-timeout race.</li></ul> | **Qualified.** Stranded while the owner lives and keeps heartbeating (14/14, and 3/3 with a second default-timeout worker). Recovered when another worker's short-timeout maintenance wins the race (1/3) or the owner stops heartbeating (2/2). | High, with the condition | Outages longer than 60 s under default settings with many workers (recovery is probabilistic) were not measured |
| F3 | An unmapped Redis error kills the delay-queue consumer thread | <ul><li>A real network blackhole.</li><li>Liveness reported from inside the worker.</li><li>PR #895 alone.</li><li>Two workers.</li></ul> | **Survived, and wider than claimed.** Blackhole 3/3; never restarted. One pause killed both workers' consumers (3/3). #895 alone: no death, but stranding (3/3). | High | The host-form broker with a stall over 110 s; the enqueue-path variant |
| F4 | A requeue failure at shutdown aborts `Worker.stop()`; hang with AsyncIO | <ul><li>No harness barrier.</li><li>A `TimeoutError`.</li><li>AsyncIO installed first.</li><li>Identifying the thread that holds the process.</li></ul> | **Survived.** Exit 1, or a hang with AsyncIO, in every variant, after correcting my own sequencing error. Only the event-loop thread holds the process. | High | The exit-code policy is a maintainer choice |
| Fix a1 | Dead-lettering is a safe correction | The nack fails too and the worker dies; what the dead letter holds | Safe: recoverable (3/3). The dead letter keeps the original payload, without the traceback. | High | It is a change of semantics |
| Fix a2 | Retrying the enqueue is a correction | A lost reply; shutdown; `actor.send()`'s exception type | **Regressions:** duplicates (3/3), an API change, blocking. Bounded at shutdown. | High | - |
| Reconnect fix | One fix for F2-F4 | Ownership expiry; a lost promotion reply; repeated outages; an ETA during the outage; shutdown during the outage | **Duplicates on ownership expiry (2/2).** Otherwise it works. | High | An ownership-checked promotion was not implemented |
| Part 1 alone | Mapping the `requeue` errors fixes F4 and F3's thread death without duplicates | F4 without a barrier, with and without AsyncIO; F3 under a pause; regression tests in the container | F4 fixed: exit 0 with the documented warning, `after_worker_shutdown` ran, no hang (1/1 each). F3's thread survives and later delayed messages run (3/3), but the messages held during the stall are stranded (3/3) (the worker's own delay queue is 0, its ack set holds 3). No duplicates: nothing is retained. Regression tests: F4 passes; F3 fails only at "the delayed message held during the stall never ran" (as with PR #895); F1 and F2 fail, because Part 1 does not address them; every control passes. | Medium to high: 3 F3 runs and 1 F4 run per variant, plus the regression tests | It leaves F2 for a separate change |

## The eight questions, per finding

| Question | F1 | F2 | F3 | F4 |
| --- | --- | --- | --- | --- |
| 1. Production-reachable? | Yes, with ordinary infrastructure faults: a refused or reset connection at the retry enqueue, coinciding with a failing actor | Yes, with any Redis outage longer than redis-py's retry window while delayed messages are held | Plausible but uncommon: a stall or partition longer than two socket timeouts | Plausible: stopping workers while Redis is unavailable |
| 2. Dramatiq's normal public API and paths? | Yes: the stock CLI, default middleware, `actor.send()` | Yes: `send_with_options(delay=...)` | Yes | Yes: SIGTERM to the CLI |
| 3. Could the fault injection itself cause it? | No. The fault is a real Redis restart. The barrier only times the actor's failure. `fault-actor-redis` needs no instruction to fail. The verification's lost-reply and ack-fail variants used the proxy and a barrier, and narrowed the claim rather than producing it. | No. Real restarts; MONITOR and the worker's own state agree. | No. The blackhole and `CLIENT PAUSE` both do it; no Dramatiq code is touched. | No. The shutdown barrier is not needed (`nobarrier`); with my sequencing error corrected, every variant agrees. |
| 4. Explicit guarantee, implied invariant, or expectation? | Explicit (C5) | Strong implied invariant; arguably within C2's "eventually"; contradicts M1 | Strong implied invariant (the run loop is designed to restart) | Implied invariant (the documented warning branch), plus an undesirable hang |
| 5. Does a recovery mechanism undo the consequence? | No Dramatiq mechanism; logs record the actor and arguments | Yes, eventually: when the owner exits or stops heartbeating, or another worker wins the race | Held messages: as F2. New delayed messages: other workers can take them, unless their consumers died too (the two-worker run). | Yes: the messages are recovered by heartbeat maintenance |
| 6. Alternative explanations? | Redis losing data: ruled out by AOF `always`, `control-kill` and the final restart. Retry delays: 20 s observed against a 1-2 s backoff. | Delayed execution: ruled out (300 s with defaults; 660 s in an external run). Visibility: ruled out (the in-worker state). | Slow recovery: ruled out (the thread is reported dead, and no restart is in the code) | The harness: ruled out (`nobarrier`); outstanding tasks: ruled out (only the loop thread) |
| 7. Does the correction restore the invariant? | a1 and a2: yes | Reconnect fix: yes while ownership holds | The reconnect fix or Part 1: yes, for the thread | The reconnect fix or Part 1: yes |
| 8. Could the correction cause something worse? | a2: duplicates, an API change, blocking. a1: no. | Reconnect fix: duplicates when ownership expires (2/2) | Part 1: no | An exit-code change (policy) |

## F1: a failed message whose retry can't be enqueued is acknowledged and deleted

### A. Recovery mechanisms (source reading, `dispatch.lua` and `brokers/redis.py` at `08d711a`)

- **`ack` deletes the payload.** It removes the id from the worker's ack set, and then deletes the payload with `hdel` (lines 191-196).
- **Maintenance can't bring it back.** It requeues an id only if its payload still exists (`hexists`, lines 119-121), so it cannot resurrect an acked message.
- **No dead-letter entry is made.** Only `nack` moves a payload to `.XQ` (lines 200-212), and the worker nacks only if `message.failed` is set. `dead_message_ttl` only prunes `.XQ`.
- **Nothing else keeps a copy.** The Redis broker keeps no other copy of the payload, so once acked, only an external backup or the application could recover it.
- **Restarting a worker can't help either.** The Redis broker re-fetches only what is in queue lists, ack sets and payload hashes.

Observed in the original runs:
- Nothing came back after a further Redis restart from the append-only file (8 of 8).
- Nothing came back with a replacement worker running maintenance on every call.

**RabbitMQ (source reading only, not run).**
- `_RabbitmqConsumer.ack` acknowledges by delivery tag on the consumer's channel. On a connection loss RabbitMQ requeues unacked deliveries itself (`_RabbitmqConsumer.requeue`'s docstring).
- After a reconnect, the worker's retried ack meets a new consumer with an empty `known_tags` set. It logs "Failed to ack message: not in known tags." and does nothing.
- So an outage that kills the consumer's connection would get the original redelivered on RabbitMQ, not deleted. F1's loss on RabbitMQ would need the retry publish to fail while the consumer's channel stays up and acks. That condition is narrower, and was not established here.
- **F1 is therefore stated for the Redis broker only.**

### B. Failure timing (observed)

Each outcome was induced at a real protocol boundary and observed three ways:
- **MONITOR:** what Redis executed;
- **the witness:** what ran;
- **snapshots:** what Redis held.

All runs: 2.2.1, macOS. Counts are in `outputs/verify/SUMMARY.md`.

| # | Scenario | How it was induced | Did Redis execute the retry enqueue (MONITOR)? | Original | Retry | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Enqueue never reaches Redis | Redis process stopped when `Retries` enqueues; connection refused | No | Acked: payload deleted | None | **Lost**: 21/21 original runs (16 macOS, 5 Linux). The replacement found nothing, and nothing came back after a further restart. |
| 2a | Redis accepts the enqueue, reply lost; URL form (no client retries) | Proxy forwards `EVALSHA … enqueue … default.DQ`, drops the reply, closes the connection | Yes, once | Acked | In `default.DQ`; runs | **Not lost.** The retry ran once. Dramatiq still logged `[CRITICAL] Unexpected failure in after_process_message`, a failure report for a retry that exists. Observed in 3/3. |
| 2b | Same, host form (redis-py 8.1.0 retries by default) | Same | Yes, **twice**: redis-py re-sent the call on a new connection | Acked | Id in `default.DQ` twice | **Not lost; the retry ran twice.** Nothing was logged. Observed in 3/3. |
| 3a | Retry accepted and acknowledged, then the original's ack fails; Redis returns | A barrier after the successful enqueue; Redis stopped before the ack, restarted 8 s later | Yes | The ack was retried every 5 s, then succeeded | Runs | **Not lost, no duplicate.** Observed in 3/3. |
| 3b | Same, but the worker is killed during the outage | Same, plus SIGKILL | Yes | Not acked; a replacement redelivered it | Runs | **Not lost; the work ran twice** (original and retry). At-least-once delivery permits this. Observed in 3/3. |

**What this changes.**
- **F1's loss is specific to scenario 1:** the retry enqueue failed *before Redis received it*.
- **When Redis received the enqueue,** the work survived, either once or twice.
- **The CRITICAL log line is wrong in both directions.** In scenario 1 it is the only trace of a real loss. In scenario 2a it reports a failure that did not happen.

**About scenario 2.** It used an injected fault: the proxy let the command through and discarded Redis's reply. Its production equivalent is a connection reset after Redis has written the reply, during a failover or a network drop. That is plausible but rare, and it is not a production-confirmed observation.

**A side observation, not pursued** (the brief excludes new defect hunts):
- Scenario 2b is a general property of `RedisBroker(host=...)` under redis-py 8.x. Any enqueue whose reply is lost is re-sent by redis-py and lands twice, because the Lua `enqueue` (`rpush`) is not idempotent.
- At-least-once delivery permits this.

### C. Middleware and configuration

`Retries.after_process_message` (`middleware/retries.py:97-148`) has three outcomes for a failure (source reading):

- **`throws`, exhausted retries, or `retry_when` returning False:** it calls `message.fail()`, so the worker nacks into the dead-letter queue, and no enqueue is involved.
  - An `on_retry_exhausted` callback is sent *after* `fail()`. If that send fails, it is swallowed, but the message is already marked failed.
- **Otherwise,** it enqueues the retry. That includes `dramatiq.Retry(delay=...)`, every retry before the last, and the last allowed retry. Only this branch reaches F1.
- **Middleware order cannot change this.** `Retries` is last in `default_middleware`, so `emit_after` runs its hook first. `emit_after` swallows the exception whatever runs afterwards, and the worker's ack decision reads only `message.failed`.

Observed, Redis down when `Retries` runs:

| Variant | Branch | Outcome |
| --- | --- | --- |
| `retryexc`: actor raises `dramatiq.Retry(delay=1000)` | enqueue | **Lost**: acked with no retry or dead letter (3/3); CRITICAL logged |
| `lastretry`: `max_retries=1`, attempt 0 fails | enqueue of the final retry | **Lost** (3/3); CRITICAL logged |
| `exhausted`: `max_retries=1`, attempt 1 fails | `message.fail()` | Dead-lettered (1/1); not affected |
| `throws`: `ValueError` listed in `throws` | `message.fail()` | Dead-lettered (1/1); not affected |

**RabbitMQ.** See A. No run.

### D. The candidate fixes

Observed on macOS, builds `master 08d711a + fix`. Counts are in `outputs/verify/SUMMARY.md`.

| Fix | Challenge | Observed | Reading |
| --- | --- | --- | --- |
| a1 (dead-letter) | The original fault (earlier study runs) | Dead-lettered, 7/7. Still in `default.XQ` after a final Redis restart. | No loss |
| a1 | `nack` fails as well, and the worker is SIGKILLed during the outage (`a1-nackfail-kill`) | The original was not nacked and stayed in the dead worker's ack set. The replacement redelivered it and it ran once: 3/3. | `message.fail()` reliably leads to a nack, retried every 5 s on connection errors. If the worker dies first, the message stays recoverable. |
| a1 | What the dead letter holds | The payload as originally stored: actor, arguments, options, `retries: 0`. No traceback of this failure, because `nack` copies the stored payload (`dispatch.lua:200-212`). | Enough to re-enqueue by hand, within `dead_message_ttl` (7 days). It changes the outcome for a message that had retries left, from retried to dead-lettered. |
| a1 | Normal retries; Dramatiq's tests | Unchanged (3/3); regression and control tests pass | |
| a2 (keep retrying the enqueue) | The original fault (earlier study runs) | The retry was enqueued once Redis returned, then the original acked; attempt 1 completed, 7/7 | No loss |
| a2 | Reply lost after Redis accepted the enqueue, URL form (`a2-lostreply`) | **The retry ran twice in 3/3.** Unpatched code ran it once in 3/3 under the same fault. | a2 re-enqueues with a new Redis id when a reply is lost. **New duplicates.** |
| a2 | SIGTERM during the outage, `--worker-shutdown-timeout 4000` (`a2-shutdown`) | Exit 0 after the shutdown timeout. The original was never acked; a replacement redelivered it and it ran once: 3/3. | Shutdown can interrupt it. The block is bounded by the outage or by the shutdown timeout. No loss. |
| a2 | Blocking | In the run inspected, the worker thread stayed in `Retries` for the whole 30 s outage, logging "Failed to enqueue a retry … will be retried in 5 seconds" | Lost throughput during outages, in the same style as the existing ack loop |
| a2 | What `actor.send()` raises during an outage | Unpatched 2.2.1: `redis.exceptions.ConnectionError`. With a2: `dramatiq.errors.ConnectionClosed`, **not** a `redis.ConnectionError` (`f1send`, 1 run each) | API change for producers on Redis |
| Both | Combined with the reconnect fix | Every regression test and control passes | No interaction failure |

**Verdict.**
- **a1 is the safer minimal correction:** no new duplicates, no API change, no blocking. Its cost is semantic: during an outage, a message with retries left goes to the dead-letter queue and needs a manual requeue.
- **a2 keeps retry semantics,** but adds duplicates when a reply is lost, blocks worker threads, and changes an exception type.
- **Neither is ready as a PR** without the maintainers choosing the semantics. a1 is ready for a patch discussion.

## F2: delayed messages stranded in a live worker's ack set after a reconnect

### A. Ownership (source reading, checked against MONITOR and the state reporter)

- **Where the message is.** A delayed message's id sits in the `dramatiq:<queue>.DQ` list. Its payload sits in `dramatiq:<queue>.DQ.msgs`.
- **How it enters the ack set.** `fetch` moves the id from the list into `dramatiq:__acks__.<broker_id>.<queue>.DQ` in the same Lua call (`dispatch.lua:154-173`).
- **How it leaves.** Only three ways:
  - `ack` (promotion, then acknowledging the DQ copy);
  - `requeue`;
  - maintenance, run by some worker.
- **Who owns it.** Ownership is keyed by `broker_id`, a `uuid4` created once per `RedisBroker` instance (`brokers/redis.py:108`). In the CLI that means once per worker process. All consumer threads of that process share it, and it survives consumer recreation after an error.
- **What heartbeats mean.** The heartbeat is a score in `dramatiq:__heartbeats__`, refreshed by every dispatch call of that `broker_id` (`dispatch.lua:58`).
- **When maintenance recovers.** Maintenance treats a worker as dead when its heartbeat is older than the *calling* worker's `heartbeat_timeout` (`dispatch.lua:111`). It then requeues that worker's ack set for the queue named in the call, on a random roll per call (`redis.py:238-242`).

**Observed: two independent views.** The second Redis key below is exactly as quoted.

- **Worker 1's own memory.** The state reporter runs inside worker 1. It shows its delay-queue consumer's in-memory queue going from 3 to 0 at the connection error, while Redis still held all three ids in `dramatiq:__acks__.<worker 1>.default.DQ`. This happened in every unpatched F2 run with the reporter where nothing ran while worker 1 lived: 3/3 in `secondworker` and 2/3 in `secondworker-shorthb` (`worker1_dq_delay_queue_series` in each `result.json`). So the stranded state is real, not a visibility or timing artifact: the worker no longer holds the messages, and Redis still assigns them to it.
- **MONITOR, including commands run inside Lua** (`[0 lua]` lines). Example: `f2/secondworker-host/20261025T042846Z-rep1`, id `ba5bcdbe-…`.
  1. At `1792902528.03` it is enqueued, fetched, and `sadd`-ed into `dramatiq:__acks__.105a78d9-….default.DQ` (worker 1).
  2. No command touches it for 65 s, through the outage and the observation window, although a second live worker ran maintenance on every call.
  3. At `1792902593.90`, after worker 1 exited, the replacement's maintenance runs `hexists`, then `rpush dramatiq:default.DQ`, then `sadd` into its own set; then it acks.

### B. Recovery conditions (observed)

| Event | Recovers the stranded messages? | Evidence |
| --- | --- | --- |
| Redis reconnecting; consumer recreated ("Restarting consumer") | No | Every unpatched fault run: 14/14 in the original study, plus every verify run |
| Maintenance by the owning worker itself, on every call, 2 s heartbeat timeout | No: it refreshes its own heartbeat first (`dispatch.lua:58`) | `fault-aggressive`, 14/14 |
| A second live worker, maintenance on every call, 60 s heartbeat timeout (Dramatiq's default timeout) | No, 3/3 | `secondworker` |
| A second live worker, maintenance on every call, **2 s** heartbeat timeout, after a 15 s outage | **Yes in 1/3.** MONITOR shows worker 2's first `fetch` after Redis returned ran maintenance (timeout `2000`) and requeued worker 1's set before worker 1's next call refreshed its heartbeat. No in 2/3. | `secondworker-shorthb` |
| The owning worker stops heartbeating while alive: SIGSTOP 6 s, while a second worker has a 2 s timeout | **Yes, 2/2.** About 2 s into worker 1's pause, worker 2's maintenance deleted worker 1's delay-queue ack set (MONITOR: a Lua `del` called from worker 2's `fetch`) and ran all three messages, once each. There were no duplicates, because worker 1 had already dropped them from memory. | `sigstop` |
| The owning worker exits gracefully | Not by itself: the ids stay in its ack set after exit 0 | Every run |
| A replacement or restart (new process) | Yes, after the heartbeat timeout plus a maintenance roll: immediately with fast maintenance; 293 s in the one default-maintenance sample (F4) | Every run |

**What this changes.**
- **"Stranded until the worker exits" is too strong as stated.** The precise statement: the messages stay stranded while the owning worker process lives and keeps calling Redis, *unless* another worker's maintenance runs, between Redis returning and the owner's first call, with a heartbeat timeout shorter than the outage.
- **Under Dramatiq's defaults** (60 s timeout, a 1-in-1,000 maintenance roll) that escape needs an outage longer than 60 s *and* a maintenance roll in the first moments after recovery. So with defaults, stranding is the expected outcome.
- **Nothing here is mathematically permanent.** Recovery follows when the worker exits and another worker's maintenance runs.

### C. The proposed fix (`fix-redis-reconnect`), challenged

All runs observed on macOS. The fix rests on one assumption: messages a Redis worker still holds after a reconnect are still owned by it, because ownership is keyed by `broker_id`, not by the consumer object.

That holds while the worker's heartbeat stays fresh:
- Acks through the newly created consumer work, because MONITOR shows the `srem` aimed at the same `dramatiq:__acks__.<broker_id>.default.DQ` key.
- Delayed jobs ran once on the live worker in every fix run that did not lose ownership.

**It fails when ownership expires while the worker still holds the messages:**

| Challenge | Observed | Reading |
| --- | --- | --- |
| Another worker recovers the messages while the owner still holds them: SIGSTOP 6 s, the other worker on a 2 s heartbeat timeout (`sigstop`) | **Each message ran twice, 2/2.** Worker 2 ran all three during the pause. Within 0.2 s of SIGCONT, worker 1 promoted its retained copies and they ran again. Unpatched code ran each once, 2/2. | **A new duplicate.** The retained copy outlives its Redis ownership. Dramatiq already duplicates in-flight messages in this situation, but the fix extends it to delayed messages. |
| A second worker with a 2 s heartbeat timeout after a 15 s outage (`secondworker-shorthb`) | Each ran once, 2/2. In both runs worker 1 refreshed its heartbeat before worker 2's maintenance ran. | The same risk as above, when the race goes the other way |
| The promotion's reply is lost after Redis accepted it (`promotion-lostreply`) | One message ran twice in both builds. With the fix, the second run came 2.7 s later (put back, requeued, promoted again). Unpatched, it came 37 s later, after worker 1 exited and the replacement's maintenance recovered the stranded entry. | **No extra duplicate**; the fix moves it earlier. This is the same window as #431. |
| The ETA passes during the outage, so the promotion fails (`eta-during-outage`) | With the fix, each ran once after Redis returned. Unpatched, they were stranded (F2). | Works |
| Two outages in a row (`repeated`) | Each ran once on worker 1, at its ETA (1/1) | Works across repeated reconnects |
| SIGTERM during the outage (`shutdown-during-outage`) | Worker 1 exited 0 while Redis was down. The three ids stayed in its ack set, because the requeue in `close()` failed, was mapped, and kept them. The replacement ran each once (1/1). | Works. Recovery after a shutdown during an outage still relies on heartbeat maintenance, as without the fix. |
| Network blackhole (F3's trigger) | No thread death; worker 1's own memory shows the three held messages kept (`delay_queue: 3`) | Works |

**What would make the fix safe:** an ownership-checked promotion. A Lua command that promotes a delayed message only while its id is still in the caller's ack set would turn the late copy's promotion into a no-op. PR #859 (closed by its author) proposed exactly that, for #431.

**Verdict.** Without it, `fix-redis-reconnect` swaps indefinite stranding for occasional duplicates whenever the owner's heartbeat expires while the owner is alive. At-least-once delivery permits that, but it should not be proposed as is.

## F3: the delay-queue consumer thread dies on an unmapped Redis error

**The exact path, observed** in the tracebacks of every death:

1. `_RedisConsumer.__next__` raises `redis.exceptions.TimeoutError: Timeout reading from socket` from the fetch. It is not mapped (`brokers/redis.py:372-373` catches only `redis.ConnectionError`).
2. `ConsumerThread.run` takes the generic `except Exception` branch ("Consumer encountered an unexpected error.") and calls `close()`.
3. `close()` drains the delay queue and calls `requeue`, which raises a second `TimeoutError` (`brokers/redis.py:332`).
4. `close()`'s `except BrokerConnectionError` (`worker.py:488`) does not match. The exception leaves the `except` block, and `run()` ends ("Exception in thread …").

**Is it intentional?** Nothing in the code or tracker suggests the exclusion is deliberate. #894 reports the misclassification; no maintainer has replied.

**Supervision (source reading).** `Worker` never checks its consumer threads, and the CLI supervises only processes. Observed: the state reporter shows `default.DQ` with `alive: false` from the death until the worker stops. No restart happened in any run.

| Question | Observed |
| --- | --- |
| Do ordinary messages keep processing? | Yes, in every run |
| Do delayed messages sent later stop? | On that worker, yes: the probe sat in `dramatiq:default.DQ` in every run |
| Do the messages held in memory come back? | Only after the worker exits and another worker's maintenance runs |
| Another production-reachable trigger | **A network blackhole through the proxy** (`f3/blackhole`, URL form): the same death in 3/3. So the trigger is not specific to `CLIENT PAUSE`. |
| Two workers holding delayed messages, one 15 s pause | **Both delay-queue consumers died** (3/3): both report `alive: false`, and "Exception in thread" is in both logs. The later delayed probe stayed in `dramatiq:default.DQ` with no live consumer anywhere, while ordinary jobs ran. So one Redis stall can stop delayed work, retries included, on every worker that held delayed messages. |

**Separating the effects:**
- **(1) Thread termination** is F3's own defect.
- **(2) Stranding of the held messages** is the same ack-set mechanism as F2.
- **(3) Redis availability** recovered in every run: Redis was back, and ordinary work ran.
- **(4) Process health:** the process stayed up, heartbeated, and exited 0 on SIGTERM. So a supervisor sees a healthy worker.

**PR #895, evaluated on its own**, with its `dramatiq/brokers/redis.py` change applied to `08d711a`:

| Check | Observed |
| --- | --- |
| `CLIENT PAUSE` (earlier study runs) | No death (2/2), but the held messages are stranded |
| Network blackhole | No death (consumer alive), and the later delayed probe ran (1/1); the held messages are still in the ack set (1/1) |
| Regression test `test_f3_…` | **Fails** on its last assertion: "the delayed message held during the stall never ran". The thread-alive and probe assertions passed. |

So #895 removes the thread death, and in exchange exposes F2. It is a necessary part of a fix, but not sufficient.

## F4: shutdown requeue failure aborts `Worker.stop()`; AsyncIO hang

**Shutdown ordering, from source and the logs.** `Worker.stop()` runs in this order:

1. emit `before_worker_shutdown`;
2. stop the worker threads, then `join_all` them, up to `--worker-shutdown-timeout`;
3. stop and join the consumer threads;
4. requeue the work queue (`worker.py:170-180`);
5. `close()` each consumer;
6. emit `after_worker_shutdown`.

If step 4 raises, steps 5 and 6 are skipped. The AsyncIO middleware stops its event-loop thread only in step 6 (`middleware/asyncio.py:36-38`). That thread is non-daemon (#899).

| Variant | What it removes or changes | Observed |
| --- | --- | --- |
| Earlier study runs | The study's shutdown barrier; Redis stopped at the requeue | Exit 1 in 11/11; hang with AsyncIO in 4/4 |
| `nobarrier` | **No barrier.** Redis is already down when SIGTERM arrives; one job running, one prefetched; `--worker-shutdown-timeout 3000` | Exit 1 in 2/2; `after_worker_shutdown` skipped. The same traceback, through `worker.py:177` and `brokers/redis.py:332`. |
| `nobarrier-asyncio` | The same, with AsyncIO | **Hung** in 3/3 |
| `pause-boundary` | A **`TimeoutError`** instead of a refused connection (`CLIENT PAUSE … WRITE` at the requeue, URL form) | Exit 1 in 2/2; `after_worker_shutdown` skipped |
| `pause-boundary-asyncio` | The same, with AsyncIO | Hung in 2/2 |
| `barrier-asyncio-first` | AsyncIO installed *first* in the middleware list instead of last | Hung in 2/2 |
| Fixed build, `nobarrier-asyncio` | With `fix-redis-reconnect` | Exit 0; `Failed to requeue messages on queue 'default'` logged; `after_worker_shutdown` ran; no hang (1/1) |

**An error in this verification, corrected.** The first runs of `pause-boundary`, `pause-boundary-asyncio` and `barrier-asyncio-first` exited 0. My new harness branch had released the first job before `Worker.stop()` began, so the worker also processed the prefetched job, and there was nothing to requeue. Their logs show no "Re-enqueueing" line.

Those runs are kept, excluded, in `outputs/verify/_invalid-harness-sequencing/`. The branch now waits for `before_worker_shutdown`, and the results above are from the re-runs.

**What the hang depends on.**
- **Middleware order and harness barrier:** neither, per the variants above.
- **The Redis exception type:** either type works, as long as it escapes `requeue` unmapped.
- **No outstanding asyncio task is involved.** No async actor ran in any of these runs. During the hang, the reporter's last list of non-daemon threads is `["MainThread", "Thread-2"]`. In the same runs without AsyncIO, only `MainThread` is listed, in all 4 such runs (`nobarrier` 2, `pause-boundary` 2). So `Thread-2` is the event-loop thread.
- **The worker thread keeps retrying the first job's ack** about every 9 s during the hang. It is a daemon thread, so it does not hold the process.

**Is exit 0 after a failed requeue appropriate?**
- **Not necessarily.** The documented codes are 0 "exits gracefully" and 1 "is killed".
- **What the code intended.** Shutdown with a failed requeue is not fully graceful: work is left for heartbeat recovery. But the original author's handler logs a warning and continues, which implies a normal exit.
- **What matters for correctness.** It is completing shutdown, so that consumers close and `after_worker_shutdown` runs; that is what ends the hang. The exit code is a separate policy choice.
- **An alternative fix** finishes shutdown and still exits non-zero. Report both options, and let the maintainers choose.

## Cross-cutting checks

### A. Version validity

Tested: 2.2.1 (PyPI) and `master` `08d711a`, which was still the tip of `master` on 2026-10-25 (`git ls-remote`). Claims are limited to those two builds.

The verification runs used 2.2.1. The regression tests ran on `08d711a`. The two are byte-identical for the files involved.

### B. Redis configuration

| Setting | Used | Needed for the result? |
| --- | --- | --- |
| Redis server | 8.6.2 (macOS), 8.0.2 (Linux) | No dependence seen |
| Persistence | `appendonly yes`, `appendfsync always` | Only to rule out the broker losing data across a restart. With Redis's default persistence, a restart can lose recent writes on its own, which would confound F1 and F2. |
| redis-py | 8.1.0. The host form retries 10 times with backoff; the URL form never retries; both have a 5 s socket timeout | **F1:** the loss happens with either form. With the host form, the outage must outlast about 3 s of client retries. **F3:** with the URL form the stall must exceed 2 × 5 s; with the host form about 2 × 55 s (source; not run). |
| Heartbeat timeout, maintenance chance | Dramatiq's defaults (60 s, 1 in 1,000) or, in "aggressive" variants, 2 s and every call | **F2** reproduces with the defaults (300 s, plus 660 s in the unfinished external review). Aggressive settings only strengthen the claim. |
| Queues, workers | One queue (`default`), one process with one thread; two workers where stated | Larger prefetch counts change how many messages are affected, not the mechanism (source) |

### C. Production reachability (conservative)

| Finding | Shortest realistic sequence | Classification |
| --- | --- | --- |
| F1 | An actor fails while Redis is unreachable in a way that refuses or resets connections before the command is sent: a restart, a failover, or the network dropping. The outage must outlast about 3 s with the host form, and any blip suffices with the URL form. Coincidence is likely when the actor's failure is caused by the same outage. | **Ordinary transient infrastructure failure**, in that correlated case. It needs the outage and a failing actor at once. |
| F2 | Any Redis outage that outlasts redis-py's retry window while a worker holds delayed messages (scheduled work, or retries due within the delay-prefetch window), as long as that worker keeps running afterwards | **Ordinary transient infrastructure failure** |
| F3 | A Redis stall or network partition longer than two socket timeouts (10 s with the URL form) while the delay-queue consumer holds delayed messages. Shown with `CLIENT PAUSE` and with a proxy blackhole (the partition model). | **Plausible but uncommon timing** |
| F4 | A worker is asked to stop while Redis is unavailable and messages sit prefetched in its work queue: for example, workers restarted during a Redis incident. Shown without any shutdown barrier (`nobarrier`). | **Plausible but uncommon timing**. Ordinary during a Redis incident for anyone who restarts workers then. |

### D. Contract verification

The strongest authoritative source for each finding:

| Finding | Strongest source | Exact text (source location) | Classification |
| --- | --- | --- | --- |
| F1 | Retry and dead-letter documentation | "Dramatiq automatically retries failures with exponential backoff." (`docs/source/guide.rst:217-218`); "Once a message has exceeded its retry or age limits, it gets moved to the dead letter queue" (`guide.rst:267-268`) | **Explicit documented contract violation.** A failure with retries left is neither retried nor dead-lettered. The often-quoted "Messages are only ever acknowledged … after they have been successfully processed" (`advanced.rst:174-175`) is loose: normal retries also ack a failed original, after enqueueing its replacement. So it is supporting evidence, not the main contract. |
| F2 | Recovery documentation, and the maintainer on #527 | "the messages it pulled from the broker will eventually be re-delivered to it (assuming it recovers) or another worker" (`advanced.rst:177-180`). Maintainer, #527: "some time (the heartbeat timeout) has to pass until those messages are put back" | **Strong implied correctness invariant violation.** The worker recovered and was never re-delivered the messages. They reach another worker only after it exits, which arguably still satisfies the letter of "eventually". The behavior contradicts the maintainer's explanation. |
| F3 | The code's own design | `ConsumerThread.run`: "While the consumer is running (i.e. hasn't been shut down), try to restart it" (`worker.py:335-336`) | **Strong implied correctness invariant violation.** There is no documentation of consumer-thread supervision. |
| F4 | The handler's intent, and the exit codes | `worker.py:176-179` logs "Failed to requeue messages on queue" and continues. Exit codes: "`0` Returned when the process exits gracefully"; "`1` Returned when the process is killed." (`advanced.rst:312-313`) | **Strong implied invariant violation** (the documented handler is unreachable on Redis), plus **undocumented but undesirable** behavior (the hang). Whether exit 1 is wrong is a judgment call; see F4. |

### E. Independence

Four findings, three underlying defects:

1. **Swallowed retry enqueue (F1).** `Retries`' enqueue failure is swallowed by `emit_after`, and the worker then acks. This is broker-independent code; only the Redis consequence was shown.
2. **Delay-queue reset on Redis (F2).** On a connection error, the consumer thread discards its in-memory delay queue, a RabbitMQ assumption. It is also F3's consequence once the `TimeoutError` is mapped (PR #895).
3. **Unmapped `requeue` errors (F3, F4).** `_RedisConsumer.requeue` lets Redis errors escape unmapped, so the `except BrokerConnectionError` handlers in `ConsumerThread.close()` and `Worker.stop()` cannot catch them.
   - **F3** needs, in addition, the unmapped `TimeoutError` in the fetch, which is #894.
   - **F4** is the shutdown manifestation.

So the upstream material is two reports, not four:
- **F1**;
- **the Redis consumer's connection-error handling**, covering F2 to F4. One fix, `fix-redis-reconnect`, addresses all three.

### F. Patch interactions

`fix-d4-a1` and `fix-d4-a2` were each combined with `fix-redis-reconnect`. Both combinations apply cleanly, and pass every regression test and control (table below).

One interaction found in source: `fix-d4-a2` maps `RedisBroker.enqueue`'s errors to `ConnectionClosed`. That reroutes F3's promotion-path variant from the generic handler to the connection-error handler.
- **Without the reconnect fix,** that turns a would-be thread death into F2's stranding.
- **With it,** the message is kept.

This variant was not run.

## Regression tests

**The file.** `reproductions/regression-tests/test_ppcs_lifecycle.py` holds four regression tests and three negative controls. They use Dramatiq's own `redis_broker` and `redis_worker` fixtures.

**How faults are injected.** Each test patches one dispatch call on the broker (`do_enqueue`, `do_fetch` or `do_requeue`) to raise the redis-py exception a real outage produces. The patch applies once, on the relevant queue, so no live outage is needed. An autouse fixture shortens `CONSUMER_RESTART_DELAY_SECS` to 1 s; this is the same restart path with a shorter pause.

**Where they ran.** In a disposable Linux container (`python:3.13-slim`, Redis 8.0.2 on the container's own loopback) against seven source trees, all from `08d711a`:
- `master`;
- each fix;
- PR #895's `redis.py` change alone;
- the two fix combinations.

Raw output: `outputs/verify/linux-regression/regression-*.txt`.

| Test | master | fix-d4-a1 | fix-d4-a2 | fix-redis-reconnect | requeue mapping only | PR #895 only | a1 + reconnect | a2 + reconnect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1: a failed message is not deleted when its retry can't be enqueued | **FAILED** | passed | passed | **FAILED** | **FAILED** | **FAILED** | passed | passed |
| F1 control: a normal retry works | passed | passed | passed | passed | passed | passed | passed | passed |
| F2: a delayed message survives a connection error in the delay consumer | **FAILED** | **FAILED** | **FAILED** | passed | **FAILED** | **FAILED** | passed | passed |
| F2 control: a delayed message runs without a fault | passed | passed | passed | passed | passed | passed | passed | passed |
| F3: the delay consumer survives a timeout while holding messages | **FAILED** | **FAILED** | **FAILED** | passed | **FAILED** (held message) | **FAILED** (held message) | passed | passed |
| F4: `Worker.stop()` finishes shutdown when requeue fails | **FAILED** | **FAILED** | **FAILED** | passed | passed | **FAILED** | passed | passed |
| F4 control: `Worker.stop()` requeues when Redis is up | passed | passed | passed | passed | passed | passed | passed | passed |

**Why each fails on `master`** (the assertion messages in `regression-master.txt`):
- **F1:** "acknowledged without a retry or a dead letter" (one attempt, no dead letter).
- **F2:** "the delayed message never ran while the worker was alive".
- **F3:** "the delay-queue consumer thread died" (`ConsumerThread … stopped`).
- **F4:** `worker.stop()` raised `redis.exceptions.ConnectionError`.

With PR #895, F3 fails only at "the delayed message held during the stall never ran".

Every test fails against the unpatched implementation and passes with its intended correction, and every negative control passes everywhere.

**Kept as integration reproductions** (real outages, real CLI): `reproductions/verify.py`, `reproductions/experiments.py` and `reproductions/minimal/`.

**Dramatiq's full suite**, minus benchmarks, with a 60 s per-test timeout (`outputs/verify/linux-regression/suite-*.txt`). RabbitMQ and memcached tests skip without servers.

| Tree | Result | Failures compared with `master` |
| --- | --- | --- |
| `master` | 5 failed, 182 passed, 129 skipped | Baseline. All five are environment-related and outside the code under study: the Prometheus metrics test, the SIGHUP reload test (timeout), the pidfile reload test, and two source-watch tests. |
| `fix-d4-a1` | 6 failed, 181 passed | The same five, plus `test_redis_actors_retry_with_backoff_on_failure`: a timing assertion (the retry arrived 3.645 s after the failure, against a 3.5 s bound). **Not reproduced** in 10/10 isolated runs on `fix-d4-a1`, or in 10/10 on `master`. It also passed on the `a1 + reconnect` tree, which contains a1's change. a1 does not touch this path (the enqueue succeeds here). So it is not attributable to a1. |
| `fix-d4-a2` | 5 failed, 182 passed | The same five |
| `fix-redis-reconnect` | 5 failed, 182 passed | The same five |
| `a1 + reconnect` | 5 failed, 182 passed | The same five |
| `a2 + reconnect` | 5 failed, 182 passed | The same five |

A first attempt without a timeout hung on `master` (kept as `suite-*.hung-attempt.txt`). Passing these tests shows no new failure in Dramatiq's existing coverage. It does not show the fixes are correct; the regression tests and integration runs are the evidence for that.

## Decision

**1. Ready for upstream discussion.** The core findings survived serious attempts at falsification. In particular:
- **F1** was narrowed to retry enqueues that never reach Redis.
- **F2** was qualified with an explicit recovery condition.
- **F3** turned out wider than claimed: a single stall killed every holding worker's consumer.
- **F4** holds without any special harness.

An independent maintainer could reproduce each one:
- from a single-file reproduction (F1, F2);
- from the regression tests on Dramatiq's own fixtures;
- with the causal path visible in Redis's own MONITOR log.

| Finding | Readiness |
| --- | --- |
| F1 | **Ready for an issue** (Report A). The fix choice, a1 or a2, is ready for a patch discussion inside that issue. a1 is preferred; a2 has observed regressions. No PR. |
| F2 | **Ready for an issue**, as Report B together with F3 and F4, citing #527. **The fix is not ready** until promotion is ownership-checked. |
| F3 | Part of Report B. Also **ready for a comment on #894 / PR #895** (#895 alone leaves messages stranded). |
| F4 | Part of Report B. Also **ready for a comment on #899** (a second path to the hang). The `requeue` mapping alone (`fix-redis-requeue-mapping.diff`, 4 lines) is **ready for a patch discussion** as an incremental fix: it fixes F4 and F3's thread death with no duplicates, and leaves F2's stranding to the ownership-checked retention. |

**Approval.** Any upstream text needs the user's approval of its exact content. It should be written by the user, with AI assistance disclosed, per Dramatiq's contribution policy and this repository's rules.
