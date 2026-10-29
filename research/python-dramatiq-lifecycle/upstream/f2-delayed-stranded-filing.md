# DM2. Filing package for stranded delayed messages

Queued 2026-10-27 in [`docs/upstream-submissions.md`](../../../docs/upstream-submissions.md) as DM2. Not approved to post. The proposed issue text is [`dramatiq-delayed-stranded-draft.md`](dramatiq-delayed-stranded-draft.md), written 2026-10-28. This file is the checklist, not the issue text. Dramatiq's `CONTRIBUTING.md` asks for a human author, and it says pull requests that look automated will be closed. The person who posts this writes the body and can stand behind every sentence. The investigation used AI tools; the report says so in the author's own words, as the author of dramatiq#911 did. No pull request goes with it. The candidate fix duplicated messages when the owner's heartbeat expired while it still held them (2 of 2 under SIGSTOP). That fix is not ready.

F1, F3, and F4 are not this item. The study's Report B grouped F2 with F3 and F4, and it put Report A (F1) first. This queue entry is F2 only.

## Destination

A new issue on `Bogdanp/dramatiq`, using the project's bug-report template. Link #527. Do not reopen #527. A comment on that closed issue is the alternative if a duplicate search that day finds the maintainers treating a new issue as the same report.

Checked through the GitHub API on 2026-10-27:

- #527 ("Delayed Jobs aren't run after cycling Redis") is closed, state reason `completed`, since 2023-02-25. It has three comments. Nothing has been added since.
- A search for `delayed redis` in that repository returned #527, plus #431 (open, delayed messages duplicated onto the work queue; updated 2026-10-11). #431 is a different outcome.
- PyPI `dramatiq` `latest` was 2.2.1.
- `master` was `d3138e2ea8244e2a53f51fbb309dd0eda061e64b` (2026-10-27, a Dependabot bump of two GitHub Actions). The last commit that touches `dramatiq/worker.py` is `fb252f92bbc1` (2026-05-17). The last commit that touches `dramatiq/brokers/redis.py` is `4dafddc3a649` (2025-09-22).
- On that `master`, `ConsumerThread.run` still clears `self.delay_queue` in the `BrokerConnectionError` handler at `worker.py` lines 325–327, and `close()` still requeues whatever is in that queue at line 486. Those are the lines the study cited. The reproduction was not re-run on `d3138e2`.

## Before posting

1. Approval of the exact title, body, and destination.
2. Read #527 again, including the maintainer's heartbeat-timeout explanation.
3. Search issues and pull requests updated after 2026-10-27. If one already reports messages stranded in a live worker's ack set after a Redis restart, comment there instead.
4. If PyPI is no longer 2.2.1, run `reproductions/minimal/n1_delayed_stranded.py` on that release before describing it. The saved output below is 2.2.1.
5. Re-read `worker.py` lines 325–327 and 486 if `master` has a commit on that file after `fb252f92bbc1`.
6. Disclose AI assistance in the investigation. Do not attach a patch.

## What the report can rest on

Rewrite these. The qualification at the top of finding F2 is part of the claim.

- After Redis restarts, delayed messages a live worker had already fetched stay in that worker's ack set. They do not run while that worker stays up and keeps calling Redis. They run after that worker exits.
- This held on Dramatiq 2.2.1 and on `master` `08d711a`, on macOS and on Linux. The fault table is in [`findings.md`](../findings.md), section F2. Under Dramatiq's defaults, one run was still stranded 300 seconds after the ETA, with a heartbeat under 0.7 seconds old.
- A second worker with maintenance on every call and the default heartbeat timeout did not recover them (3 of 3). Recovery while the owner was alive happened when another worker's maintenance ran first with a 2 second timeout (1 of 3), and when the owner was SIGSTOPped past the other worker's timeout (2 of 2).
- The minimal program is `reproductions/minimal/n1_delayed_stranded.py`. It sets `heartbeat_timeout=2000` and `maintenance_chance` to the broker's full scale, so a heartbeat-timeout recovery would have put the message back within seconds. Saved output `outputs/minimal/n1_delayed_stranded-rel221.txt`, Dramatiq 2.2.1, redis-py 8.1.0, redis-server 8.6.2:

```text
30 s after the ETA: runs=0, DQ list=[], ack sets={'dramatiq:__acks__.019509e3-8a95-4d50-849f-3017f2a39b16.default.DQ': ['e1d80c0e-0f0a-4d71-be2a-ec49ad0e8500']}, worker heartbeat age=597 ms
after worker.stop(): runs=0, ack sets={'dramatiq:__acks__.019509e3-8a95-4d50-849f-3017f2a39b16.default.DQ': ['e1d80c0e-0f0a-4d71-be2a-ec49ad0e8500']}
```

- The connection-error handler replaces `delay_queue` with an empty queue before `close()` requeues it, so nothing is returned to Redis. The messages stay in `dramatiq:__acks__.<worker>.default.DQ`. Each dispatch refreshes the heartbeat, so maintenance does not select that worker.
- `_RabbitmqConsumer.requeue` says RabbitMQ redelivers unacked messages on disconnect, which is why dropping the in-memory copies is safe there. Redis does not.
- #527 reports the symptom: delayed jobs did not run after Redis was cycled, and ran hours later. It was closed with the explanation that the heartbeat timeout has to pass. These runs kept a fresh heartbeat and the messages stayed put.
- A control with no Redis restart ran the messages at their ETA (3 of 3). A worker that was SIGKILLed, rather than Redis restarted, did have its messages recovered by a replacement (3 of 3).

## Leave out

- F1 (a retry that never reaches Redis is acknowledged).
- F3 (the delay-queue thread dies on an unmapped timeout) and F4 (`Worker.stop()` during an outage), unless the person later decides to restore the study's grouped Report B.
- The diffs under `reproductions/fixes/`.
- A claim that the messages are lost permanently. They run after the owning worker exits.
- Any name of this research repository.
