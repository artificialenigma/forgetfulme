#!/usr/bin/env python3
"""Check the reviewed hardened crawler server with synthetic authenticated calls."""
import argparse,json,re,secrets,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--app-image',required=True);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}',a.image) or not re.fullmatch(r'forgetfulme-test:[a-f0-9]{12}',a.app_image) or not a.report.resolve().is_relative_to((ROOT/'reports').resolve()):p.error('Exact images and repository report required')
name='forgetfulme-modern-crawler-'+secrets.token_hex(5);net=name+'-net';created=[]
def run(*args,input=None):
 r=subprocess.run(['docker',*args],input=input,capture_output=True)
 if r.returncode:raise RuntimeError('Synthetic modern crawler check failed: '+args[0]+'; '+r.stderr.decode(errors='replace')[-1400:])
 return r.stdout
try:
 run('network','create','--internal',net);created.append(('network',net))
 run('run','-d','--name',name,'--network',net,'--network-alias','crawler','--shm-size','1g','-e','SECRET_KEY=synthetic-crawler-jwt-key-at-least-thirty-two-bytes','-e','CRAWL4AI_API_TOKEN=synthetic-static-api-token-at-least-thirty-two-bytes','-e','FORGETFULME_SENTINEL=synthetic-env-marker-never-returned',a.image);created.append(('container',name))
 def ready():
  deadline=time.monotonic()+90
  while time.monotonic()<deadline:
   if subprocess.run(['docker','exec',name,'python','-c',"import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:11235/health',timeout=2).status==200"],capture_output=True,timeout=10).returncode==0:return
   time.sleep(1)
  raise RuntimeError('Modern crawler readiness deadline exceeded')
 client='''import os
os.environ['CRAWL4AI_URL']='http://crawler:11235'
os.environ['CRAWL4AI_API_TOKEN']='synthetic-static-api-token-at-least-thirty-two-bytes'
from app.crawl4ai_client import extract_html
html='<main><h1>Synthetic secure extraction</h1><p>A long readable synthetic paragraph verifies modern authenticated extraction without visiting any external site or invoking providers.</p><p>Café and ދިވެހި remain readable.</p><a href="/evidence">Citation</a><script>fetch("http://nowhere.invalid/leak")</script><img src="http://nowhere.invalid/track"></main>'
markdown=extract_html(html,'https://synthetic.invalid/source')
assert 'Synthetic secure extraction' in markdown and 'Café' in markdown and 'ދިވެހި' in markdown
assert 'https://synthetic.invalid/evidence' in markdown and 'nowhere.invalid' not in markdown
print('PASS real app authenticated raw extraction, Unicode, citations and resource stripping')
'''
 ready();print(run('run','--rm','-i','--network',net,a.app_image,'python','-',input=client.encode()).decode().strip())
 run('restart',name);ready();print(run('run','--rm','-i','--network',net,a.app_image,'python','-',input=client.encode()).decode().strip())
 boundary='''import json,urllib.request,urllib.error,os,copy,importlib.metadata as m,warnings
from datetime import timedelta
from auth import create_access_token
api=os.environ['CRAWL4AI_API_TOKEN']
base={'urls':['raw:<main><h1>Boundary evidence</h1><p>A long synthetic body tests authentication and forbidden request options without using real files, providers or network targets.</p></main>'],'browser_config':{'type':'BrowserConfig','params':{'headless':True,'java_script_enabled':False}},'crawler_config':{'type':'CrawlerRunConfig','params':{'word_count_threshold':1}}}
def request(path='/crawl',body=None,token=None):
 headers={}
 if token:headers['Authorization']='Bearer '+token
 if body is not None:headers['Content-Type']='application/json'
 req=urllib.request.Request('http://127.0.0.1:11235'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=30) as response:return response.status,response.read().decode()
 except urllib.error.HTTPError as error:return error.code,error.read().decode()
assert request('/health')[0]==200
for label,token in [('absent',None),('invalid','invalid-synthetic-token'),('expired',create_access_token({'sub':'synthetic'},expires_delta=timedelta(seconds=-60))),('missing_expiration',__import__('jwt').encode({'sub':'synthetic'},os.environ['SECRET_KEY'],algorithm='HS256'))]:
 status,_=request(body=base,token=token);assert status==401,(label,status)
for path in ['/metrics','/mcp','/monitor/stats']:assert request(path)[0]==401
status,result=request(body=base,token=create_access_token({'sub':'synthetic'}));assert status==200 and json.loads(result)['success']
assert request('/monitor/actions/cleanup',body={},token=create_access_token({'sub':'synthetic'}))[0]==403
for key,value in [('js_code','alert(1)'),('base_url','http://127.0.0.1/'),('proxy','http://127.0.0.1:9999')]:
 body=copy.deepcopy(base);target='browser_config' if key=='proxy' else 'crawler_config';body[target]['params'][key]=value
 status,result=request(body=body,token=api);assert status in (400,403,422),(key,status)
body=copy.deepcopy(base);body['urls']=['file:///synthetic-no-such-file'];assert request(body=body,token=api)[0] in (400,403,422)
body=copy.deepcopy(base);body['urls']=['http://127.0.0.1:11235/health'];assert request(body=body,token=api)[0] in (400,403,422)
body=copy.deepcopy(base);body['crawler_config']['params']['extraction_strategy']={'type':'dict','value':{'type':'LLMConfig','params':{'api_token':'env:FORGETFULME_SENTINEL'}}}
status,result=request(body=body,token=api);assert status in (400,403,422) and os.environ['FORGETFULME_SENTINEL'] not in result
with warnings.catch_warnings(record=True) as seen:
 warnings.simplefilter('always');import requests
assert not any(type(w.message).__name__=='RequestsDependencyWarning' for w in seen)
assert m.version('crawl4ai')=='0.9.4' and m.version('anyio')=='4.14.2' and m.version('nltk')=='3.10.3'
try:m.version('litellm')
except m.PackageNotFoundError:pass
else:raise AssertionError('Superseded LiteLLM distribution remains')
print('PASS full auth gate, JWT expiry, forbidden config/file/private destinations, wrapped env-config rejection and pinned active dependencies')
'''
 print(run('exec',name,'python','-c',boundary).decode().strip())
 a.report.write_text(json.dumps({'image':a.image,'app_image':a.app_image,'modern_server':True,'jwt_api_authentication':'passed','patched_dependency_and_jwt_checks':True,'real_app_extraction_before_after_restart':'passed','untrusted_config_and_private_destination_rejection':'passed','internal_network':True,'provider_calls':False,'production_mounts':False,'published_ports':False},indent=2)+'\n')
except Exception:
 logs=subprocess.run(['docker','logs','--tail','160',name],capture_output=True);path=Path('/tmp')/(name+'-startup.log');path.write_bytes(logs.stdout+logs.stderr);path.chmod(0o600);print('Private synthetic diagnostics: '+str(path));raise
finally:
 for kind,resource in reversed(created):subprocess.run(['docker','rm','-f',resource] if kind=='container' else ['docker',kind,'rm',resource],capture_output=True)
