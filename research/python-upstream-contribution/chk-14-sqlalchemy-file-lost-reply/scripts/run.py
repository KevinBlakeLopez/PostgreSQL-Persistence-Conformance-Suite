"""Run CHK-10's six cells, three repetitions each, one process per run.

Usage: run.py <venv> <instance.json> <output dir>
Each run gets a fresh storage directory. Writes <cell>.rep<N>.out and .raw.json, then reports
whether each cell's repetitions are byte-identical.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = HERE / "chk10.py"
venv, instance_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
instance = json.loads(instance_path.read_text())
env = {**os.environ, "CHK10_APP_PASSWORD": instance["app_password"], "CHK10_CLUSTER_NAME": instance["cluster_name"]}
python = venv / "bin" / "python"
out.mkdir(parents=True, exist_ok=True)
versions = subprocess.run([python, "-I", PROGRAM, "--versions"], env=env, capture_output=True, text=True, check=True)
(out / "versions.json").write_text(versions.stdout)
print(versions.stdout.strip())

results = {}
for form in ("docs", "begin", "commit-rollback", "admin"):
    for arm in ("lost-reply", "rejected", "no-fault"):
        cell = f"{form}.{arm}"
        outputs = []
        for rep in (1, 2, 3):
            storage = out / "storage" / f"{cell}.rep{rep}"
            run_env = {**env, "CHK10_STORAGE": str(storage)}
            r = subprocess.run([python, "-I", PROGRAM, form, arm, out / f"{cell}.rep{rep}.raw.json"],
                               env=run_env, capture_output=True, text=True, timeout=120)
            (out / f"{cell}.rep{rep}.out").write_text(r.stdout)
            if r.returncode != 0 or r.stderr.strip():
                (out / f"{cell}.rep{rep}.err").write_text(r.stderr)
            outputs.append((r.returncode, r.stdout))
        identical = len({o for _, o in outputs}) == 1
        verdict = next((l for l in outputs[0][1].splitlines() if l.startswith("verdict:")), "verdict: (none)")
        results[cell] = {"exit": [c for c, _ in outputs], "reps_identical": identical, "verdict": verdict}
        print(f"{cell:20} exit={[c for c, _ in outputs]} identical={identical}  {verdict}")
(out / "summary.json").write_text(json.dumps(results, indent=1) + "\n")
