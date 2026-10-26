# S = the review's scratch directory: venv/ is the fresh PyPI install, sqlalchemy-src/ is
# `git clone --depth 1 --branch rel_2_1_5 https://github.com/sqlalchemy/sqlalchemy.git` (4fbf72c07f5b).
# util/concurrency.py was compared separately afterwards, with the same cmp.
SP="$S/venv/lib/python3.13/site-packages/sqlalchemy"; for f in engine/base.py engine/default.py engine/util.py pool/base.py pool/impl.py dialects/postgresql/psycopg.py dialects/postgresql/_psycopg_common.py util/langhelpers.py orm/session.py; do if cmp -s "$SP/$f" "$S/sqlalchemy-src/lib/sqlalchemy/$f"; then echo "identical: $f"; else echo "DIFFERS: $f"; fi; done
