"""Run CHK-4's matrix: 2 SQLAlchemy versions x 3 stacks x 3 arms x 3 repetitions, one process per run.

Repetition-major order: every cell's repetition 1, then every cell's repetition 2, then 3.
Environment: CHK4_INSTANCE (instance.json from chk4_setup.py), CHK4_VENV_216 and CHK4_VENV_215.
Writes output/sa-<version>/<stack>.<arm>.rep<n>.out (stdout; stderr, if any, to .err), raw/ for the
PIDs, xids and times, versions.json per version, and output/runs.txt.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.join(HERE, "chk4_after_rollback.py")
OUTPUT = os.path.join(HERE, "output")
STACKS = ("sync-psycopg", "async-asyncpg", "async-psycopg")
ARMS = ("lost-reply", "rejected", "no-fault")
VENVS = {"2.1.6": os.environ["CHK4_VENV_216"], "2.1.5": os.environ["CHK4_VENV_215"]}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def main(reps):
    instance = json.load(open(os.environ["CHK4_INSTANCE"]))
    env = {**os.environ, "CHK4_APP_PASSWORD": instance["app_password"], "CHK4_CLUSTER_NAME": instance["cluster_name"]}
    lines = []
    for version, venv in VENVS.items():
        directory = os.path.join(OUTPUT, f"sa-{version}")
        os.makedirs(os.path.join(directory, "raw"), exist_ok=True)
        r = subprocess.run([os.path.join(venv, "bin", "python"), "-I", PROGRAM, "--versions"], env=env,
                           capture_output=True, text=True, timeout=60)
        open(os.path.join(directory, "versions.json"), "w").write(r.stdout + r.stderr)
    for rep in reps:
        for version, venv in VENVS.items():
            directory = os.path.join(OUTPUT, f"sa-{version}")
            for stack in STACKS:
                for arm in ARMS:
                    name = f"{stack}.{arm}.rep{rep}"
                    start = now()
                    r = subprocess.run([os.path.join(venv, "bin", "python"), "-I", PROGRAM, stack, arm,
                                        os.path.join(directory, "raw", f"{name}.json")],
                                       env=env, capture_output=True, text=True, timeout=120)
                    lines.append(f"sa-{version} {name} exit={r.returncode} {start} {now()}")
                    print(lines[-1], flush=True)
                    open(os.path.join(directory, f"{name}.out"), "w").write(r.stdout)
                    if r.stderr:
                        open(os.path.join(directory, f"{name}.err"), "w").write(r.stderr)
    with open(os.path.join(OUTPUT, "runs.txt"), "a") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [1, 2, 3])
