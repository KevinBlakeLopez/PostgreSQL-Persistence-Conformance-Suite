# Dramatiq worker lifecycle and message delivery correctness

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

## Objective

This study asked whether Dramatiq acknowledges, abandons, loses or misreports messages during realistic worker and broker failures, in ways that contradict its documented delivery guarantees. It applies the PPCS method:

- an explicit contract;
- a production-reachable trigger;
- an observer outside the worker;
- controls;
- repetition;
- source-level root cause;
- an upstream check.

It is a research package for human review. Nothing was filed, posted or proposed upstream. The brief is [../python-dramatiq-investigation-prompt.md](../python-dramatiq-investigation-prompt.md).

## Scope

- **Broker: Redis.**
  - Dramatiq's Redis broker keeps the whole message lifecycle in inspectable keys: queue lists, payload hashes, per-worker ack sets, dead-letter sets and heartbeats. Its recovery logic is a single Lua script.
  - Its in-memory handling after connection errors assumes RabbitMQ semantics (F2), so Redis is where the contracts are weakest.
  - RabbitMQ was not run.
- **Examined:**
  - worker shutdown;
  - consumer restart after connection errors;
  - acknowledgement and its retry loop;
  - the `Retries` middleware;
  - delayed-message promotion;
  - Redis maintenance and heartbeats;
  - the CLI's signal handling.
- **Set aside, with reasons:** D1, D3, D5 and D6 from the brief, and N3-N5. The reasons are in [candidate-matrix.md](candidate-matrix.md).
- **Independence from PPCS:** the study uses no database, no PPCS adapter and no PPCS infrastructure.

## Tested versions

| Component | Versions |
| --- | --- |
| Dramatiq | 2.2.1 (PyPI, latest release); `master` at `08d711a` (2026-10-13). The files involved are byte-identical between the two. `master` plus each candidate fix. |
| redis-py | 8.1.0 (the latest Dramatiq allows) |
| Redis server | 8.6.2 (macOS, Homebrew); 8.0.2 (Linux, Debian package) |
| Python | CPython 3.13.11 (macOS); 3.13.17 (Linux) |
| OS | macOS 26.6.2 arm64; Linux in a `python:3.13-slim` container (Debian 13.7, kernel 6.8.0-64, aarch64) |

## Main conclusions

**After the adversarial verification of 2026-10-25** ([adversarial-verification.md](adversarial-verification.md)), all four findings stand:
- F1 is narrowed;
- F2 has a recovery condition;
- F3 turned out wider than claimed;
- one candidate fix was found to introduce duplicates.

The bullets below include those changes.

- **F1, CONFIRMED DEFECT (narrowed).** A failed message whose retry enqueue never reaches Redis is acknowledged and deleted.
  - **The sequence.** When an actor fails and the broker refuses the connection at the moment `Retries` enqueues the retry, three things happen in order:
    1. `Broker.emit_after` logs the enqueue's exception at CRITICAL and swallows it.
    2. The worker acknowledges the original as soon as the broker returns.
    3. The message is gone: there is no retry, no dead letter and no further attempt.
  - **What the logs claim.** Dramatiq logs "Retrying message … in N milliseconds" before the enqueue, and the worker later shuts down with exit code 0.
  - **Counts.** Lost in 21 of 21 fault runs: 16 on macOS and 5 on Linux, across 2.2.1 and `master`, the host and URL connection forms, and an actor that fails on its own because it uses the same Redis.
  - **Controls.**
    - With `max_retries=0` the same failure dead-letters the message.
    - Killing the worker instead of letting it ack leaves the message recoverable, and a replacement runs it.
    - Without a fault the retry works.
  - **Not lost when Redis received the enqueue.** When only the reply was lost, the retry ran (3/3), though Dramatiq still logged the CRITICAL failure; with the host form, redis-py re-sent the call and the retry ran twice (3/3). When only the ack failed, nothing was lost either.
  - **Scope.** A `dramatiq.Retry` exception and the last allowed retry are affected; exhausted and `throws` failures are dead-lettered. Redis broker only: on RabbitMQ, source reading suggests the original would be redelivered.
  - **Contract.** It contradicts the documented retry and dead-letter behavior (`guide.rst:217-218`, `267-268`). "Messages are only ever acknowledged … after they have been successfully processed" supports this, but loosely.
  - **Upstream.** No issue exists. The behavior was described in two comments on PR #545 (closed unmerged).
- **F2, CONFIRMED DEFECT (conditional).** After a Redis connection error, delayed messages a live worker had fetched are stranded while that worker lives and keeps heartbeating, unless another worker's maintenance gets there first.
  - **Mechanism.** The consumer thread discards its in-memory delay queue without requeueing it. The messages stay in the worker's ack set, and because the worker keeps heartbeating, Redis maintenance never returns them. This includes scheduled retries.
  - **Counts.** Stranded in 14 of 14 runs. The worker's heartbeat stayed under 0.7 s old, and the messages were not recovered even with maintenance on every call and a 2 s heartbeat timeout. With Dramatiq's defaults they were still stranded 300 s past their ETA.
  - **Ownership, confirmed from both sides.** Redis's MONITOR shows the ack-set entry untouched while the owner lives. The worker's own state shows its in-memory delay queue dropping to 0.
  - **The condition.**
    - A second live worker on the default heartbeat timeout did not recover them (3/3).
    - They are recovered when another worker's maintenance, with a heartbeat timeout shorter than the outage, wins a race against the owner (1/3 with a 2 s timeout), or when the owner stops heartbeating while alive (2/2).
  - **Upstream.** #527 reported this symptom in 2023, and was closed with a heartbeat-timeout explanation that these runs contradict.
- **F3, CONFIRMED DEFECT.** An unmapped Redis error (`redis.TimeoutError`) while the delay-queue consumer holds messages kills that consumer thread.
  - **Effect.** The worker stays up and keeps running ordinary messages, but never fetches delayed ones again.
  - **Counts.**
    - The thread died in 10 of 10 runs with a 15 s `CLIENT PAUSE … WRITE`, and in 0 of 3 with a 7 s pause.
    - It also died under a real network blackhole through a TCP proxy (3/3).
    - With two workers, one pause killed both workers' consumers (3/3).
    - Upstream PR #895 alone prevents the death, but the held messages are then stranded, as in F2.
  - **Upstream.** Related to the open #894 / PR #895, which do not report thread death and do not cover the failing call.
- **F4, CONFIRMED DEFECT, lower severity.** If Redis is unavailable at the shutdown requeue, `Worker.stop()` raises instead of taking its documented warning branch.
  - **Effect.** The worker exits with code 1 and skips `after_worker_shutdown`. With the AsyncIO middleware, the worker process never exits.
  - **No loss.** The messages are recovered later through heartbeat maintenance.
  - **Counts.** Exit 1 in 11 of 11 runs; a hang in 4 of 4 with AsyncIO.
  - **Harness independence.** It reproduced without any shutdown barrier, with a `TimeoutError` instead of a refused connection, and with AsyncIO installed first.
  - **Upstream.** It is a second path to #899's hang, and #900 would not fix it.

Candidate fixes exist as diffs in `reproductions/fixes/`.
- **`fix-d4-a1`** (dead-letter) is the safe F1 correction.
- **`fix-d4-a2`** (retry the enqueue) duplicated retries after lost replies, and changes what `actor.send()` raises.
- **`fix-redis-reconnect`** fixes F2-F4, but ran delayed messages twice when another worker recovered them while the owner still held them. It needs ownership-checked promotion first.
- **`fix-redis-requeue-mapping`** is the `requeue` part alone; see the verification.

Regression tests on Dramatiq's own fixtures (`reproductions/regression-tests/`) fail on `master` and pass with each intended fix. See [findings.md](findings.md), [adversarial-verification.md](adversarial-verification.md) and [upstream-opportunities.md](upstream-opportunities.md). The report in the brief's format is [FINAL-REPORT.md](FINAL-REPORT.md).

## Evidence and classification

- **How an outcome is decided.** Never from the worker's own logs. Three sources are used:
  - snapshots of every `dramatiq:*` key, read over the harness's own Redis connection;
  - an external witness, a TCP service in the harness process, that records each attempt's start, effect and completion, and each acknowledgement and enqueue Dramatiq reports;
  - the worker's exit status.
- **Faults are real broker events:**
  - a graceful Redis restart with `appendfsync always`;
  - Redis's own `CLIENT PAUSE … WRITE`;
  - SIGTERM or SIGKILL to the worker.
- **Synchronization.** Witness barriers in the actor or in one public middleware hook fix when a fault happens. No Dramatiq code is modified outside the fix-evaluation builds.
- **Classifications** use the brief's labels. Runtime claims are backed by recorded runs; statements from source reading are labelled as such.

## Running it

Requirements:
- macOS or Linux;
- CPython 3.13;
- a `redis-server` binary (Homebrew's on macOS);
- free loopback ports 56391-56398.

The harness never uses Redis's default port, 6379, which a machine's other Redis servers often hold. Dramatiq's own test fixtures default to that port and call `flushall()`, so the study ran them only in a Linux container.

```sh
# 1. Environments (any directory outside the repository)
python3.13 -m venv rel221 && rel221/bin/pip install 'dramatiq[redis]==2.2.1' 'redis==8.1.0'
git clone https://github.com/Bogdanp/dramatiq && git -C dramatiq checkout 08d711a
python3.13 -m venv master && master/bin/pip install './dramatiq[redis]' 'redis==8.1.0'
# Optional: a fix build. Copy the tree, apply reproductions/fixes/<fix>.diff, install it the same way.

# 2. The network guard (refuses everything except loopback ports 56391-56398)
reproductions/netguard/install.sh rel221        # and each other venv

# 3. One experiment, e.g. F1's fault variant, three repetitions
rel221/bin/python -I reproductions/experiments.py d4 --variant fault --reps 3

# 4. Everything that was run
reproductions/run-batch.sh <dir>/rel221 <dir>/master    # repetitions and controls
reproductions/run-fixes.sh <dir>                       # fixes; expects venvs named as in run-fixes.sh
rel221/bin/python -I reproductions/summarize.py         # writes outputs/SUMMARY.md

# 5. Minimal single-file reproductions (suitable for a bug report)
rel221/bin/python reproductions/minimal/d4_retry_lost.py --redis-server "$(command -v redis-server)" --port 56391
rel221/bin/python reproductions/minimal/n1_delayed_stranded.py --redis-server "$(command -v redis-server)" --port 56391
```

Experiments and variants:

| Experiment | Variants |
| --- | --- |
| `d4` | `fault`, `fault-actor-redis`, `control-ok`, `control-kill`, `control-noretries` |
| `n1` | `fault-aggressive`, `fault-default`, `control-norestart`, `control-crash` |
| `n2` | `fault`, `control-shortpause` |
| `d7` | `fault`, `fault-asyncio`, `fault-defaultrecovery`, `control`, `control-asyncio` |

Every variant takes `--form host|url`.

Linux: `reproductions/linux/` holds the three scripts used inside a disposable `python:3.13-slim` container, with this directory mounted at `/study`:
- `setup-in-container.sh` builds the same environments;
- `reproduce.sh` runs the reproductions into `outputs/linux/`;
- `upstream-tests.sh` runs Dramatiq's own tests against Redis on the container's loopback.

## Limitations

- **One broker.** RabbitMQ was assessed only from source.
- **Not run:**
  - the `Callbacks`/`Pipelines` variants of F1;
  - the enqueue-path variant of F3;
  - a lost *fetch* reply (N5).

  The verification did run lost replies for the retry enqueue and for promotion, through the fault proxy.
- **Single-process workers.** Every run used one process and one thread (the CLI's `--processes 1 --threads 1`). Larger prefetch counts change how many messages are affected, not the mechanisms.
- **Timing figures** come from a laptop on battery, with `caffeinate -i` during batches. Outcomes do not depend on timing, because outages are several times longer than redis-py's retry window.
- **Default-maintenance recovery** (293 s in F4) is one sample of a random process.
- **The fixes are proofs of concept.** Regression tests exist for the findings (`reproductions/regression-tests/`). The fixes' API and log choices belong to the maintainers, and two of them were found to introduce duplicates (see the verification).

## Layout

| Path | Contents |
| --- | --- |
| `candidate-matrix.md` | All candidates, the documented contracts, the preliminary review's claims checked against the source, and the selection |
| `findings.md` | Hypothesis, contract, trigger, evidence, controls, root cause, adversarial review, classification and fix evaluation per finding |
| `upstream-opportunities.md` | Ranked contributions, Dramatiq's contribution policy, and the trade-offs of the fixes |
| `FINAL-REPORT.md` | The report in the brief's section 19 format, revised after the verification |
| `adversarial-verification.md` | The investigator's attempt to falsify F1-F4: the narrowing, the qualifications, the fix challenges, regression tests and the final decision |
| `reproductions/` | The application (`app.py`), harness (`harness.py`), experiments (`experiments.py`), batch scripts, summarizers, network guard, Linux scripts, candidate fixes as diffs, and minimal reproductions. Added for the verification: `verify.py`, `run-verify.sh` and `verify_summary.py`; the fault-injecting TCP proxy `faultproxy.py`; `regression-tests/`; and `linux/setup-regression.sh`, `run-regression.sh`, `run-regression-one.sh` and `run-suites.sh`. |
| `outputs/` | Raw evidence per run; see [outputs/README.md](outputs/README.md), [outputs/SUMMARY.md](outputs/SUMMARY.md) and [outputs/verify/SUMMARY.md](outputs/verify/SUMMARY.md) |
