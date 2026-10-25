import ast, hashlib, json, pathlib, re, subprocess
r=pathlib.Path(__file__).parent
repo=pathlib.Path('$WORKTREE')
chk=repo/'research/python-upstream-contribution/chk-5-tortoise'
readme=(chk/'README.md').read_text()
sha=lambda b:hashlib.sha256(b).hexdigest()
hashes={}
for p in chk.rglob('*'):
    if p.is_file() and p.name!='README.md':
        h=sha(p.read_bytes()); hashes[str(p.relative_to(chk))]={'sha256':h,'listed_in_readme':h in readme}
print('FILES',json.dumps(hashes,indent=2))
draft=(repo/'research/python-upstream-contribution/upstream-drafts/tortoise-save-after-rollback.md').read_text()
draft_body=draft.split("\n---\n")[1]
blocks=re.findall(r'<details>.*?```[^\n]*\n(.*?)\n```.*?</details>',draft_body,re.S)
log=(chk/'output/server-log-extract.txt').read_text().splitlines(keepends=True)
expected=[(chk/'tortoise_save_after_rollback.py').read_text(),(chk/'output/asyncpg.rep1.out').read_text(),''.join(log[15:25])+'…\n'+''.join(log[38:50])]
for i,(a,b) in enumerate(zip(blocks,expected)):
    print('DETAIL',i+1,'byte-identical',a+'\n'==b,'sha256',sha((a+'\n').encode()),sha(b.encode()))
commits=['972e82a','d92490e','4442ae2']
paths=set()
for c in commits:
    names=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',c],cwd=repo,text=True).splitlines()
    for p in names: paths.add((c,p))
patterns={'local-personal-path':r'(?:/Users/|/home/|[A-Z]:\\Users\\)[^\s`\"\']+', 'token':r'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY-----)', 'password-value':r'(?i)(?:postgres(?:ql)?://[^:\s]+:)[^@\s]{4,}@'}
hits=[]
for c,p in sorted(paths):
    data=subprocess.check_output(['git','show',c+':'+p],cwd=repo).decode()
    for n,line in enumerate(data.splitlines(),1):
        for kind,pat in patterns.items():
            for match in re.finditer(pat,line):
                if '<password>' not in match.group() and '<pw>' not in match.group():hits.append((c,p,n,kind))
print('COMMITTED_BLOBS',len(paths),'SCAN_HITS',hits)
for rev in ['develop','tag']:
    base=r/rev
    print('REV',rev)
    for p in ['tortoise/models.py','tortoise/backends/base/executor.py','tortoise/backends/base/client.py','tortoise/backends/asyncpg/client.py','tortoise/backends/psycopg/client.py','tortoise/transactions.py']:
        data=(base/p).read_bytes()
        print(p,sha(data),'README-hash',sha(data) in readme)
    tree=ast.parse((base/'tortoise/models.py').read_text())
    model=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Model')
    save=next(n for n in model.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='save')
    (r/(rev+'-save.txt')).write_text(ast.get_source_segment((base/'tortoise/models.py').read_text(),save))
    print('save source lines',save.lineno,save.end_lineno)
    catches=[]; tx=[]; count=0
    funcs=[]
    for p in (base/'tests').rglob('*.py'):
        t=ast.parse(p.read_text())
        for n in ast.walk(t):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test'):
                count+=1
            if isinstance(n,(ast.Try,ast.With,ast.AsyncWith)):
                s=ast.get_source_segment(p.read_text(),n)
                iscatch=isinstance(n,ast.Try) or any(x in s.split(':\n',1)[0] for x in ['raises','assertRaises','suppress'])
                if iscatch:
                    catches.append(f'{p.relative_to(base)}:{n.lineno}-{n.end_lineno}\n{s}\n')
                    if any(x in s for x in ['in_transaction(', 'atomic(', '_in_transaction(']):tx.append(catches[-1])
    print('test functions',count,'catch constructs',len(catches),'direct transactional catch constructs',len(tx))
    (r/(rev+'-test-catches.txt')).write_text('\n'.join(catches))
    (r/(rev+'-test-tx-catches.txt')).write_text('\n'.join(tx))
body=draft.split('\n---\n')[1]
visible=re.sub(r'<details>.*?</details>','',body,flags=re.S)
visible=re.sub(r'\]\(.*?\)',']',visible)
print('VISIBLE nonempty source lines',len([x for x in visible.splitlines() if x.strip()]),'words',len(visible.split()))
print('P45 rep hashes',[(p.name,sha(p.read_bytes())) for p in (repo/'research/python-production-failure-gap-analysis/output').glob('p45.rep*.out')])
