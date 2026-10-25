# Invalid runs: harness sequencing error

These three F4 runs (`barrier-asyncio-first-host`, `pause-boundary-url`,
`pause-boundary-asyncio-url`, recorded 2026-10-25 04:44-04:45 UTC) are kept
for the record but excluded from all counts.

`verify.py`'s barrier branch released the first job before `Worker.stop()`
had begun (the CLI checks for SIGTERM once a second). So the worker thread
also processed the prefetched job, and the work queue was empty at the
requeue step. Every one of these runs logs "Requeueing in-memory messages..."
followed directly by "Done requeueing", with no "Re-enqueueing" line, so the
fault under test was never exercised. Their exit code 0 says nothing about
F4.

The branch now waits for `before_worker_shutdown` before releasing the job,
as `experiments.py`'s D7 always did. The variants were re-run afterwards.
