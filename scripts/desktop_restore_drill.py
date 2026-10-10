#!/usr/bin/env python3
"""Rehearse Obsidian startup/restart with private backups in disposable volumes."""
import argparse,hashlib,io,json,re,secrets,subprocess,tarfile,time
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--backup-dir',required=True,type=Path);p.add_argument('--desktop-image',required=True);p.add_argument('--app-image',default='forgetfulme-test:b1258a3cddfe');p.add_argument('--report',required=True,type=Path)
a=p.parse_args();folder=a.backup_dir.resolve();report=a.report.resolve()
if not folder.is_relative_to((ROOT/'backups').resolve()) or not report.is_relative_to((ROOT/'reports').resolve()):p.error('Use repository backup/report directories')
if not re.fullmatch(r'sha256:[a-f0-9]{64}',a.desktop_image) or not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',a.app_image):p.error('Exact desktop ID and retained tested app required')
files={'vault':folder/'vault.tar.gz','config':folder/'obsidian-config.tar.gz'}
if not all(x.is_file() and not x.is_symlink() for x in files.values()):p.error('Matched vault/config backup required')
name='forgetfulme-desktop-restore-'+secrets.token_hex(5);net=name+'-net';created=[]
def run(*args,input=None):
 r=subprocess.run(['docker',*args],input=input,capture_output=True)
 if r.returncode:raise RuntimeError('Disposable desktop command failed: '+args[0]+'; private output suppressed')
 return r.stdout
expected={};skipped={};volumes={}
extract='''import io,os,sys,tarfile
from pathlib import Path
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 t.extractall('/restore',members=[m for m in t.getmembers() if m.isdir() or m.isfile()],filter='data')
for root,dirs,files in os.walk('/restore'):
 os.chown(root,10001,10001)
 for f in files:os.chown(Path(root)/f,10001,10001)
'''
try:
 run('network','create','--internal',net);created.append(('network',net))
 for label,path in files.items():
  data=path.read_bytes();hashes={};skip=0
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
   members=archive.getmembers()
   if len(members)>=100000 or sum(m.size for m in members)>=2*1024**3:raise ValueError('Backup exceeds budget')
   for m in members:
    path=PurePosixPath(m.name)
    if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe archive path')
    if m.isfile():
     key=str(path)
     if key in hashes:raise ValueError('Duplicate archive file')
     hashes[key]=hashlib.sha256(archive.extractfile(m).read()).hexdigest()
    elif not m.isdir():skip+=1
  volume=name+'-'+label;run('volume','create',volume);created.append(('volume',volume));volumes[label]=volume;expected[label]=hashes;skipped[label]=skip
  run('run','--rm','-i','--network','none','--user','root','--mount','type=volume,source='+volume+',target=/restore',a.app_image,'python','-c',extract,input=data)
 def verify(label,allow_added=False):
  check='''import hashlib,json
from pathlib import Path
expected=json.loads(%r);root=Path('/restore')
actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
assert all(actual.get(k)==v for k,v in expected.items() if not (%r and k.startswith('.obsidian/'))),'original source files changed'
if not %r:assert actual==expected
'''%(json.dumps(expected[label]),allow_added,allow_added)
  run('run','--rm','-i','--network','none','--user','10001:10001','--mount','type=volume,source='+volumes[label]+',target=/restore,readonly',a.app_image,'python','-',input=check.encode())
 verify('vault');verify('config')
 run('run','-d','--name',name,'--network',net,'--shm-size','1g','-e','PUID=10001','-e','PGID=10001','-e','TZ=Indian/Maldives','-e','SUBFOLDER=/obsidian/','-e','HARDEN_DESKTOP=true','-e','NO_GAMEPAD=true','-e','NO_WEBCAM=true','--mount','type=volume,source='+volumes['vault']+',target=/vault','--mount','type=volume,source='+volumes['config']+',target=/config',a.desktop_image);created.append(('container',name))
 def ready():
  for _ in range(90):
   r=subprocess.run(['docker','exec',name,'curl','-fsS','http://127.0.0.1:3000/obsidian/'],capture_output=True)
   if r.returncode==0:return
   time.sleep(1)
  raise RuntimeError('Desktop startup HTTP failed within 90 seconds; private output suppressed')
 ready()
 # HTTP alone can pass while the actual desktop process failed.
 process_check="ps -eo args | grep -E '/opt/[Oo]bsidian/obsidian|/usr/lib/obsidian/obsidian' | grep -v grep >/dev/null"
 def process_ready():
  for _ in range(90):
   if subprocess.run(['docker','exec',name,'sh','-c',process_check],capture_output=True).returncode==0:return
   time.sleep(1)
  raise RuntimeError('Obsidian process unavailable after HTTP readiness')
 process_ready()
 run('restart',name);ready();process_ready();verify('vault',True)
 report.write_text(json.dumps({'image':a.desktop_image,'matched_backup':folder.name,'restored_regular_files':{k:len(v) for k,v in expected.items()},'runtime_special_files_skipped':skipped,'http_startup_restart':True,'obsidian_process_running':True,'original_vault_source_files_unchanged':True,'obsidian_workspace_metadata_changes':'allowed only under .obsidian/','internal_network':True,'published_ports':False,'original_config_hashes_verified_before_startup':True,'config_mutations_after_startup':'expected, disposable only','interactive_ui_and_plugin_compatibility':'not evaluated'},indent=2)+'\n')
 print('PASS matched copied config/vault: Obsidian HTTP/process startup/restart and original vault source hashes; interactive UI not claimed')
finally:
 for kind,resource in reversed(created):
  subprocess.run(['docker','rm','-f',resource] if kind=='container' else ['docker',kind,'rm',resource],capture_output=True)
