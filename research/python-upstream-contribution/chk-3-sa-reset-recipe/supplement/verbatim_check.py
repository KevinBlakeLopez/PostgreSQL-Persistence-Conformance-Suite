"""Check that the supplement's two hooks are byte-identical to those in ../chk3_reset_recipe.py.

Usage: python -I verbatim_check.py
The main program's copies were checked against SQLAlchemy's docs and the roadmap by ../verbatim_check.py.
"""
import ast, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def source(path, name):
    src = open(path, encoding="utf-8").read()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return src.splitlines()[node.lineno - 1:node.end_lineno]


ok = True
for name in ("documented_recipe", "corrected_example"):
    same = source(os.path.join(HERE, "chk3_supplement.py"), name) == source(
        os.path.join(HERE, "..", "chk3_reset_recipe.py"), name)
    ok &= same
    print(f"{name}: {'identical to' if same else 'DIFFERS from'} ../chk3_reset_recipe.py")
sys.exit(0 if ok else 1)
