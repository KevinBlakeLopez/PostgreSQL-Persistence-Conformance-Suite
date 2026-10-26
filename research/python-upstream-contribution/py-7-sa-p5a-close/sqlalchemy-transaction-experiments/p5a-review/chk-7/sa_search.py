"""Read-only GitHub searches of sqlalchemy/sqlalchemy through `gh` (issues, PRs, discussions).

Usage: python -I sa_search.py <out.json>
Writes every query, its result count and its hits. Nothing is posted.
"""
import json, subprocess, sys

REPO = "sqlalchemy/sqlalchemy"
SINCE = "2026-10-18"

P5A_ISSUE_QUERIES = [  # the review's evidence index, 2026-10-18
    'commit "idle in transaction"', "failed commit close pool rollback", "transaction_was_reset",
    "skip_reset", "_close_no_reset", '"Reset agent is not active"',
    "commit exception connection returned to pool", "commit fails rollback not called",
    "inactive transaction close rollback", '"rollback() fully" commit failed',
    "commit error next checkout transaction", "reset on return commit failed",
]
P5A_DISCUSSION_QUERIES = [  # the review lists "five similar queries" without their text; these are mine
    "transaction_was_reset", "failed commit close pool", "commit exception connection returned to pool",
    'commit "idle in transaction"', "reset on return commit failed",
]
RECIPE_QUERIES = [
    "reset_on_return", "DISCARD", '"RESET ALL"', "reset event psycopg", '"DISCARD ALL"', '"DISCARD TEMP"',
    "postgresql_reset_on_return", '"Resource Reset"', '"CLOSE ALL"', "pool reset event postgresql",
    "pool_reset_on_return psycopg", "_reset_postgresql",
]

GQL = """query($q: String!, $after: String) {
  search(query: $q, type: %s, first: 100, after: $after) {
    issueCount discussionCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue { number title state createdAt updatedAt url __typename }
      ... on PullRequest { number title state createdAt updatedAt url __typename }
      ... on Discussion { number title createdAt updatedAt url category { name } __typename }
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
        if not data["pageInfo"]["hasNextPage"] or len(nodes) >= 300:
            count = data["issueCount"] if kind == "ISSUE" else data["discussionCount"]
            return count, nodes
        after = data["pageInfo"]["endCursor"]


out = []


def run(group, kind, q):
    count, nodes = search(kind, q)
    out.append({"group": group, "kind": kind, "query": q, "count": count, "hits": nodes})
    print(f"{group:28s} {kind:10s} {count:5d}  {q}", flush=True)


for q in P5A_ISSUE_QUERIES:
    run("p5a-issues-all-time", "ISSUE", q)  # issues and PRs; filtered by date afterwards
for q in P5A_DISCUSSION_QUERIES:
    run("p5a-discussions-all-time", "DISCUSSION", q)
run("created-since", "ISSUE", f"created:>={SINCE}")
run("created-since", "DISCUSSION", f"created:>={SINCE}")
run("updated-since", "ISSUE", f"updated:>={SINCE}")
run("updated-since", "DISCUSSION", f"updated:>={SINCE}")
for q in RECIPE_QUERIES:
    run("recipe-issues-all-time", "ISSUE", q)
    run("recipe-discussions-all-time", "DISCUSSION", q)
json.dump(out, open(sys.argv[1], "w"), indent=1)
