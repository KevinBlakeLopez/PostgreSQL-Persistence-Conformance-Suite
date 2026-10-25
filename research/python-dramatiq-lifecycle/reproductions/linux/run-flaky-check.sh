#!/bin/bash
# Inside the container: run one of Dramatiq's tests 10 times per tree, to tell
# a flaky timing assertion from a regression. Usage: run-flaky-check.sh <test id> <tree>...
set -uo pipefail
test=$1; shift
out=/study/outputs/verify/linux-regression
for t in "$@"; do
  pass=0; fail=0
  for i in $(seq 1 10); do
    if ( cd /src/$t && /venv/test/bin/python -m pytest -o addopts='' -p no:cacheprovider -q "$test" ) >> $out/flaky-$t.txt 2>&1; then
      pass=$((pass+1))
    else
      fail=$((fail+1))
    fi
  done
  echo "$t: $pass passed, $fail failed of 10 ($test)" | tee -a $out/flaky-summary.txt
done
