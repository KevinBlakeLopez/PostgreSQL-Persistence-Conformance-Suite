"""Posting-day GitHub searches of sqlalchemy/sqlalchemy for P5a (PY-7). Read-only; nothing is posted.

Usage: python3 -I posting_day_search.py <out.json> <out.txt>

1. CHK-7's 17 queries (sa_search.py), all time; hits created or updated on or after SINCE are listed.
2. Everything created or updated on or after SINCE, issues/PRs and discussions.
3. New queries for the two triggers that replace no DBAPI method, all time; every hit is listed.
4. Anything authored by AUTHOR in the repository, all time.
"""
import json, subprocess, sys, time, datetime

REPO = "sqlalchemy/sqlalchemy"
SINCE = "2026-10-25"  # CHK-7's search ran 2026-10-25 01:24 UTC; this overlaps it from midnight UTC
AUTHOR = "KevinBlakeLopez"

CHK7_ISSUE_QUERIES = [
    'commit "idle in transaction"', "failed commit close pool rollback", "transaction_was_reset",
    "skip_reset", "_close_no_reset", '"Reset agent is not active"',
    "commit exception connection returned to pool", "commit fails rollback not called",
    "inactive transaction close rollback", '"rollback() fully" commit failed',
    "commit error next checkout transaction", "reset on return commit failed",
]
CHK7_DISCUSSION_QUERIES = [
    "transaction_was_reset", "failed commit close pool", "commit exception connection returned to pool",
    'commit "idle in transaction"', "reset on return commit failed",
]
TRIGGER_QUERIES = [
    "commit listener exception", "commit event exception rollback", "ConnectionEvents commit raise",
    '"Explicit commit() forbidden"', "psycopg transaction() commit", "dispatch.commit",
]

GQL = """query($q: String!, $after: String) {
  search(query: $q, type: %s, first: 100, after: $after) {
    issueCount discussionCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue { number title state createdAt updatedAt url author { login } __typename }
      ... on PullRequest { number title state createdAt updatedAt url author { login } __typename }
      ... on Discussion { number title createdAt updatedAt url author { login } category { name } __typename }
    }
  }
}"""


def search(kind, q):
    nodes, after = [], None
    while True:
        args = ["gh", "api", "graphql", "-f", "query=" + GQL % kind, "-f", f"q=repo:{REPO} {q}"]
        if after:
            args += ["-f", f"after={after}"]
        data = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)["data"]["search"]
        nodes += data["nodes"]
        time.sleep(1)
        if not data["pageInfo"]["hasNextPage"] or len(nodes) >= 300:
            return (data["issueCount"] if kind == "ISSUE" else data["discussionCount"]), nodes
        after = data["pageInfo"]["endCursor"]


def line(n):
    kind = n["__typename"]
    state = n.get("state") or (n.get("category") or {}).get("name", "")
    return (f"    {kind:11s} #{n['number']:<6d} {state:16s} created {n['createdAt'][:10]} updated {n['updatedAt'][:10]}"
            f" by {(n.get('author') or {}).get('login')} | {n['title']}")


def recent(n):
    return n["createdAt"][:10] >= SINCE or n["updatedAt"][:10] >= SINCE


def main(out_json, out_txt):
    start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results, text = [], []

    def run(group, kind, q):
        count, nodes = search(kind, q)
        results.append({"group": group, "kind": kind, "query": q, "count": count, "hits": nodes})
        return count, nodes

    text.append(f"== 1. CHK-7's queries, all time; hits created or updated on or after {SINCE} are listed")
    for kind, queries in (("ISSUE", CHK7_ISSUE_QUERIES), ("DISCUSSION", CHK7_DISCUSSION_QUERIES)):
        for q in queries:
            count, nodes = run("chk7-queries", kind, q)
            hits = [n for n in nodes if recent(n)]
            text.append(f"  {kind:10s} {count:4d} results, {len(hits)} recent  | {q}")
            text += [line(n) for n in hits]
    for kind in ("ISSUE", "DISCUSSION"):
        for which in ("created", "updated"):
            count, nodes = run(f"{which}-since", kind, f"{which}:>={SINCE}")
            text.append(f"\n== 2. Everything {which} on or after {SINCE} ({kind}): {count}")
            text += [line(n) for n in nodes]
    text.append("\n== 3. New queries for the two triggers, all time; every hit is listed")
    for q in TRIGGER_QUERIES:
        for kind in ("ISSUE", "DISCUSSION"):
            count, nodes = run("trigger-queries", kind, q)
            text.append(f"  {kind:10s} {count:4d} results  | {q}")
            text += [line(n) for n in nodes]
    text.append(f"\n== 4. Authored by {AUTHOR} in {REPO}, all time")
    for kind in ("ISSUE", "DISCUSSION"):
        count, nodes = run("author", kind, f"author:{AUTHOR}")
        text.append(f"  {kind:10s} {count:4d} results")
        text += [line(n) for n in nodes]
    end = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [f"GitHub GraphQL search of {REPO} through `gh api graphql`, read-only.",
              f"Run {start} to {end}. Every query is prefixed with repo:{REPO}.",
              "ISSUE searches return issues and pull requests; DISCUSSION searches return discussions.", ""]
    json.dump(results, open(out_json, "w"), indent=1)
    open(out_txt, "w").write("\n".join(header + text) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
