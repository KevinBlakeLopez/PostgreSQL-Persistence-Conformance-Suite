"""Run each harness case in a fresh process; keep JSON, stderr, and server log.

Usage: python run_cases.py [case ...]   (default: every case)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
PY = str(HERE.parent / "venv" / "bin" / "python")
ENV = {**os.environ, "DOCKER_CONTEXT": "colima"}

sys.path.insert(0, str(HERE))
names = sys.argv[1:]
if not names:
    src = (HERE / "p5a_review.py").read_text()
    block = src.split("CASES = {", 1)[1].split("\n}\n", 1)[0]
    names = re.findall(r'^\s+"([a-z_\-]+)":', block, re.M)

for name in names:
    since = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t = time.monotonic()
    p = subprocess.run([PY, str(HERE / "p5a_review.py"), name], capture_output=True, text=True, timeout=120)
    elapsed = time.monotonic() - t
    (OUT / f"{name}.stderr").write_text(p.stderr)
    (OUT / f"{name}.json").write_text(p.stdout)
    time.sleep(0.5)
    log = subprocess.run(
        ["docker", "logs", "--since", since, "sa-tx-probe"], capture_output=True, text=True, env=ENV
    )
    try:
        data = json.loads(p.stdout)
        pids = {data["first"].get("pid"), data["second_checkout"].get("pid")} - {None}
    except Exception as e:  # keep going; the summary will show the failure
        print(f"{name}: exit={p.returncode} JSON unreadable ({e}); stderr tail: {p.stderr[-400:]}")
        continue
    lines = [
        ln for ln in (log.stdout + log.stderr).splitlines()
        if any(f"[{pid}]" in ln for pid in pids)
    ]
    (OUT / f"{name}.serverlog").write_text("\n".join(lines) + "\n")
    print(f"{name}: exit={p.returncode} {elapsed:.1f}s pids={sorted(pids)} serverlog_lines={len(lines)}")
