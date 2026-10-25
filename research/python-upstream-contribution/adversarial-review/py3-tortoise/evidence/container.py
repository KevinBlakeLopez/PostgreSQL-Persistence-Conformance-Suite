import json, os, secrets, socket, subprocess, time
from pathlib import Path
root=Path(__file__).parent
name='ppcs-py3-adversarial-czkemg'
env=dict(os.environ,DOCKER_CONTEXT='colima')
def docker(*args):
    return subprocess.run(['docker',*args],env=env,capture_output=True,text=True,check=True).stdout
print(docker('ps','--format','{{.Names}} {{.Ports}}'))
with socket.socket() as s:
    assert s.connect_ex(('127.0.0.1',55439)) != 0, 'port occupied'
pw=secrets.token_hex(20)
token=secrets.token_hex(12)
data={'name':name,'port':55439,'url':f'postgresql://postgres:{pw}@127.0.0.1:55439/postgres','token':token}
(root/'connection.json').write_text(json.dumps(data))
(root/'connection.json').chmod(0o600)
print(docker('run','-d','--name',name,'-e',f'POSTGRES_PASSWORD={pw}','-p','127.0.0.1:55439:5432','--tmpfs','/var/lib/postgresql','postgres:18.6@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336','postgres','-c',f'cluster_name={token}','-c','max_connections=100','-c','log_lock_waits=on','-c','deadlock_timeout=1s','-c','log_statement=all','-c','log_line_prefix=%m [%p] app=%a xid=%x ','-c','shared_preload_libraries=auto_explain','-c','auto_explain.log_min_duration=0','-c','auto_explain.log_analyze=on','-c','auto_explain.log_timing=off'))
for _ in range(30):
    p=subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],env=env,capture_output=True,text=True)
    if p.returncode==0:break
    time.sleep(0.3)
print(p.stdout)
(root/'container-inspect.json').write_text(docker('inspect','--format','{{json .Config.Image}}',name))
