# Harness development runs

These runs were made while building `reproductions/harness.py`. They are kept as recorded and are not evidence for any finding.

- `*-smoke-control`, `*-smoke-suspect`: first version of the backend, which answered the calls on a connection one at a time. In the suspect run, the backend was still inside the 60 s "work" delay when the process ended, so it never read the release message that followed on the same connection. The backend was changed to answer each call on its own thread.
- `*-smoke2-control --work-delay 0.3` and `*-smoke2-suspect`: second version of the backend. Because of a shell quoting slip, both were started with the default 60 s work delay, so both are suspect-case runs, despite the first one's name.
- `*-smoke3-exceeds-term`, `*-smoke3-hypercorn-8s-term`: checks of the third harness version (own process group, group kill at the hard limit, client result snapshot with its end time, `--shield`).

## First full E1 run (2026-10-24T18-42Z to 18-52Z, second harness version)

The directories in `outputs/e1-run1/` are the first full E1 run. Two of its cases are not usable as recorded:

- `e1-08-hypercorn-exceeds-term` and `e1-09-hypercorn-exceeds-int`: Hypercorn runs the application in a worker process (default `workers = 1`). The harness signalled the supervisor, then at the 20 s hard limit killed only the supervisor, so the worker kept running as an orphan. Its witness file shows the request was never cancelled and finished its 60 s of work, which is how the client fields came to record a `200` (the harness stored the client result by reference and the orphan answered after the harness had moved on). The third harness version kills the whole process group and snapshots the client result.
- `e1-15-py314-exceeds-term`, repetitions 2 and 4: the host went into maintenance sleep on battery during the run (`pmset -g log`), so their wall-clock timings (488 s and 990 s from signal to exit) include sleep. Their outcomes match the other repetitions. The second run wraps every case in `caffeinate -i`.
