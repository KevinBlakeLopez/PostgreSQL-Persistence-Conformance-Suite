#!/usr/bin/env bash
# E1: Uvicorn's graceful-shutdown timeout and the tasks it cancels.
#
# LC_VENVS must name the directory holding the virtual environments described in README.md:
#   venv-313       Python 3.13, uvicorn 0.54.0 (latest release), starlette, fastapi, hypercorn
#   venv-313-main  Python 3.13, uvicorn main at e4981ad
#   venv-313-fix   Python 3.13, uvicorn main at e4981ad plus uvicorn-await-cancelled-tasks.diff, fastapi
#   venv-314       Python 3.14, uvicorn 0.54.0
set -euo pipefail
: "${LC_VENVS:?set LC_VENVS to the directory holding the virtual environments}"
cd "$(dirname "$0")"
REPS="${REPS:-5}"
H="$LC_VENVS/venv-313/bin/python"   # the harness itself only needs the standard library
KEEP_AWAKE=()
command -v caffeinate >/dev/null && KEEP_AWAKE=(caffeinate -i)   # macOS: no idle sleep mid-run

run() { "${KEEP_AWAKE[@]}" "$H" harness.py --reps "$REPS" "$@"; }
REL="$LC_VENVS/venv-313/bin/python"

# Controls: the request finishes inside the timeout.
run --case e1-01-in-time-term       --python "$REL" --timeout 2 --work-delay 0.3 --signal TERM
run --case e1-02-in-time-int        --python "$REL" --timeout 2 --work-delay 0.3 --signal INT

# Suspect: the request outlives the timeout and is cancelled.
run --case e1-03-exceeds-term       --python "$REL" --timeout 2 --signal TERM
run --case e1-04-exceeds-int        --python "$REL" --timeout 2 --signal INT
# A release the backend answers at once: is the loss a race with lifespan shutdown?
"${KEEP_AWAKE[@]}" "$H" harness.py --reps 20 --case e1-05-exceeds-term-fast-release --python "$REL" --timeout 2 --release-delay 0 --signal TERM

# The application protects its release with asyncio.shield().
run --case e1-16-exceeds-term-shielded --python "$REL" --timeout 2 --shield --signal TERM
run --case e1-17-exceeds-int-shielded  --python "$REL" --timeout 2 --shield --signal INT

# Framework-managed background task (FastAPI BackgroundTasks), with and without the timeout.
run --case e1-06-fastapi-bg-exceeds-term    --python "$REL" --app fastapi --timeout 2 --signal TERM
run --case e1-07-fastapi-bg-no-timeout-term --python "$REL" --app fastapi --work-delay 1 --signal TERM

# Differential: Hypercorn on the same application. Its graceful timeout is not enforced on
# Python 3.12+ (pgjones/hypercorn#308), so the work is kept shorter than the hard limit.
run --case e1-08-hypercorn-8s-work-term --python "$REL" --server hypercorn --timeout 2 --work-delay 8 --signal TERM
run --case e1-09-hypercorn-8s-work-int  --python "$REL" --server hypercorn --timeout 2 --work-delay 8 --signal INT

# Default branch, unpatched and patched.
run --case e1-10-main-exceeds-term  --python "$LC_VENVS/venv-313-main/bin/python" --timeout 2 --signal TERM
run --case e1-11-main-exceeds-int   --python "$LC_VENVS/venv-313-main/bin/python" --timeout 2 --signal INT
run --case e1-12-fix-exceeds-term   --python "$LC_VENVS/venv-313-fix/bin/python" --timeout 2 --signal TERM
run --case e1-13-fix-exceeds-int    --python "$LC_VENVS/venv-313-fix/bin/python" --timeout 2 --signal INT
run --case e1-14-fix-fastapi-bg-exceeds-term --python "$LC_VENVS/venv-313-fix/bin/python" --app fastapi --timeout 2 --signal TERM

# Another interpreter.
run --case e1-15-py314-exceeds-term --python "$LC_VENVS/venv-314/bin/python" --timeout 2 --signal TERM
