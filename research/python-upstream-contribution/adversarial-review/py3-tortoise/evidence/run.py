import hashlib,json,os,pathlib,re,subprocess,sys
r=pathlib.Path(__file__).parent
repo=pathlib.Path('$WORKTREE')
src=repo/'research/python-upstream-contribution/chk-5-tortoise'
conn=json.loads((r/'connection.json').read_text())
env=dict(os.environ,DATABASE_URL=conn['url'],PYTHONDONTWRITEBYTECODE='1')
out=r/'outputs';out.mkdir(exist_ok=True)
def run(name,venv,program,backend):
    cmd=[str(r/venv/'bin/python'),'-I',str(program),backend]
    p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=40)
    (out/name).write_text(p.stdout+p.stderr)
    print(name, 'exit',p.returncode, 'sha256',hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest())
    return p
phase=sys.argv[1]
if phase=='witness-check':
    run('psycopg-extra-plus-witness.out','venv-psycopg',src/'tortoise_save_after_rollback.py','psycopg')
if phase=='install-check':
    for v in ['asyncpg','psycopg']:
        (r/('freeze-'+v+'-initial.txt')).write_text(subprocess.check_output([str(r/f'venv-{v}/bin/pip'),'freeze'],text=True))
        for b in ['asyncpg','psycopg']:
            run(f'install-{v}-run-{b}.out',f'venv-{v}',src/'tortoise_save_after_rollback.py',b)
elif phase=='reproduce':
    for b in ['asyncpg','psycopg']:
        for i in range(1,4):
            p=run(f'{b}.rep{i}.out','venv-asyncpg',src/'tortoise_save_after_rollback.py',b)
            original=(src/f'output/{b}.rep{i}.out').read_text()
            mask=lambda s:re.sub(r'pg_xact_status\(\d+\)','pg_xact_status(XID)',s)
            print('MATCH recorded after masking IDs:',mask(p.stdout)==mask(original))
    for b in ['asyncpg','psycopg']:
        run(f'wrapped-{b}.out','venv-asyncpg',src/'chk5_update_count.py',b)
    run('controls.out','venv-asyncpg',src/'controls_django_sqlalchemy.py','')
    program=(src/'tortoise_save_after_rollback.py').read_text()
    program=re.sub(r'async def current_xid\(conn\):.*?\n\n\nasync def fate\(witness, xid\):.*?\n\n\nasync def rows', 'async def current_xid(conn):\n    return "not-collected"\n\n\nasync def fate(witness, xid):\n    return "not-collected"\n\n\nasync def rows',program,flags=re.S)
    (r/'no-xid.py').write_text(program)
    for b in ['asyncpg','psycopg']:
        run(f'no-xid-{b}.out','venv-asyncpg',r/'no-xid.py',b)
    program=program.replace('"application_name=repro-tortoise"','"application_name=repro-tortoise&minsize=1&maxsize=1"')
    (r/'pool-one-no-xid.py').write_text(program)
    run('pool-one-no-xid-asyncpg.out','venv-asyncpg',r/'pool-one-no-xid.py','asyncpg')
