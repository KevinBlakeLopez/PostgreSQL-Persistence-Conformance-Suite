#!/usr/bin/env bash
# E2 (historical control): a signal that arrives while lifespan startup is still running.
# Uvicorn before 0.41.0 returned from _serve() without sending lifespan shutdown (fixed by #2812).
#
# LC_VENVS must name the directory holding the virtual environments described in README.md:
#   venv-313      Python 3.13, uvicorn 0.54.0
#   venv-313-old  Python 3.13, uvicorn 0.40.0
set -euo pipefail
: "${LC_VENVS:?set LC_VENVS to the directory holding the virtual environments}"
cd "$(dirname "$0")"
REPS="${REPS:-5}"
H="$LC_VENVS/venv-313/bin/python"
KEEP_AWAKE=()
command -v caffeinate >/dev/null && KEEP_AWAKE=(caffeinate -i)

run() { "${KEEP_AWAKE[@]}" "$H" harness.py --reps "$REPS" --hold-startup "$@"; }

run --case e2-01-startup-signal-0.40.0-term --python "$LC_VENVS/venv-313-old/bin/python" --signal TERM
run --case e2-02-startup-signal-0.40.0-int  --python "$LC_VENVS/venv-313-old/bin/python" --signal INT
run --case e2-03-startup-signal-0.54.0-term --python "$LC_VENVS/venv-313/bin/python" --signal TERM
run --case e2-04-startup-signal-0.54.0-int  --python "$LC_VENVS/venv-313/bin/python" --signal INT
