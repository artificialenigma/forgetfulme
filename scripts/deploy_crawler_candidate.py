#!/usr/bin/env python3
"""Replace only the standalone stack crawler, retaining its container for rollback."""
import argparse,datetime,io,json,os,re,secrets,subprocess,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--test-report',required=True,type=Path);p.add_argument('--modern-server',action='store_true');p.add_argument('--keep-worker-stopped',action='store_true');a=p.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}',a.image):p.error('Exact tested image ID required')
report=a.test_report.resolve()
if not report.is_relative_to((ROOT/'reports').resolve()):p.error('Repository test report required')
proof=json.loads(report.read_text())
if proof.get('image')!=a.image or proof.get('jwt_api_authentication')!='passed' or not proof.get('patched_dependency_and_jwt_checks'):p.error('Candidate must pass real extraction/restart/dependency/auth checks')
if a.modern_server and (not proof.get('modern_server') or not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',proof.get('app_image',''))):p.error('Matching modern-server/app proof required')
def run(*args,input=None):
 r=subprocess.run(['docker',*args],input=input,capture_output=True)
 if r.returncode:raise RuntimeError('Crawler deployment command failed: '+args[0]+'; private output suppressed')
 return r.stdout
old=json.loads(run('inspect','crawl4ai'))[0]
if old['Mounts'] or set(old['NetworkSettings']['Networks'])!={'bridge','forgetfulme_crawl4ai'}:p.error('Unexpected mounts/networks; review compatibility before deployment')
if old['Config']['Cmd']!=['supervisord','-c','supervisord.conf']:p.error('Unexpected crawler command')
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');folder=ROOT/'backups'/('crawler-upgrade-'+stamp);folder.mkdir(mode=0o700)
def save(name,data):
 target=folder/name;target.write_bytes(data);target.chmod(0o600)
save('container-private.json',json.dumps(old).encode())
config=run('exec','crawl4ai','cat','/app/config.yml');save('config-private.yml',config)
environment=old['Config']['Env']
env_before=None;env_after=None;env_written=False
if a.modern_server:
 env_path=ROOT/'.env';env_before=env_path.read_bytes();save('app-env-before-private.env',env_before)
 existing=re.search(r'^(?:export )?CRAWL4AI_API_TOKEN=(.*)$',env_before.decode(),re.M)
 token=existing.group(1).strip().strip("\"'") if existing else ''
 if not token:token=secrets.token_hex(32)
 if not re.fullmatch(r'[A-Za-z0-9._-]{32,}',token):p.error('Existing service token requires explicit compatibility review')
 text=env_before.decode();line='CRAWL4AI_API_TOKEN='+token
 text=re.sub(r'^(?:export )?CRAWL4AI_API_TOKEN=.*$',line,text,flags=re.M) if existing else text.rstrip()+'\n'+line+'\n'
 env_after=text.encode()
 mapping=dict(x.split('=',1) for x in environment);mapping['CRAWL4AI_API_TOKEN']=token
 if len(mapping.get('SECRET_KEY','').encode())<32:mapping['SECRET_KEY']=secrets.token_hex(32)
 environment=[k+'='+v for k,v in mapping.items()]
 default=run('run','--rm','--network','none','--entrypoint','cat',a.image,'/app/config.yml')
 merge='''import sys,json,yaml
data=json.load(sys.stdin);old=yaml.safe_load(data['old']);new=yaml.safe_load(data['new'])
for key in ['llm','redis','crawler']:
 if isinstance(old.get(key),dict):new.setdefault(key,{}).update(old[key])
new['app']['port']=old.get('app',{}).get('port',11235)
print(yaml.safe_dump(new))
'''
 config=run('run','--rm','-i','--network','none','--entrypoint','python',a.image,'-c',merge,input=json.dumps({'old':config.decode(),'new':default.decode()}).encode())
 save('config-modern-private.yml',config)
if any('\n' in x or '\r' in x for x in environment):p.error('Multiline environment needs explicit preservation support')
save('environment-private.env',('\n'.join(environment)+'\n').encode())
prior='crawl4ai-rollback-'+stamp;renamed=False;new=False;worker_stopped=False;disconnected=False
try:
 if env_after is not None:
  if (ROOT/'.env').read_bytes()!=env_before:raise RuntimeError('App environment changed during preparation; retry from current state')
  (ROOT/'.env').write_bytes(env_after);(ROOT/'.env').chmod(0o600);env_written=True
 run('tag',old['Image'],'forgetfulme-crawler-rollback:'+stamp)
 run('stop','--time','30','forgetfulme-worker-1');worker_stopped=True
 run('stop','--time','30','crawl4ai');run('rename','crawl4ai',prior);renamed=True
 run('network','disconnect','forgetfulme_crawl4ai',prior);disconnected=True
 options=['create','--name','crawl4ai','--network','bridge','--shm-size',str(old['HostConfig']['ShmSize']),'--env-file',str(folder/'environment-private.env')]
 for port,bindings in (old['HostConfig'].get('PortBindings') or {}).items():
  for bind in bindings or []:
   spec=(bind['HostIp']+':' if bind['HostIp'] else '')+bind['HostPort']+':'+port
   options.extend(['--publish',spec])
 policy=old['HostConfig']['RestartPolicy']
 if policy['Name'] and policy['Name']!='no':options.extend(['--restart',policy['Name']+(':'+str(policy['MaximumRetryCount']) if policy['Name']=='on-failure' and policy['MaximumRetryCount'] else '')])
 for option in old['HostConfig'].get('SecurityOpt') or []:options.extend(['--security-opt',option])
 run(*options,a.image);new=True
 # Copy preserved private server config without printing it or exposing it in argv.
 archive=io.BytesIO()
 with tarfile.open(fileobj=archive,mode='w') as t:
  member=tarfile.TarInfo('config.yml');member.size=len(config);member.mode=0o644;member.uid=member.gid=999;t.addfile(member,io.BytesIO(config))
 run('cp','-','crawl4ai:/app',input=archive.getvalue())
 run('network','connect','--alias','crawl4ai','forgetfulme_crawl4ai','crawl4ai');run('start','crawl4ai')
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  healthy=subprocess.run(['docker','exec','crawl4ai','python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:11235/health',timeout=2)"],capture_output=True,timeout=10)
  if healthy.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Candidate did not become healthy; restoring original container')
 assert run('inspect','--format','{{.Image}}','crawl4ai').decode().strip()==a.image
 assert run('exec','crawl4ai','cat','/app/config.yml')==config
 if not a.keep_worker_stopped:run('start','forgetfulme-worker-1');worker_stopped=False
 if not a.keep_worker_stopped:run('exec','forgetfulme-worker-1','python','-c',"import urllib.request; from urllib.parse import urlsplit; import os; url=os.environ['CRAWL4AI_URL'].rstrip('/')+'/health'; assert urlsplit(url).hostname=='crawl4ai'; assert urllib.request.urlopen(url,timeout=5).status==200")
 summary={'image':a.image,'previous_image':old['Image'],'retained_stopped_container':prior,'private_backup':folder.name,'ports_networks_preserved':True,'legacy_config_environment_preserved':not a.modern_server,'modern_auth_and_config_migration':a.modern_server,'worker_health_route':not a.keep_worker_stopped,'worker_left_stopped_for_app_rollout':a.keep_worker_stopped,'rollback':'original stopped container retained; automatic recovery on deployment failure'}
 (ROOT/'reports/crawler-rollout-2026-10-07.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
except Exception:
 if env_written:(ROOT/'.env').write_bytes(env_before);(ROOT/'.env').chmod(0o600)
 if new:subprocess.run(['docker','rm','-f','crawl4ai'],capture_output=True)
 if renamed:
  run('rename',prior,'crawl4ai')
  if disconnected:run('network','connect','--alias','crawl4ai','forgetfulme_crawl4ai','crawl4ai')
  run('start','crawl4ai')
 elif old['State']['Running']:subprocess.run(['docker','start','crawl4ai'],capture_output=True)
 raise
finally:
 if worker_stopped and not a.keep_worker_stopped:subprocess.run(['docker','start','forgetfulme-worker-1'],capture_output=True)
