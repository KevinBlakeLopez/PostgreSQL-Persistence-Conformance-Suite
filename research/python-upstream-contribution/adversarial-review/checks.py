"""Read-only review checks. No database connections and no harness execution.

Run: python3.14 -I checks.py <PPCS-root> <download-directory>
The download directory contains upstream/ archives and records/ HTTP responses.
"""
import ast
import collections
import hashlib
import html
import json
import pathlib
import re
import shlex
import subprocess
import sys
import tarfile

repo, download = map(pathlib.Path, sys.argv[1:])
print('Review interpreter:', sys.version.replace('\n', ' '))
print('No database programs executed by this script.')

def sha(data):
    return hashlib.sha256(data).hexdigest()

for name, source, output in [
    ('psycopg-1453-comment', 'research/python-ecosystem-contribution-audit/psycopg_transaction_block.py', 'research/python-ecosystem-contribution-audit/psycopg_transaction_block.txt'),
    ('asyncpg-commit-rollback', 'research/python-upstream-contribution/chk-2-asyncpg/asyncpg_commit_rollback.py', 'research/python-upstream-contribution/chk-2-asyncpg/output/asyncio.rep1.out'),
]:
    draft = repo / 'research/python-upstream-contribution/upstream-drafts' / (name + '.md')
    text = draft.read_text()
    rules = list(re.finditer(r'^---$', text, re.M))
    body = text[rules[-2].end()+1:rules[-1].start()]
    blocks = re.findall(r'^```([^\n]*)\n(.*?)^```', body, re.M | re.S)
    for label, path, embedded in [('program', source, next(v for lang, v in blocks if lang == 'python')), ('output', output, blocks[-1][1])]:
        data = (repo / path).read_bytes()
        print(name, label, 'byte-identical:', data == embedded.encode(), 'SHA256:', sha(data))
        assert data == embedded.encode()
    print(name, 'posted links:', re.findall(r'https://[^\s)]+', body))

out = repo / 'research/python-upstream-contribution/chk-2-asyncpg/output'
files = sorted(out.glob('*.rep*.out'))
normalized = [re.sub(r'pg_xact_status\(\d+\)', 'pg_xact_status(X)', p.read_text()).split('\n', 1)[1] for p in files]
print('Normalized six outputs identical:', len(files) == 6 and len(set(normalized)) == 1)
for p in files:
    print(p.name, sha(p.read_bytes()))

# Independent parser: do not import or rely on server_log_sessions.py.
printed = {}
for p in files:
    arm = None
    for line in p.read_text().splitlines():
        if line.split(':', 1)[0] in ('managed', 'explicit', 'raw', 'control'):
            arm = line.split(':', 1)[0]
        m = re.search(r'pg_xact_status\((\d+)\) (\w+)', line)
        if m:
            assert m[1] not in printed
            printed[m[1]] = (p.stem, arm, m[2])
psql = {}
for line in (out / 'psql-xact-status.txt').read_text().splitlines():
    cells = [x.strip() for x in line.split('|')]
    if len(cells) == 4 and cells[2].isdigit():
        assert cells[2] not in psql
        psql[cells[2]] = (cells[0], cells[1], cells[3])
assert printed == psql and len(printed) == 24
sessions = collections.defaultdict(list)
for lineno, line in enumerate((out / 'server.log').read_text().splitlines(), 1):
    m = re.match(r'.*?\[(\d+)\] app=repro-(managed|explicit|raw|control) xid=(\d+) (LOG|ERROR|DETAIL|STATEMENT):\s+(.*)', line)
    if m:
        sessions[m[1]].append((lineno, *m.groups()[1:]))
assert len(sessions) == 24
for pid, records in sessions.items():
    arm = records[0][1]
    captures = [x for x in records if 'select pg_current_xact_id()::text' in x[-1]]
    assert len(captures) == 1
    xid = captures[0][2]
    assert printed[xid][1] == arm
    errors = [x for x in records if x[3] == 'ERROR']
    assert len(errors) == 1 and 'duplicate key' in errors[0][-1]
    statements = [x[-1].removeprefix('statement: ') for x in records if x[3] == 'LOG' and x[-1].startswith('statement: ')]
    controls = [x for x in statements if re.match(r'^(BEGIN|COMMIT|SAVEPOINT|ROLLBACK|RELEASE)\b', x)]
    assert controls[-1] == ('COMMIT' if arm == 'raw' else 'COMMIT;')
    assert not any(x.startswith('ROLLBACK') for x in controls) if arm != 'control' else any(x.startswith('ROLLBACK TO') for x in controls)
    print('Independent log match:', printed[xid][0], arm, 'pid', pid, 'xid', xid, 'fate', printed[xid][2], 'lines', records[0][0], '-', records[-1][0], 'controls', controls)
print('Independent check: 24/24 log sessions match script and psql; 18 aborted, 6 committed.')

for name, archive, prefix, source in [
    ('psycopg', 'psycopg.tar.gz', 'psycopg-psycopg-9935680', 'psycopg/psycopg/transaction.py'),
    ('asyncpg', 'asyncpg.tar.gz', 'MagicStack-asyncpg-13b0191', 'asyncpg/transaction.py'),
]:
    root = download / 'upstream' / prefix
    head = json.loads((download / 'records' / (name + '-head.json')).read_text())['sha']
    print(name, 'default branch SHA:', head)
    with tarfile.open(download / 'upstream' / (name + '-release.tar.gz')) as tar:
        member = next(x for x in tar.getmembers() if x.name.endswith('/' + source))
        released = tar.extractfile(member).read()
    print(name, 'release transaction.py identical to master:', released == (root / source).read_bytes(), sha(released))
    assert released == (root / source).read_bytes()
    print(name, 'root inventory:', sorted(p.name for p in root.iterdir()))
    for directory in (root, root / '.github', root / 'docs'):
        candidates = list(directory.iterdir()) if directory == root else list(directory.rglob('*'))
        policy = [str(p.relative_to(root)) for p in candidates if p.is_file() and any(x in p.name.lower() for x in ('contrib', 'conduct', 'security', 'issue_template', 'agents', 'claude'))]
        print(name, 'policy/template paths in', directory.name, ':', policy)
    # Scan both try/except and exception-catching context managers. Resolve
    # simple local transaction aliases as well as direct transaction() calls.
    count = 0
    for p in sorted((root / 'tests').rglob('*.py')):
        tree = ast.parse(p.read_text()); count += 1
        for fn in [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            aliases = set()
            for n in ast.walk(fn):
                if isinstance(n, (ast.Assign, ast.AnnAssign)) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'transaction':
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    aliases.update(t.id for t in targets if isinstance(t, ast.Name))
            def is_transaction(expr):
                return (isinstance(expr, ast.Name) and expr.id in aliases) or (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == 'transaction')
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'commit' and name == 'asyncpg':
                    print(name, 'explicit commit test call', str(p.relative_to(root)), n.lineno)
                if not isinstance(n, (ast.With, ast.AsyncWith)) or not any(is_transaction(i.context_expr) for i in n.items):
                    continue
                for nested in ast.walk(n):
                    if isinstance(nested, (ast.Try, ast.TryStar)) and nested.handlers:
                        print(name, 'try/except inside transaction', str(p.relative_to(root)), nested.lineno, [ast.unparse(h.type) if h.type else 'bare' for h in nested.handlers])
                    if not isinstance(nested, (ast.With, ast.AsyncWith)) or nested is n:
                        continue
                    for item in nested.items:
                        e = item.context_expr
                        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and 'raises' in e.func.attr.lower():
                            print(name, 'catching context inside transaction', str(p.relative_to(root)), fn.name, 'transaction line', n.lineno, 'catch line', nested.lineno, ast.unparse(e))
    print(name, 'AST parsed test files:', count)

for p in sorted((download / 'records').glob('search-*.json')):
    data = json.loads(p.read_text())
    print(p.name, 'total', data.get('total_count'), 'incomplete', data.get('incomplete_results'), 'error', data.get('message'))
    print([(x['number'], x['title']) for x in data.get('items', [])])
for p in sorted((download / 'records').glob('*discussions*.html')):
    items = {}
    for url, title in re.findall(r'href="(/[^" ]+/discussions/\d+)"[^>]*>(.*?)</a>', p.read_text(), re.S):
        if '<svg' not in title:
            items[url] = html.unescape(re.sub('<[^>]+>', '', title)).strip()
    print(p.name, 'discussion results:', items)

p6 = [json.loads(x) for x in (repo / 'research/python-production-failure-gap-analysis/output/p6.jsonl').read_text().splitlines()]
for state in ('57014', '40P01', '40001'):
    rows = [x for x in p6 if x['subject'] == 'asyncpg' and x['sqlstate'] == state]
    assert len(rows) == 3 and all(x['caught'] == state and x['api'].startswith('returned normally') and x['fate'] == 'aborted' and x['marker_visible'] is False for x in rows)
    print('P6 asyncpg:', state, '3/3 returned normally, aborted, marker absent; backend_after is null in all:', all(x['backend_after'] is None for x in rows))

command = 'DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres python asyncpg_commit_rollback.py [asyncio|uvloop]'
tokens = list(shlex.shlex(command, posix=True, punctuation_chars=True))
print('Command contains shell pipeline token:', '|' in tokens)
result = subprocess.run(['zsh', '-f', '-c', "printf '%s\\n' [asyncio|uvloop]"], capture_output=True, text=True)
print('Shell metasyntax demonstration only (no Python/DB):', result.returncode, result.stderr.strip())

print('Database executable discovery:', {x: subprocess.run(['which', x], capture_output=True, text=True).stdout.strip() for x in ('postgres', 'initdb')})
print('Completed read-only checks.')
