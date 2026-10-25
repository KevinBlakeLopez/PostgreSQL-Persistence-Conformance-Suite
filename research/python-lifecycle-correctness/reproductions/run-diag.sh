#!/usr/bin/env bash
# Diagnostic: what Uvicorn's own registry holds at the lifespan boundary.
#
# Both builds add one log line before `await self.lifespan.shutdown()`
# (uvicorn-diagnostic-registry-log.diff); the line reports server_state.connections (with each
# transport open or closing) and server_state.tasks. It is instrumentation of the code under
# test, not a behavior change.
#   venv-313-diag       main e4981ad + diagnostic line
#   venv-313-fixb-diag  main e4981ad + bounded fix + diagnostic line
set -euo pipefail
: "${LC_VENVS:?set LC_VENVS to the directory holding the virtual environments}"
cd "$(dirname "$0")"
H="$LC_VENVS/venv-313/bin/python"
KEEP_AWAKE=()
command -v caffeinate >/dev/null && KEEP_AWAKE=(caffeinate -i)
DIAG="$LC_VENVS/venv-313-diag/bin/python"
FIXB_DIAG="$LC_VENVS/venv-313-fixb-diag/bin/python"

run() { "${KEEP_AWAKE[@]}" "$H" harness.py --timeout 2 --hard-limit 20 --reps 5 "$@"; }

run --case d-01-diag-in-time-term    --python "$DIAG"      --work-delay 0.3 --signal TERM
run --case d-02-diag-exceeds-term    --python "$DIAG"      --signal TERM
run --case d-03-diag-exceeds-int     --python "$DIAG"      --signal INT
run --case d-04-fixb-diag-exceeds-term --python "$FIXB_DIAG" --signal TERM
run --case d-05-fixb-diag-exceeds-int  --python "$FIXB_DIAG" --signal INT
