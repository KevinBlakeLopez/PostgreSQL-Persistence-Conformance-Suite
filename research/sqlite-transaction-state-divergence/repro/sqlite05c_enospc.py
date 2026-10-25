"""SQLITE-05c, host side: run sqlite05c_enospc_container.py in a disposable container.

Each repetition is a fresh container: --rm, --network none, a 16 MiB tmpfs at
/data, the image pinned by digest, this directory and the wheel directory
mounted read-only. SQLAlchemy 2.1.6 is installed offline from the two wheels
whose SHA-256 sums are below. The container's stdout (one JSON document) is
the record.

    .venv/bin/python -I repro/sqlite05c_enospc.py

Needs Docker on the colima context and the image already present.
The wheels: .venv/bin/python -m pip download --only-binary=:all:
  --platform manylinux_2_17_aarch64 --platform manylinux2014_aarch64
  --python-version 3.13 --implementation cp --abi cp313 sqlalchemy==2.1.6
  -d .wheels-linux
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script's directory off sys.path
import common  # noqa: E402


IMAGE = "python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962"
WHEELS = common.STUDY / ".wheels-linux"
WHEEL_SHA256 = {
    "sqlalchemy-2.1.6-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl":
        "650f97996a4c529f4930969f3ba11bcdb57ff160ed1cb87ea0174393bf4f5f73",
    "typing_extensions-4.16.0-py3-none-any.whl":
        "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
}
VARIANTS = ("raw", "default", "autocommit-false", "begin-recipe")


def check_wheels() -> None:
    for name, digest in WHEEL_SHA256.items():
        actual = hashlib.sha256((WHEELS / name).read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"{name}: sha256 {actual}, expected {digest}")


def scenario(variant: str) -> Callable[[Path, str], dict[str, Any]]:
    def run(work: Path, token: str) -> dict[str, Any]:
        name = f"ppcs-sqlite-sd-enospc-{token[:12]}"
        install = ("pip install -q --no-index --no-deps "
                   + " ".join(f"/wheels/{w}" for w in WHEEL_SHA256) + " >/dev/null 2>&1")
        command = [
            "docker", "run", "--rm", "--network", "none", "--name", name,
            "--tmpfs", "/data:rw,size=16m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{common.STUDY / 'repro'}:/repro:ro",
            "-v", f"{WHEELS}:/wheels:ro",
            IMAGE, "sh", "-c",
            f"{install}; python -I /repro/sqlite05c_enospc_container.py {variant} {token}",
        ]
        env = {**os.environ, "DOCKER_CONTEXT": "colima"}
        proc = subprocess.run(command, capture_output=True, text=True, timeout=300, env=env)
        try:
            doc = json.loads(proc.stdout)
        except json.JSONDecodeError:
            doc = {"stdout_tail": proc.stdout[-2000:]}
        result = doc.get("result") or {}
        setup = doc.get("setup") or {}
        if variant == "raw":
            observed = {
                "failed_seq": result.get("failed_seq"),
                "first_error": (result.get("first_error") or {}).get("sqlite_errorname"),
                "first_error_chain": (result.get("first_error") or {}).get("chain"),
                "in_transaction_after_error": result.get("in_transaction_after_error"),
                "commit_error": (result.get("commit_error") or {}).get("chain"),
                "committed_seqs": result.get("committed_seqs"),
            }
        else:
            observed = {
                "skipped_seqs": [s["seq"] for s in result.get("skipped", [])],
                "skipped_errors": sorted({(s["error"] or {}).get("chain", [""])[0] for s in result.get("skipped", [])}),
                "commit_error": (result.get("commit_error") or {}).get("chain"),
                "application_claims_committed": result.get("application_claims_committed"),
                "committed_seqs": result.get("committed_seqs"),
                "claim_matches_database": result.get("claim_matches_database"),
            }
        observed["container"] = {
            "returncode": proc.returncode,
            "python": doc.get("python"),
            "sqlite": doc.get("sqlite"),
            "sqlalchemy": result.get("sqlalchemy"),
            "free_after_filler_mib": round((setup.get("free_after_filler") or 0) / 1048576, 1),
        }
        return {"observed": observed, "document": doc, "stderr_tail": proc.stderr.splitlines()[-5:],
                "command": command}

    return run


def main() -> None:
    check_wheels()
    common.run_experiment("sqlite05c-enospc", [(v, scenario(v)) for v in VARIANTS])


if __name__ == "__main__":
    main()
