#!/usr/bin/env bash
# E3: does a fix that awaits the cancelled tasks keep shutdown bounded?
#
# Three builds of Uvicorn under the same cases:
#   venv-313       0.54.0, unpatched
#   venv-313-fix   main e4981ad + uvicorn-await-cancelled-tasks.diff (unbounded wait)
#   venv-313-fixb  main e4981ad + uvicorn-await-cancelled-tasks-bounded.diff (bounded wait, honors force exit)
# Also re-runs the core F1 cases with the harness that tags and logs every backend reply.
set -euo pipefail
: "${LC_VENVS:?set LC_VENVS to the directory holding the virtual environments}"
cd "$(dirname "$0")"
H="$LC_VENVS/venv-313/bin/python"
KEEP_AWAKE=()
command -v caffeinate >/dev/null && KEEP_AWAKE=(caffeinate -i)
REL="$LC_VENVS/venv-313/bin/python"
FIX="$LC_VENVS/venv-313-fix/bin/python"
FIXB="$LC_VENVS/venv-313-fixb/bin/python"

run() { "${KEEP_AWAKE[@]}" "$H" harness.py --timeout 2 --hard-limit 20 "$@"; }

# Core F1 cases with tagged replies.
run --reps 5 --case e3-01-release-exceeds-term --python "$REL"  --signal TERM
run --reps 5 --case e3-02-release-exceeds-int  --python "$REL"  --signal INT
run --reps 5 --case e3-03-fix-exceeds-term     --python "$FIX"  --signal TERM
run --reps 5 --case e3-04-fix-exceeds-int      --python "$FIX"  --signal INT
run --reps 5 --case e3-05-fixb-exceeds-term    --python "$FIXB" --signal TERM
run --reps 5 --case e3-06-fixb-exceeds-int     --python "$FIXB" --signal INT

# The cleanup releases through a lifespan-owned pool that lifespan shutdown closes first.
run --reps 5 --case e3-07-release-shared-term --python "$REL"  --shared --signal TERM
run --reps 5 --case e3-08-release-shared-int  --python "$REL"  --shared --signal INT
run --reps 5 --case e3-09-fix-shared-term     --python "$FIX"  --shared --signal TERM
run --reps 5 --case e3-10-fixb-shared-term    --python "$FIXB" --shared --signal TERM

# The unit suppresses its cancellation and keeps working (misbehaving application).
run --reps 3 --case e3-11-release-stubborn-term --python "$REL"  --stubborn --signal TERM
run --reps 3 --case e3-12-release-stubborn-int  --python "$REL"  --stubborn --signal INT
run --reps 3 --case e3-13-fix-stubborn-term     --python "$FIX"  --stubborn --signal TERM
run --reps 3 --case e3-14-fix-stubborn-int      --python "$FIX"  --stubborn --signal INT
run --reps 3 --case e3-15-fixb-stubborn-term    --python "$FIXB" --stubborn --signal TERM
run --reps 3 --case e3-16-fixb-stubborn-int     --python "$FIXB" --stubborn --signal INT

# Cleanup that takes longer than the timeout (5 s release, 2 s timeout).
run --reps 3 --case e3-17-release-long-cleanup-term --python "$REL"  --release-delay 5 --signal TERM
run --reps 3 --case e3-18-fix-long-cleanup-term     --python "$FIX"  --release-delay 5 --signal TERM
run --reps 3 --case e3-19-fixb-long-cleanup-term    --python "$FIXB" --release-delay 5 --signal TERM

# Long cleanup, and a second Ctrl+C (SIGINT) once the cleanup has reached the backend.
run --reps 3 --case e3-20-release-long-cleanup-int-int --python "$REL"  --release-delay 5 --signal INT --second-signal INT
run --reps 3 --case e3-21-fix-long-cleanup-int-int     --python "$FIX"  --release-delay 5 --signal INT --second-signal INT
run --reps 3 --case e3-22-fixb-long-cleanup-int-int    --python "$FIXB" --release-delay 5 --signal INT --second-signal INT
