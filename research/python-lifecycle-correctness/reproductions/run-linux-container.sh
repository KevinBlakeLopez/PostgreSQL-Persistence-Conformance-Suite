#!/usr/bin/env bash
# Linux validation of F1, run inside a disposable python:3.13-slim container. From this
# research directory, first build the bounded fix as a wheel (Uvicorn is pure Python):
#
#   pip wheel --no-deps -w .linux-build <uvicorn checkout at e4981ad + uvicorn-await-cancelled-tasks-bounded.diff>
#   docker run --rm --name lc-linux-validation -v "$PWD":/work python:3.13-slim \
#     bash /work/reproductions/run-linux-container.sh
#
# Outputs land in outputs/ as usual. .linux-build/ is ignored by git; delete it afterwards.
set -euo pipefail
cd /work/reproductions
echo "== $(uname -srm); $(. /etc/os-release && echo "$PRETTY_NAME"); $(python3 --version)"

python3 -m venv /venvs/venv-313 && /venvs/venv-313/bin/pip install -q uvicorn==0.54.0 starlette==1.10.0 fastapi==0.162.0
python3 -m venv /venvs/venv-313-std && /venvs/venv-313-std/bin/pip install -q "uvicorn[standard]==0.54.0"
python3 -m venv /venvs/venv-313-fixb && /venvs/venv-313-fixb/bin/pip install -q /work/.linux-build/uvicorn-0.54.0-py3-none-any.whl starlette==1.10.0 fastapi==0.162.0
/venvs/venv-313-fixb/bin/python -c "import inspect, uvicorn.server as s; assert '_wait_cancelled_tasks' in inspect.getsource(s.Server), 'bounded fix missing'"

REL=/venvs/venv-313/bin/python STD=/venvs/venv-313-std/bin/python FIXB=/venvs/venv-313-fixb/bin/python
run() { "$REL" harness.py --timeout 2 --hard-limit 20 "$@"; }

run --reps 5 --case linux-01-in-time-term      --python "$REL"  --work-delay 0.3 --signal TERM
run --reps 5 --case linux-02-exceeds-term      --python "$REL"  --signal TERM
run --reps 5 --case linux-03-exceeds-int       --python "$REL"  --signal INT
run --reps 5 --case linux-04-standard-exceeds-term --python "$STD" --signal TERM
run --reps 5 --case linux-05-shared-term       --python "$REL"  --shared --signal TERM
run --reps 5 --case linux-06-fastapi-bg-exceeds-term --python "$REL" --app fastapi --signal TERM
run --reps 5 --case linux-07-fixb-exceeds-term --python "$FIXB" --signal TERM
run --reps 5 --case linux-08-fixb-exceeds-int  --python "$FIXB" --signal INT
run --reps 5 --case linux-09-fixb-shared-term  --python "$FIXB" --shared --signal TERM
run --reps 3 --case linux-10-fixb-stubborn-term --python "$FIXB" --stubborn --signal TERM

for build in REL FIXB; do
  for flag in "" "--sigint"; do
    for n in 1 2 3; do
      echo "== minimal_repro.py $build ${flag:-(SIGTERM)} run $n"
      "${!build}" minimal_repro.py $flag || true
    done
  done
done
