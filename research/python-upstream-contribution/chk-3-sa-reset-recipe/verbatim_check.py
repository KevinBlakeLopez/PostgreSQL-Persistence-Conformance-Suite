"""Check that the code under test in chk3_reset_recipe.py is copied unchanged from its sources.

Usage: python -I verbatim_check.py <sqlalchemy dialects/postgresql/base.py> <roadmap.md> <p7_sa_reset_recipe.py>

Each block is compared after textwrap.dedent, line by line, with trailing whitespace ignored.
"""
import ast, os, sys, textwrap

base_py, roadmap, p7 = sys.argv[1:4]
HERE = os.path.dirname(os.path.abspath(__file__))
program = open(os.path.join(HERE, "chk3_reset_recipe.py"), encoding="utf-8").read()


def lines(path, first, last):
    return open(path, encoding="utf-8").read().splitlines()[first - 1:last]


def inner(src, outer):
    """The decorated function nested in `outer`, decorator included."""
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == outer)
    inner_fn = next(n for n in fn.body if isinstance(n, ast.FunctionDef))
    start = inner_fn.decorator_list[0].lineno if inner_fn.decorator_list else inner_fn.lineno
    return src.splitlines()[start - 1:inner_fn.end_lineno]


def norm(block):
    return [l.rstrip() for l in textwrap.dedent("\n".join(block)).splitlines()]


def find_block(path, first_line_text, n):
    text = open(path, encoding="utf-8").read().splitlines()
    i = next(i for i, l in enumerate(text) if l.strip() == first_line_text)
    return i + 1, text[i:i + n]


checks = [
    ("documented_recipe", "SQLAlchemy dialects/postgresql/base.py 317-326", lines(base_py, 317, 326)),
    ("search_path_on_connect", "SQLAlchemy dialects/postgresql/base.py 359-366", lines(base_py, 359, 366)),
]
start, block = find_block(roadmap, '@event.listens_for(postgresql_engine, "reset")', 14)
checks.append(("corrected_example", f"roadmap lines {start}-{start + 13}", block))
p7_src = open(p7, encoding="utf-8").read()
checks.append(("p7_variant", "p7_sa_reset_recipe.py corrected_reset", inner(p7_src, "corrected_reset")))

ok = True
# demo_reset_recipe.py: its documented_recipe is the docs text; its rollback_then_discard_all is
# the corrected example without the two comments, so it is compared as code (AST), not as text
demo = open(os.path.join(HERE, "demo_reset_recipe.py"), encoding="utf-8").read()
same = norm(inner(demo, "documented_recipe")) == norm(lines(base_py, 317, 326))
print(f"demo documented_recipe: {'identical to' if same else 'DIFFERS from'} SQLAlchemy dialects/postgresql/base.py 317-326")
ok &= same
dump = lambda block: ast.dump(ast.parse(textwrap.dedent("\n".join(block))))
same = dump(inner(demo, "rollback_then_discard_all")) == dump(inner(program, "corrected_example"))
print(f"demo rollback_then_discard_all: {'same AST as' if same else 'DIFFERENT AST from'} corrected_example")
ok &= same
for name, where, ref in checks:
    mine = norm(inner(program, name))
    same = mine == norm(ref)
    ok &= same
    print(f"{name}: {'identical to' if same else 'DIFFERS from'} {where} ({len(mine)} lines)")
    if not same:
        print(f"   {len(mine)} lines here, {len(norm(ref))} in the source")
        for a, b in zip(mine, norm(ref)):
            if a != b:
                print("   mine:", a, "\n   ref: ", b)
sys.exit(0 if ok else 1)
