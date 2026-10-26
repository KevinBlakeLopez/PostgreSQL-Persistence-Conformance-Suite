"""Run false_commit_async.py three times (one process each) and extract the server log.

Usage: python3 -I run.py <venv python> <container> <full log path>     PGPASSFILE must be set

Writes output/rep<N>.json, .stderr and .exit (the virtualenv prefix replaced by <venv>), then the
container log's lines whose application_name starts with "fc-" to output/server-log-extract.txt.
The whole log goes to <full log path>, outside the evidence directory.
"""
import os, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"


def main(py, container, full_log):
    if "PGPASSFILE" not in os.environ:
        sys.exit("PGPASSFILE is not set")
    prefix = subprocess.run([py, "-I", "-c", "import sys; print(sys.prefix)"], capture_output=True, text=True,
                            check=True).stdout.strip()
    mask = lambda s: s.replace(prefix, "<venv>").replace(os.path.realpath(prefix), "<venv>")
    OUT.mkdir(exist_ok=True)
    for rep in (1, 2, 3):
        p = subprocess.run([py, "-I", str(HERE / "false_commit_async.py"), str(rep)], capture_output=True, text=True,
                           timeout=300)
        (OUT / f"rep{rep}.json").write_text(mask(p.stdout))
        (OUT / f"rep{rep}.stderr").write_text(mask(p.stderr))
        (OUT / f"rep{rep}.exit").write_text(f"exit={p.returncode}\n")
        print(f"rep{rep}: exit={p.returncode}, stdout {len(p.stdout)} bytes, stderr {len(p.stderr)} bytes")
    log = subprocess.run(["docker", "logs", container], capture_output=True, text=True, check=True,
                         env={**os.environ, "DOCKER_CONTEXT": "colima"})
    text = log.stdout + log.stderr
    pathlib.Path(full_log).write_text(text)
    lines = [ln for ln in text.splitlines() if re.search(r" app=fc-", ln)]
    (OUT / "server-log-extract.txt").write_text("\n".join(lines) + "\n")
    print(f"server log: {len(text.splitlines())} lines; extract: {len(lines)} lines")


if __name__ == "__main__":
    main(*sys.argv[1:4])
