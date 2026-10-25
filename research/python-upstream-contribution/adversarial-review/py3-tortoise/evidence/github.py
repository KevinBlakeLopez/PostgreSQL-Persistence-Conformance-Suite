import json, pathlib, subprocess, time
r=pathlib.Path(__file__).parent
out=r/'github'; out.mkdir(exist_ok=True)
def get(name,*args):
    p=subprocess.run(['gh','api',*args],capture_output=True,text=True)
    (out/(name+'.json')).write_text(p.stdout if p.returncode==0 else json.dumps({'error':p.stderr}))
    print(name,p.returncode, len(p.stdout))
for n in [1212,2293,242,1094]:
    get(str(n),f'repos/tortoise/tortoise-orm/issues/{n}')
    get(str(n)+'-comments',f'repos/tortoise/tortoise-orm/issues/{n}/comments','--paginate')
get('2293-pr','repos/tortoise/tortoise-orm/pulls/2293')
get('2293-files','repos/tortoise/tortoise-orm/pulls/2293/files','--paginate')
get('2293-reviews','repos/tortoise/tortoise-orm/pulls/2293/reviews','--paginate')
get('develop','repos/tortoise/tortoise-orm/commits/develop')
get('org-github','repos/tortoise/.github/git/trees/HEAD','-f','recursive=1','-X','GET')
get('recent-commits','repos/tortoise/tortoise-orm/commits','-X','GET','-f','sha=develop','-f','since=2026-10-25T01:30:00Z')
queries=['rollback save','rollback instance','saved_in_db','savepoint save','retry insert','save silently','zero rows','force_update rollback','save after rollback','is:pr rollback','created:>2026-10-25T01:30:00Z','is:pr merged:>2026-10-25T01:30:00Z','updated:>2026-10-25T01:30:00Z']
for i,q in enumerate(queries):
    time.sleep(3)
    get(f'search-{i:02d}','search/issues','-X','GET','-f','q=repo:tortoise/tortoise-orm '+q,'-f','per_page=100')
(out/'queries.json').write_text(json.dumps(queries,indent=2))
