#!/bin/sh
# Record every experiment once, in order, then regenerate output/RESULTS.md.
# Run from anywhere; paths are relative to the study directory.
# sqlite05c_enospc.py and minimal_matrix.py need Docker on the colima context,
# the pinned python:3.13-slim image and .wheels-linux/; minimal_matrix.py also
# needs .venv-py314 and .venv-sa20 (see README.md).
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python
for script in trace_check sqlite01_raw sqlite02_core sqlite03_session sqlite04_savepoint \
              sqlite05_realistic sqlite05b_batch sqlite06_django sqlite05c_enospc minimal_matrix; do
    echo "== repro/$script.py"
    "$PY" -I "repro/$script.py"
done
"$PY" -I repro/summarize.py
