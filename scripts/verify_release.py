import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser(description='Read-only live release/source/settings verification; no provider calls')
parser.add_argument('--baseline',required=True,type=Path)
parser.add_argument('--image',default='forgetfulme-app:local')
args=parser.parse_args()
if not args.baseline.resolve().is_relative_to((root/'backups').resolve()):parser.error('Choose a private baseline inside repository backups/')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'app').rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
def docker(parts,code=None):
 result=subprocess.run(['docker',*parts],cwd=root,input=code,text=True,capture_output=True,check=True)
 return result.stdout
expected_image=json.loads(docker(['image','inspect',args.image]))[0]['Id']
for service in ['web','worker','wiki-worker','library-worker','scheduler']:
 code="""import hashlib,json
from pathlib import Path
actual={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('app').rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert actual==json.loads(%r)
print(len(actual))
""" % json.dumps(manifest)
 count=docker(['compose','exec','-T',service,'python','-'],code).strip()
 state=json.loads(docker(['inspect','forgetfulme-'+service+'-1']))[0]
 assert state['State']['Health']['Status']=='healthy'
 assert state['Image']==expected_image, 'Service does not use the expected tested image'
 assert state['Config']['Labels'].get('com.forgetfulme.app_fingerprint')==fingerprint
 print(service+': healthy, '+count+' app files matched')
baseline=json.loads(args.baseline.read_text())
code="""import hashlib,json,re,http.cookiejar,urllib.request,urllib.parse,urllib.error,os
from pathlib import Path
from app.db import connect
expected=json.loads(%r)
for name,digest in expected['source_manifest'].items():assert hashlib.sha256((Path('/vault')/name).read_bytes()).hexdigest()==digest
with connect() as db:
 assert db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()['automation_enabled']==expected['automation']
 assert db.execute('SELECT enabled FROM ai_settings WHERE id=1').fetchone()['enabled']==expected['ai']
 controls=db.execute('SELECT visits_enabled,history_exports_enabled,downloads_enabled,local_index_enabled,ai_enabled FROM ingestion_controls WHERE id=1').fetchone()
 assert controls==expected.get('ingestion_stages',{name:None for name in controls})
 jobs=db.execute('SELECT state,seen,changed,failed FROM library_index_jobs ORDER BY id DESC LIMIT 1').fetchone()
cookies=http.cookiejar.CookieJar()
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
login_client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies),NoRedirect())
base='http://127.0.0.1:8000'
with client.open(base+'/login',timeout=15) as response:login=response.read().decode()
csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
try:login_client.open(base+'/login',data=urllib.parse.urlencode(dict(username=os.environ['ADMIN_USER'],password=os.environ['ADMIN_PASSWORD'],csrf=csrf)).encode(),timeout=15).close()
except urllib.error.HTTPError as response:
 assert response.code==303 and response.headers.get('Location')=='/'
 response.close()
for route in ['/library','/library/projects','/library/health','/library/questions','/library/pdf','/library/publications','/library/jobs','/library/jobs?section=errors','/library/jobs?section=renames','/vault/wiki','/settings/ai','/settings/ingestion']:
 print('Checking authenticated route: '+route,flush=True)
 with client.open(base+route,timeout=30) as response:
  assert response.status==200 and response.url==base+route
  assert '<main id="main">' in response.read().decode()
print(json.dumps({'original_sources_preserved':len(expected['source_manifest']),'automation':expected['automation'],'ai':expected['ai'],'ingestion_stages_preserved':True,'new_controls_inherit':all(v is None for v in controls.values()),'authenticated_gets':12,'latest_index_job':jobs}))
""" % json.dumps(baseline)
print(docker(['compose','exec','-T','web','python','-'],code).strip())
print('Release app fingerprint: '+fingerprint)
