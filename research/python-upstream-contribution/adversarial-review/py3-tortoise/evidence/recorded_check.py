import collections,pathlib,re
r=pathlib.Path(__file__).parent
p=pathlib.Path('$WORKTREE/research/python-upstream-contribution/chk-5-tortoise/output')
ids={}
for f in p.glob('*.out'):
    for xid,status in re.findall(r'pg_xact_status\((\d+)\) (\w+)',f.read_text()):
        assert xid not in ids
        ids[xid]=status
psql=dict(re.findall(r'\|\s*(\d+)\s*\|\s*(committed|aborted)\s*$',(p/'psql-xact-status.txt').read_text(),re.M))
log=(p/'server-log-extract.txt').read_text()
ends={}
for line in log.splitlines():
    m=re.search(r'xid=(\d+) LOG:  (?:statement: |execute [^:]+: )(COMMIT|ROLLBACK)(?:;)?\s*$',line)
    if m:ends[m[1]]='committed' if m[2]=='COMMIT' else 'aborted'
print('printed IDs',len(ids),'PSQL IDs',len(psql),'PSQL mismatches',[(k,v,psql.get(k)) for k,v in ids.items() if psql.get(k)!=v])
print('transaction-ending statement mismatches',[(k,v,ends.get(k)) for k,v in ids.items() if ends.get(k)!=v])
entries=re.split(r'(?=^\d{4}-\d\d-\d\d .+? UTC \[\d+\] app=)',log,flags=re.M)
counts=[]
for e in entries:
    if re.search(r'Query Text: UPDATE',e):
        m=re.search(r'->  .*?\(actual rows=([0-9.]+) loops=(\d+)\)',e)
        counts.append(m.groups() if m else None)
print('UPDATE child scan row/loop counts',collections.Counter(counts))
print('fates',collections.Counter(ids.values()))
