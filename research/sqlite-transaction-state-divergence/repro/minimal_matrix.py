"""Run the minimal reproductions (repro/minimal/) in four environments, three times each.

    host-py3.13-sa2.1.6         .venv            (Python 3.13.11, SQLite 3.54.1)
    host-py3.14-sa2.1.6         .venv-py314      (Python 3.14.2, SQLite 3.54.1)
    host-py3.13-sa2.0.55        .venv-sa20       (Python 3.13.11, SQLite 3.54.1)
    container-py3.13-sa2.1.6    python:3.13-slim pinned by digest, --network none,
                                SQLAlchemy from the two wheels sqlite05c_enospc.py checks

Raw stdout and stderr are kept. The summary says whether the three runs of a
script were byte-identical, and whether every environment printed the same.

    .venv/bin/python -I repro/minimal_matrix.py
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402
import sqlite05c_enospc  # noqa: E402

SCRIPTS = (
    ("sa_savepoint_batch.py", "on-conflict"),
    ("sa_savepoint_batch.py", "page-limit"),
    ("sa_core_false_commit.py", None),
    ("sa_session_close_leak.py", None),
    ("sqlite3_autocommit_false.py", None),
)
HOST_ENVS = {
    "host-py3.13-sa2.1.6": common.STUDY / ".venv" / "bin" / "python",
    "host-py3.14-sa2.1.6": common.STUDY / ".venv-py314" / "bin" / "python",
    "host-py3.13-sa2.0.55": common.STUDY / ".venv-sa20" / "bin" / "python",
}
CONTAINER_ENV = "container-py3.13-sa2.1.6"
VERSIONS = "import sys, sqlite3, sqlalchemy; print(sys.version.split()[0], sqlite3.sqlite_version, sqlalchemy.__version__)"


def container_command(inner: str) -> list[str]:
    install = ("pip install -q --no-index --no-deps "
               + " ".join(f"/wheels/{w}" for w in sqlite05c_enospc.WHEEL_SHA256) + " >/dev/null 2>&1")
    return ["docker", "run", "--rm", "--network", "none",
            "--name", f"ppcs-sqlite-sd-minimal-{secrets.token_hex(4)}",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{common.STUDY / 'repro'}:/repro:ro",
            "-v", f"{sqlite05c_enospc.WHEELS}:/wheels:ro",
            sqlite05c_enospc.IMAGE, "sh", "-c", f"{install}; {inner}"]


def run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=300, env=env)


def main() -> None:
    sqlite05c_enospc.check_wheels()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = common.OUTPUT / "minimal-matrix" / f"{stamp}-{secrets.token_hex(3)}"
    docker_env = {**os.environ, "DOCKER_CONTEXT": "colima"}
    summary: dict = {"environments": {}, "scripts": {}}
    outputs: dict[str, dict[str, str]] = {}
    for env_name in [*HOST_ENVS, CONTAINER_ENV]:
        if env_name in HOST_ENVS:
            versions = run([str(HOST_ENVS[env_name]), "-I", "-c", VERSIONS]).stdout.strip()
        else:
            versions = run(container_command(f"python -I -c '{VERSIONS}'"), docker_env).stdout.strip()
        summary["environments"][env_name] = versions
        for script, arg in SCRIPTS:
            key = script.removesuffix(".py") + (f"-{arg}" if arg else "")
            reps = []
            for rep in (1, 2, 3):
                args = [script] + ([arg] if arg else [])
                if env_name in HOST_ENVS:
                    proc = run([str(HOST_ENVS[env_name]), "-I", str(common.STUDY / "repro" / "minimal" / script)] + args[1:])
                else:
                    proc = run(container_command("python -I /repro/minimal/" + " ".join(args)), docker_env)
                text = proc.stdout + (f"--- stderr ---\n{proc.stderr}" if proc.stderr else "") + f"--- exit {proc.returncode} ---\n"
                target = run_dir / env_name / f"{key}.rep{rep}.out"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(common.scrub(text), encoding="utf-8")
                reps.append(common.scrub(text))
            outputs.setdefault(key, {})[env_name] = reps[0]
            summary["scripts"].setdefault(key, {})[env_name] = {"three_runs_identical": len(set(reps)) == 1}
    for key, by_env in outputs.items():
        summary["scripts"][key]["all_environments_identical"] = len(set(by_env.values())) == 1
    common.write_json(run_dir / "summary.json", summary)
    lines = []
    for path in sorted(run_dir.rglob("*.out")):
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(run_dir)}")
    (run_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(run_dir.relative_to(common.STUDY))


if __name__ == "__main__":
    main()
