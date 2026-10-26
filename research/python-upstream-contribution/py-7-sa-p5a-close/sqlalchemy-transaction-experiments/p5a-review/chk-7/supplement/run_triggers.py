"""CHK-7 supplement: the two P5a triggers that replace no DBAPI method, on SQLAlchemy 2.1.6.

Usage: python3 -I run_triggers.py <venv python> <container> <full server log path>

Runs the 2026-10-18 harness, ../../harness/p5a_review.py, unchanged: one process per run,
three runs per case, in the order of CASES. Saves each run's stdout (one JSON document),
stderr and exit code in output/, with the virtualenv prefix replaced by <venv> and this
repository's path by <repo>. Then saves the whole server log to the given path, outside the
repository, and the lines of the runs' SQLAlchemy backends to output/server-log-extract.txt.

PGPASSFILE must point to a passfile outside the repository.
"""
import datetime, hashlib, json, os, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
REPO = HERE.parents[4]
HARNESS = HERE.parents[1] / "harness" / "p5a_review.py"
HARNESS_SHA256 = "f54a5d7c1306f7cec85d7700c0c773722f8a6c115b9a6beb4fc9107b0b08d48d"  # as committed in cca9b98
CASES = [
    "explicit-none",               # control: commit() succeeds
    "explicit-listener",           # a raising ConnectionEvents.commit listener; Transaction.commit(), then close()
    "connect_ctx-listener",        # the same listener; Connection.commit() inside `with engine.connect()`
    "orm_commit-listener",         # the same listener; Session.commit() inside `with Session(engine)`
    "explicit-psycopg_txn_block",  # psycopg's own ProgrammingError: commit() inside psycopg's transaction()
]
REPS = 3
ENV = {**os.environ, "DOCKER_CONTEXT": "colima"}


def main(py, container, full_log):
    if "PGPASSFILE" not in os.environ:
        sys.exit("PGPASSFILE is not set")
    if hashlib.sha256(HARNESS.read_bytes()).hexdigest() != HARNESS_SHA256:
        sys.exit("the harness differs from cca9b98's")
    prefix = subprocess.run([py, "-I", "-c", "import sys; print(sys.prefix)"],
                            capture_output=True, text=True, check=True).stdout.strip()
    masks = sorted({prefix, os.path.realpath(prefix)}, key=len, reverse=True)

    def mask(s):
        for m in masks:
            s = s.replace(m, "<venv>")
        return s.replace(str(REPO), "<repo>")

    OUT.mkdir(exist_ok=True)
    runs = []
    for case in CASES:
        for rep in range(1, REPS + 1):
            start = datetime.datetime.now(datetime.timezone.utc)
            p = subprocess.run([py, "-I", str(HARNESS), case], capture_output=True, text=True, timeout=120)
            end = datetime.datetime.now(datetime.timezone.utc)
            stem = f"{case}.rep{rep}"
            (OUT / f"{stem}.json").write_text(mask(p.stdout))
            (OUT / f"{stem}.stderr").write_text(mask(p.stderr))
            (OUT / f"{stem}.exit").write_text(f"exit={p.returncode}\n")
            try:
                d = json.loads(p.stdout)
                pids = sorted({d["first"].get("pid"), d["second_checkout"].get("pid")} - {None})
            except Exception as e:
                pids = []
                print(f"{stem}: JSON unreadable ({e})")
            runs.append({"run": stem, "start": start.isoformat(timespec="milliseconds"),
                         "end": end.isoformat(timespec="milliseconds"), "exit": p.returncode, "pids": pids})
            print(f"{stem}: exit={p.returncode} pids={pids}")

    log = subprocess.run(["docker", "logs", container], capture_output=True, text=True, env=ENV, check=True)
    text = log.stdout + log.stderr
    pathlib.Path(full_log).write_text(text)
    lines = text.splitlines()
    wanted = {pid for r in runs for pid in r["pids"]}
    for pid in sorted(wanted):  # each backend pid belongs to one connection in this container's lifetime
        n = sum(1 for ln in lines if f"[{pid}] " in ln and "connection received" in ln)
        if n != 1:
            sys.exit(f"pid {pid}: {n} 'connection received' lines; the extract would be ambiguous")
    extract = [ln for ln in lines if (m := re.search(r" \[(\d+)\] ", ln)) and int(m.group(1)) in wanted]
    (OUT / "server-log-extract.txt").write_text("\n".join(extract) + "\n")
    (OUT / "runs.json").write_text(json.dumps(runs, indent=1) + "\n")
    print(f"server log: {len(lines)} lines; extract: {len(extract)} lines for {len(wanted)} backends")


if __name__ == "__main__":
    main(*sys.argv[1:4])
