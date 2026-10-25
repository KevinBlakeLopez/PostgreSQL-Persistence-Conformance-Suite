import collections,json,os,pathlib,re,subprocess
r=pathlib.Path(__file__).parent
c=json.loads((r/'connection.json').read_text());env=dict(os.environ,DOCKER_CONTEXT='colima')
def docker(*args):return subprocess.check_output(['docker',*args],env=env,stderr=subprocess.STDOUT,text=True)
log=docker('logs',c['name']);(r/'server.full.log').write_text(log)
ids={}
for p in (r/'outputs').glob('*.out'):
    for xid,status in re.findall(r'pg_xact_status\((\d+)\) (\w+)',p.read_text()):
        ids[xid]=(status,p.name)
query="select x,pg_xact_status(x::xid8) from unnest(array["+','.join("'"+x+"'" for x in ids)+"]) x;"
result=docker('exec',c['name'],'psql','-X','-A','-t','-U','postgres','-d','postgres','-c',query)
(r/'psql-xact-status.txt').write_text(query+'\n'+result)
got=dict(line.split('|') for line in result.splitlines())
print('PSQL',len(got),'transaction IDs; mismatches',[(x,s,got.get(x)) for x,(s,_) in ids.items() if got.get(x)!=s])
entries=re.split(r'(?=^\d{4}-\d\d-\d\d .+? UTC \[\d+\] app=)',log,flags=re.M)
sessions=collections.defaultdict(list)
for e in entries:
    m=re.match(r'.*?\[(\d+)\] app=(repro-tortoise|repro-django|repro-sqlalchemy) xid=(\d+) (.*)',e,re.S)
    if m:sessions[(m[1],m[2])].append((m[3],m[4]))
for key,es in sessions.items():
    tx=[]
    print('\nSESSION',key)
    for xid,e in es:
        sql=re.search(r'LOG:  (?:execute [^:]+: |statement: )(.*?)(?:\n|$)',e)
        if sql:
            s=sql[1]
            if s.lower().startswith(('begin','savepoint','release','rollback','commit','insert','update','select pg_current')):
                tx.append((xid,s))
                print('xid='+xid,s)
                if s.upper().startswith(('COMMIT','ROLLBACK;','ROLLBACK TRANSACTION;')):
                    if xid in ids:print('  PSQL FATE',got[xid],ids[xid][1])
        if 'Query Text: UPDATE' in e or 'Query Text: update' in e:
            scan=re.search(r'->  .*?\(actual rows=([0-9.]+) loops=(\d+)\)',e)
            print('  UPDATE child scan:',scan.groups() if scan else 'inspect manually')
(r/'settings.txt').write_text(docker('exec',c['name'],'psql','-X','-U','postgres','-d','postgres','-c',"select version(); show log_statement; show log_line_prefix; show auto_explain.log_analyze; show synchronous_commit; show default_transaction_isolation; show statement_timeout; show idle_in_transaction_session_timeout;"))
