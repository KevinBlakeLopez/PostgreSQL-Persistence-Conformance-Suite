"""Paced, read-only GitHub searches for real-world evidence. Nothing is posted.

Usage: python3 -I rw_search.py <queries.json> <out dir>
queries.json: [{"id": "...", "kind": "issues" | "code", "q": "...", "n": 10}]
Writes <out>/<id>.json (raw API result) and prints one summary block per query: total count and the
first n hits (issues: number, state, date, title, URL; code: repository, path, URL). Code searches
are spaced 7 s apart and issue searches 2.5 s apart; a rate-limit answer waits 65 s and retries once.
"""
import json, pathlib, subprocess, sys, time


def run(kind, q, n):
    args = ["gh", "api", "-X", "GET", f"search/{kind}", "-f", f"q={q}", "-f", f"per_page={max(n, 10)}"]
    if kind == "code":
        args += ["-H", "Accept: application/vnd.github.text-match+json"]
    for attempt in (1, 2):
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout)
        if attempt == 1 and ("rate limit" in p.stderr.lower() or "403" in p.stderr):
            time.sleep(65)
            continue
        return {"error": p.stderr.strip()[:300]}


def main(qfile, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for spec in json.load(open(qfile)):
        n = spec.get("n", 8)
        d = run(spec["kind"], spec["q"], n)
        (out / f"{spec['id']}.json").write_text(json.dumps({"query": spec, "result": d}, indent=1))
        print(f"\n## {spec['id']} [{spec['kind']}] {spec['q']}")
        if "error" in d:
            print("  ERROR", d["error"])
        else:
            print(f"  total {d.get('total_count')}{' (incomplete)' if d.get('incomplete_results') else ''}")
            for it in d.get("items", [])[:n]:
                if spec["kind"] == "issues":
                    repo = it["repository_url"].split("/repos/")[1]
                    print(f"  {repo}#{it['number']} {it['state']} {it['created_at'][:10]} | {it['title'][:100]}")
                else:
                    frag = ""
                    if it.get("text_matches"):
                        frag = it["text_matches"][0].get("fragment", "").replace("\n", " ")[:120]
                    print(f"  {it['repository']['full_name']} {it['path'][-60:]} | {frag}")
        time.sleep(7 if spec["kind"] == "code" else 2.5)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
