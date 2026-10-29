# Upstream opportunities

Investigation date: 2026-10-24. Written by: Claude Opus 5.5 (max).

**Revised 2026-10-25 after the adversarial verification** ([adversarial-verification.md](adversarial-verification.md)):
- F1 is narrowed to retry enqueues that never reach Redis.
- F2 has an added recovery condition.
- F2-F4 are grouped as one report, because they share two root causes.
- The fixes are re-ranked, and regression tests now exist.

Nothing has been filed, posted or proposed upstream. Every item below needs the user's approval of the exact content first.

**Queued 2026-10-27.** F2 alone is DM2. The draft is [`upstream/dramatiq-delayed-stranded-draft.md`](upstream/dramatiq-delayed-stranded-draft.md), written 2026-10-28 and not approved. F1, F3, and F4 are not in that item. The sequence below still puts Report A first; the queue does not.

## How Dramatiq takes contributions

The policy is in `CONTRIBUTING.md` on `master`, last changed by #904 on 2026-10-05.

- **Bug reports.** Opening a bug report "is always recommended". It should include "a minimal, reproducible test case" and the issue template's fields.
- **PRs need a prior discussion.** "Pull Requests opened for bugs that haven't been discussed with a maintainer beforehand, may be closed."
- **Human authorship.**
  - "Do not list any LLM/AI tools in the commit authors. If you aren't willing to claim 100% authorship of the commit, then we aren't interested in reviewing it."
  - "Pull Requests that we suspect are opened by automated tools, will be closed." Three unsolicited fix PRs for #431 (#851, #854, #907) were closed by maintainers on the day they were opened. The tracker does not record why.
- **AI involvement must not be hidden.** The policy's stated goal is "respectful human interactions"; issues are not addressed explicitly. A report built on this research should:
  - **be human-written.** The user writes it and posts it, and can stand behind every claim in it.
  - **disclose AI assistance.** Say plainly that AI tools were used in the investigation and the reproductions, as the author of #911 did ("Please aware that the text was written assisted by AI").
  - **not disguise AI-produced content as purely human work.**
  - **not include a PR unless its human author can claim full authorship under the policy.** Otherwise, describe the candidate fix in the issue and leave the implementation to the maintainers, or to a contributor who writes it.
- **Maintainer activity, as seen on GitHub on 2026-10-24.**
  - `master` was last changed 2026-10-13, and was still `08d711a` on 2026-10-25.
  - LincolnPuzey and Bogdanp review and close PRs.
  - Open PRs from one outside contributor (#895, #900) have waited 4 to 7 weeks without review.
  - Bogdanp answered #527 the same day, and engaged on #545.
  - LincolnPuzey declined extra tracebacks for connection errors (#757), describing those errors as "known/expected". Fixes that add log noise may meet resistance.

## Ranked opportunities

| Rank | Item | Production impact | Confidence after verification | Reproducibility | Fix feasibility | Regression tests | Receptiveness | Effort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Report A: F1.** A failed message whose retry enqueue never reaches Redis is acked and deleted (Redis broker) | Highest. Loss of work configured for retries, with no automatic recovery; the only trace is the worker's ERROR log line, which names the actor and its arguments. Needs a refused or reset connection at the retry enqueue. | High, narrowed. Lost in 21/21 refused-enqueue runs. Not lost when Redis accepted the enqueue (lost reply: 3/3 retried once with the URL form, 3/3 retried twice with the host form) or when only the ack failed (3/3 once; 3/3 twice if the worker is killed). A `Retry` exception and the last allowed retry are affected; exhausted and `throws` failures are not. | Deterministic. Single-file reproduction (`reproductions/minimal/d4_retry_lost.py`). Regression test fails on `master` and passes with either fix. | Small: a1 is about 10 lines. a2 is about 25 lines and changes an exception type. | Ready: `test_f1_…` plus its control | Moderate: the bug was described in #545 and the maintainer engaged; there is no issue to point at | Low for an issue |
| 2 | **Report B: Redis connection errors in the consumer threads** (F2, F3, F4) | High. Delayed messages and scheduled retries a live worker held are stranded for as long as it lives and keeps calling Redis (F2). A Redis stall can kill the delay-queue consumer thread, and delayed work on that worker stops (F3). Shutdown during an outage exits 1, or hangs with AsyncIO (F4). Nothing is lost permanently; recovery comes after the worker exits. | High, with conditions. F2 was stranded in every unpatched fault run with Dramatiq's default maintenance. It was recovered while the owner lived when another worker's maintenance ran first with a heartbeat timeout shorter than the outage (1/3 runs with a 2 s timeout), or when the owner stopped heartbeating (SIGSTOP). F3 killed the thread under `CLIENT PAUSE` (7/7) and under a network blackhole (3/3). F4 reproduces without any shutdown barrier. | Deterministic. Single-file reproduction for F2 (`reproductions/minimal/n1_delayed_stranded.py`). Regression tests for F2, F3 and F4 fail on `master` and pass with the fix. | Moderate. The `requeue` mapping alone (4 lines) safely fixes F4 and F3's thread death. Fixing F2 needs delay-queue retention plus an ownership-checked promotion; see the duplicate risk below. | Ready: `test_f2_…`, `test_f3_…`, `test_f4_…` plus controls | Moderate. #527 was closed with an explanation this evidence contradicts. #894/#895 and #899/#900 are open on adjacent causes. | Medium |
| 3 | **Comment on #894 / PR #895** | Helps the open PR | High. With #895 applied alone, the thread survives but the held messages are stranded (2/2 `CLIENT PAUSE`, 1/1 blackhole, and the regression test's last assertion) | Deterministic | n/a | `test_f3_…` shows the gap | Good: a factual comment on an open PR | Low |
| 4 | **Comment on #899** | A second path to the AsyncIO hang (Redis down at shutdown), which #900's `os._exit` on a second signal does not cover | High: hang in 4/4 earlier runs and in every `nobarrier-asyncio` run | Deterministic | n/a | `test_f4_…` covers the abort, not the hang | Good | Low |

## Suggested sequence

1. **Report A (F1), written by the user, with AI assistance disclosed.** Content:
   - the minimal reproduction and its output on 2.2.1 and `master`;
   - the code path (`retries.py:147-148` → `broker.py:121-127` → `worker.py:600-607` → ack);
   - the narrowed condition: the enqueue never reached Redis;
   - the contract (`guide.rst:217-218`, `267-268`);
   - a reference to the #545 comments;
   - the regression test;
   - one question: whether the maintainers prefer dead-lettering (a1) or retrying the enqueue (a2).

   Offer a fix only after they answer, and only as a PR its human author can fully claim.
2. **Report B (F2-F4), after Report A has a response.** Content:
   - #527 and the MONITOR timeline showing the ack-set entry untouched while the owner lives;
   - the RabbitMQ assumption (`_RabbitmqConsumer.requeue`'s docstring);
   - the recovery condition;
   - F3 and F4 as consequences of the unmapped `requeue`;
   - the regression tests.
3. **Comments 3 and 4** are optional and independent, and can go first if the user prefers to help the open PRs.

## The candidate fixes and their trade-offs (observed unless marked)

| Fix | Fixes | Observed problems | Readiness |
| --- | --- | --- | --- |
| `fix-d4-a1.diff`: if enqueueing the retry raises, `message.fail()`; log "Retrying" only after success | F1. Dead-lettered instead of lost, 7/7. If the nack also fails and the worker dies, the message stays recoverable and runs once (3/3). | A message with retries left is dead-lettered during an outage, with the payload as originally stored (no traceback of this failure). Manual requeue within 7 days. | **Ready for a patch discussion.** It is the safer option. |
| `fix-d4-a2.diff`: retry the enqueue every 5 s on `BrokerConnectionError`; map `RedisBroker.enqueue` errors to `ConnectionClosed` | F1. The retry is enqueued after the outage and runs (7/7). | **Duplicates:** after a lost reply, the retry ran twice in 3/3, against once unpatched. **API change:** `actor.send()` raises `dramatiq.errors.ConnectionClosed` instead of `redis.ConnectionError`. **Blocking:** worker threads block for the outage, bounded by `--worker-shutdown-timeout` at shutdown (3/3 exited and recovered). | Not ready. A design alternative for the maintainers. |
| `fix-redis-reconnect.diff`: `Consumer.redelivers_unacked_on_disconnect` (False for Redis); keep the delay queue on Redis connection errors; map `requeue` errors; `close()` keeps what it couldn't requeue; a failed promotion is put back | F2 (delayed jobs run on the live worker, 4/4). F3 (no thread death, 4/4). F4 (exit 0 with the documented warning, no AsyncIO hang, 7/7). | **Duplicates when ownership expires while the owner still holds the messages:** with the owner SIGSTOPped past another worker's heartbeat timeout, each delayed message ran twice (2/2, against once unpatched). A lost promotion reply duplicates in both builds; the fix only makes it come sooner (2.7 s against 37 s). It adds a new consumer attribute, and changes the exit code after a failed shutdown requeue from 1 to 0 (a policy choice). | **Not ready as is.** Ready for discussion once promotion is ownership-checked (promote only while the id is in the caller's ack set, as PR #859 proposed for #431). |
| `fix-redis-requeue-mapping.diff` (Part 1 alone): `_RedisConsumer.requeue` maps `redis.ConnectionError` and `redis.TimeoutError` to `ConnectionClosed` (4 lines) | F4: exit 0 with the documented warning, no AsyncIO hang (1/1 each). F3: no thread death; later delayed jobs run (3/3). | It doesn't fix F2. The messages held during the stall stay stranded, as with PR #895. No duplicates, because it retains nothing. | **Ready for a patch discussion** as an incremental fix, alongside or after #895 |

**Patch combinations.** a1 + reconnect and a2 + reconnect both apply cleanly, and pass every regression test and control.

**Dramatiq's suites.**
- The three relevant test files pass, 43/43, for `master` and each fix (earlier run).
- The full suite, minus benchmarks: see [adversarial-verification.md](adversarial-verification.md#regression-tests).
