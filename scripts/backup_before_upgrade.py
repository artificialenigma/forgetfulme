import json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
from datetime import datetime
from zoneinfo import ZoneInfo
backup=root/'backups'/('upgrade-'+datetime.now(ZoneInfo('Indian/Maldives')).strftime('%Y-%m-%d-%H%M%S'));backup.mkdir(mode=0o700)
compose=['docker','compose']
def save(name,parts,input=None):
    target=backup/name
    with target.open('wb') as output:
        os.chmod(target,0o600)
        subprocess.run(compose+parts,input=input,stdout=output,stderr=subprocess.PIPE,cwd=root,check=True)
    return target
baseline=b'''import hashlib,json
from pathlib import Path
from app.db import connect
vault=Path('/vault');files={}
for path in vault.rglob('*'):
 relative=path.relative_to(vault)
 if path.is_file() and not path.is_symlink() and not any(part.startswith('.') for part in relative.parts) and relative.parts[0]!='Forgetful Me':
  files[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
with connect() as db:
 controls=db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()
 ai=db.execute('SELECT enabled FROM ai_settings WHERE id=1').fetchone()
 stages=db.execute('SELECT visits_enabled,history_exports_enabled,downloads_enabled,local_index_enabled,ai_enabled FROM ingestion_controls WHERE id=1').fetchone() if db.execute("SELECT to_regclass('ingestion_controls') AS name").fetchone()['name'] else None
print(json.dumps({'automation':controls['automation_enabled'],'ai':ai['enabled'],'source_manifest':files,**({'ingestion_stages':stages} if stages is not None else {})}))
'''
subprocess.run(compose+['stop','--timeout','30','worker','wiki-worker','library-worker','scheduler'],cwd=root,check=True,capture_output=True)
save('baseline.json',['exec','-T','web','python','-'],baseline)
save('database-before-second-delivery.sql',['exec','-T','db','pg_dump','-U','forgetfulme','forgetfulme'])
save('vault-before-second-delivery.tar.gz',['exec','-T','web','tar','-czf','-','-C','/vault','.'])
prior=root/'backups/upgrade-2026-10-06/baseline.json'
previous=json.loads(prior.read_text()) if prior.is_file() else {'source_manifest':{}}
current=json.loads((backup/'baseline.json').read_text())
changes=sum(current['source_manifest'].get(p)!=digest for p,digest in previous['source_manifest'].items())
print(json.dumps({'original_files':len(current['source_manifest']),'original_baseline_changes':changes,'automation':current['automation'],'ai':current['ai'],'saved_backup_files':3}))
print('Fresh backup saved: '+str(backup)+'; compare this baseline after rollout. Earlier changes are retained, never reverted.')
