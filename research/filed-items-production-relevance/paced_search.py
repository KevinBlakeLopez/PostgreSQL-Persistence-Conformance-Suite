"""Paced, read-only GitHub searches shared by several agents. Nothing is posted.

Usage: python3 -I paced_search.py <queries.json> <out dir>
queries.json: [{"id": "...", "kind": "issues" | "code", "q": "...", "n": 10}]

Adapted from PPCS research/python-upstream-contribution/real-world-evidence/searches/rw_search.py.
One lock file serializes every search across processes, so parallel agents share GitHub's
search limits (code 10/min, issues 30/min): code searches start at least 7 s apart and issue
searches 2.2 s apart, counted across all callers. A rate-limit answer waits for the reset and
retries, up to three times. Writes <out>/<id>.json (query, UTC time, raw result) and prints one
summary block per query, which callers append to their searches.txt.
"""
import fcntl, json, pathlib, subprocess, sys, time
from datetime import datetime, timezone

LOCK = pathlib.Path(__file__).resolve().parent / "search.lock"
STATE = pathlib.Path(__file__).resolve().parent / "search.state.json"
GAP = {"code": 7.0, "issues": 2.2}


def _wait_turn(kind):
    with open(LOCK, "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            state = json.loads(STATE.read_text()) if STATE.exists() else {}
        except ValueError:
            state = {}
        delay = state.get(kind, 0) + GAP[kind] - time.time()
        if delay > 0:
            time.sleep(delay)
        state[kind] = time.time()
        STATE.write_text(json.dumps(state))
        fcntl.flock(lk, fcntl.LOCK_UN)


def _reset_wait(kind):
    p = subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True)
    try:
        res = json.loads(p.stdout)["resources"]["code_search" if kind == "code" else "search"]
        return max(5, res["reset"] - time.time() + 2)
    except Exception:
        return 65


def run(kind, q, n):
    args = ["gh", "api", "-X", "GET", f"search/{kind}", "-f", f"q={q}", "-f", f"per_page={max(n, 10)}"]
    if kind == "code":
        args += ["-H", "Accept: application/vnd.github.text-match+json"]
    for attempt in range(4):
        _wait_turn(kind)
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout)
        err = p.stderr.lower()
        if attempt < 3 and ("rate limit" in err or "403" in err or "429" in err or "secondary" in err):
            time.sleep(_reset_wait(kind))
            continue
        return {"error": p.stderr.strip()[:300]}


def main(qfile, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for spec in json.load(open(qfile)):
        n = spec.get("n", 8)
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        d = run(spec["kind"], spec["q"], n)
        (out / f"{spec['id']}.json").write_text(json.dumps({"query": spec, "utc": when, "result": d}, indent=1))
        print(f"\n## {spec['id']} [{spec['kind']}] {spec['q']}  ({when})")
        if "error" in d:
            print("  ERROR", d["error"])
            continue
        print(f"  total {d.get('total_count')}{' (incomplete)' if d.get('incomplete_results') else ''}")
        for it in d.get("items", [])[:n]:
            if spec["kind"] == "issues":
                repo = it["repository_url"].split("/repos/")[1]
                kind = "PR" if it.get("pull_request") else "IS"
                print(f"  {repo}#{it['number']} {kind} {it['state']} {it['created_at'][:10]} {it['user']['login']} | {it['title'][:100]}")
            else:
                frag = ""
                if it.get("text_matches"):
                    frag = it["text_matches"][0].get("fragment", "").replace("\n", " ")[:120]
                ref = it.get("html_url", "").split("/blob/")[1].split("/")[0] if "/blob/" in it.get("html_url", "") else "?"
                print(f"  {it['repository']['full_name']} {it['path'][-70:]} @ {ref[:10]} | {frag}")
        sys.stdout.flush()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
