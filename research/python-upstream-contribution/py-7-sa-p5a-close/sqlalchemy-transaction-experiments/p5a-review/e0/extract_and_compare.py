import ast, difflib, pathlib, re
draft = pathlib.Path("<repo>/docs/sqlalchemy-p5a-close-issue-draft.md").read_text()
issue = draft.split("````markdown", 1)[1]
repro = issue.split("# Reproduction", 1)[1]
code = repro.split("```python\n", 1)[1].split("\n```", 1)[0] + "\n"
observed = repro.split("Observed on the versions above.", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0] + "\n"
pathlib.Path("draft_script.py").write_text(code)
pathlib.Path("draft_observed.txt").write_text(observed)
assert code.count("127.0.0.1:5432/") == 1, code.count("127.0.0.1:5432/")
local = code.replace("127.0.0.1:5432/", "127.0.0.1:55454/")
pathlib.Path("draft_script_55454.py").write_text(local)
check = pathlib.Path("<repo>/docs/sqlalchemy-transaction-experiments/check/p5a_close.py").read_text()
print("AST(draft with port 55454) == AST(check/p5a_close.py):", ast.dump(ast.parse(local)) == ast.dump(ast.parse(check)))
print("--- textual diff draft(55454) vs check/p5a_close.py ---")
print("".join(difflib.unified_diff(local.splitlines(True), check.splitlines(True), "draft_script_55454.py", "check/p5a_close.py", n=0)))
