#!/usr/bin/env python3
"""Test the real app HTML extractor against a disposable Crawl4AI service."""
import argparse,json,re,secrets,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--report',required=True,type=Path);p.add_argument('--patched-dependencies',action='store_true');a=p.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}',a.image) or not a.report.resolve().is_relative_to((ROOT/'reports').resolve()):p.error('Exact candidate image and repository report path required')
name='forgetfulme-crawler-check-'+secrets.token_hex(5);net=name+'-net';created=[]
def run(*args,input=None):
 r=subprocess.run(['docker',*args],input=input,capture_output=True)
 if r.returncode:raise RuntimeError('Disposable crawler command failed: '+args[0]+'; synthetic output: '+r.stderr.decode(errors='replace')[-1600:])
 return r.stdout
try:
 run('network','create','--internal',net);created.append(('network',net))
 run('run','-d','--name',name,'--network',net,'--network-alias','crawler','--shm-size','1g','-e','SECRET_KEY=synthetic-crawler-secret-with-more-than-thirty-two-bytes',a.image);created.append(('container',name))
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  check=subprocess.run(['docker','exec',name,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:11235/health',timeout=2)"],capture_output=True,timeout=10)
  if check.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Disposable crawler did not become healthy')
 test='''import os,warnings,importlib.metadata as m
os.environ['CRAWL4AI_URL']='http://crawler:11235'
os.environ.pop('CRAWL4AI_API_TOKEN',None)
from app.crawl4ai_client import extract_html
html='''+repr('''<html><head><title>Synthetic crawl</title><script>fetch('http://nowhere.invalid/leak')</script></head><body><main><h1>Synthetic Upgrade Evidence</h1><p>This synthetic paragraph contains enough readable content to verify the real HTML to Markdown API after dependency and operating system updates.</p><p>Unicode Café and ދިވެހި remain readable.</p><a href="/evidence">Synthetic citation link</a><img src="http://nowhere.invalid/track" onerror="fetch('/leak')"><iframe src="http://nowhere.invalid/frame"></iframe></main></body></html>''')+'''
markdown=extract_html(html,'https://synthetic.invalid/source')
assert 'Synthetic Upgrade Evidence' in markdown and 'readable content' in markdown
assert 'Café' in markdown and 'ދިވެހި' in markdown
assert 'https://synthetic.invalid/evidence' in markdown
assert 'nowhere.invalid' not in markdown and 'fetch(' not in markdown
print('PASS real application raw HTML extraction, Unicode, absolute citations and active-resource stripping')
'''
 print(run('run','--rm','-i','--network',net,'forgetfulme-test:b1258a3cddfe','python','-',input=test.encode()).decode().strip())
 run('restart',name)
 deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  if subprocess.run(['docker','exec',name,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:11235/health',timeout=2)"],capture_output=True).returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Crawler restart readiness failed')
 print(run('run','--rm','-i','--network',net,'forgetfulme-test:b1258a3cddfe','python','-',input=test.encode()).decode().strip())
 if a.patched_dependencies:
  dependency_check='''import warnings,importlib.metadata as m
with warnings.catch_warnings(record=True) as seen:
 warnings.simplefilter('always');import requests
assert not any(type(w.message).__name__=='RequestsDependencyWarning' for w in seen)
assert m.version('PyJWT')=='2.14.0' and m.version('urllib3')=='2.8.0' and m.version('chardet')=='5.2.0'
import jwt
key='synthetic-only-key-with-more-than-thirty-two-bytes'
good=jwt.encode({'sub':'synthetic'},key,algorithm='HS256')
assert jwt.decode(good,key,algorithms=['HS256'])['sub']=='synthetic'
bad=jwt.encode({'sub':'synthetic'},'different-synthetic-key-with-more-than-thirty-two-bytes',algorithm='HS256')
try:jwt.decode(bad,key,algorithms=['HS256'])
except jwt.InvalidSignatureError:pass
else:raise AssertionError('Wrong signature accepted')
unsigned=jwt.encode({'sub':'synthetic'},key=None,algorithm='none')
try:jwt.decode(unsigned,key,algorithms=['HS256'])
except jwt.InvalidAlgorithmError:pass
else:raise AssertionError('Unsigned algorithm accepted')
from auth import create_access_token,verify_token,get_token_dependency
from datetime import timedelta
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
good=create_access_token({'sub':'synthetic'})
assert verify_token(HTTPAuthorizationCredentials(scheme='Bearer',credentials=good))['sub']=='synthetic'
for token in [unsigned,bad,create_access_token({'sub':'synthetic'},timedelta(seconds=-60)),jwt.encode({'sub':'synthetic'},__import__('os').environ['SECRET_KEY'],algorithm='HS256')]:
 try:verify_token(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token))
 except HTTPException as e:assert e.status_code==401
 else:raise AssertionError('Invalid token accepted')
assert get_token_dependency({'security':{'jwt_enabled':False}})() is None
assert callable(get_token_dependency({'security':{'jwt_enabled':True}}))
print('PASS pinned dependencies, Requests warning check, auth token signatures/expiry/algorithm restrictions')
'''
  print(run('exec',name,'python','-c',dependency_check).decode().strip())
  # Exercise the server dependency, rather than only JWT library functions.
  run('exec','--user','root',name,'python','-c',"from pathlib import Path; import yaml; p=Path('/app/config.yml'); c=yaml.safe_load(p.read_text()); c.setdefault('security',{})['jwt_enabled']=True; p.write_text(yaml.safe_dump(c))")
  run('restart',name)
  deadline=time.monotonic()+60
  while time.monotonic()<deadline:
   if subprocess.run(['docker','exec',name,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:11235/health',timeout=2)"],capture_output=True).returncode==0:break
   time.sleep(1)
  else:raise RuntimeError('JWT-enabled API readiness failed')
  api_check='''import json,urllib.request,urllib.error
from datetime import timedelta
from auth import create_access_token
payload={'urls':['raw:<html><body><h1>Synthetic JWT evidence</h1><p>This is a long synthetic paragraph for exercising authenticated local raw HTML extraction with no external network requests.</p></body></html>'],'browser_config':{'type':'BrowserConfig','params':{'headless':True,'java_script_enabled':False}},'crawler_config':{'type':'CrawlerRunConfig','params':{'word_count_threshold':1}}}
def call(token):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 request=urllib.request.Request('http://127.0.0.1:11235/crawl',data=json.dumps(payload).encode(),headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=30) as response:return response.status,json.loads(response.read())
 except urllib.error.HTTPError as error:return error.code,None
assert call(None)[0]==401
assert call('synthetic-invalid-token')[0]==401
assert call(create_access_token({'sub':'synthetic'},timedelta(seconds=-60)))[0]==401
status,result=call(create_access_token({'sub':'synthetic'}))
assert status==200 and result['success'] and result['results'][0]['success']
print('PASS JWT-enabled API rejects absent/invalid/expired tokens and accepts authenticated raw extraction')
'''
  print(run('exec',name,'python','-c',api_check).decode().strip())
 versions=json.loads(run('exec',name,'python','-c',"import json,importlib.metadata as m; print(json.dumps({n:m.version(n) for n in ['crawl4ai','PyJWT','requests','urllib3','chardet']}))"))
 a.report.write_text(json.dumps({'image':a.image,'versions':versions,'internal_network':True,'published_ports':False,'production_mounts':False,'provider_calls':False,'real_app_extraction_before_after_restart':'passed','jwt_api_authentication':'passed' if a.patched_dependencies else 'not exercised','patched_dependency_and_jwt_checks':a.patched_dependencies},indent=2)+'\n')
except Exception:
 logs=subprocess.run(['docker','logs','--tail','160',name],capture_output=True)
 diagnostic=Path('/tmp')/(name+'-startup.log');diagnostic.write_bytes(logs.stdout+logs.stderr);diagnostic.chmod(0o600)
 print('Synthetic startup diagnostic saved privately: '+str(diagnostic),flush=True)
 raise
finally:
 for kind,resource in reversed(created):subprocess.run(['docker','rm','-f',resource] if kind=='container' else ['docker',kind,'rm',resource],capture_output=True)
