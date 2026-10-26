"""Check an installed SQLAlchemy against its wheel RECORD, and selected modules against a source tree.

Usage: python -I check_install.py <site-packages> <dist-info-name> <tag-src-dir> <module> [<module> ...]
<tag-src-dir> holds files extracted with `git show <tag>:lib/sqlalchemy/<module>`.
"""
import base64, csv, hashlib, os, sys

site, dist, src = sys.argv[1:4]
modules = sys.argv[4:]
bad, ok, missing = [], 0, []
with open(os.path.join(site, dist, "RECORD"), newline="") as f:
    for path, h, size in csv.reader(f):
        if not h or not path.startswith("sqlalchemy/"):
            continue
        algo, digest = h.split("=", 1)
        try:
            data = open(os.path.join(site, path), "rb").read()
        except FileNotFoundError:
            missing.append(path)
            continue
        d = base64.urlsafe_b64encode(hashlib.new(algo, data).digest()).rstrip(b"=").decode()
        if d != digest:
            bad.append(path)
        else:
            ok += 1
print(f"{dist}: sqlalchemy files matching RECORD: {ok} | mismatched: {bad} | missing: {missing[:5]}")
for m in modules:
    a = open(os.path.join(site, "sqlalchemy", m), "rb").read()
    b = open(os.path.join(src, m), "rb").read()
    print(("identical" if a == b else "DIFFERS") + f": {m} (sha256 {hashlib.sha256(a).hexdigest()[:16]})")
