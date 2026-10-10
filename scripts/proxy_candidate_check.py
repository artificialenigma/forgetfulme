#!/usr/bin/env python3
"""Exercise the real Caddy config using disposable synthetic backends only."""
import argparse,json,re,secrets,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);args=p.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}',args.image):p.error('Exact local candidate image ID required')
name='forgetfulme-proxy-check-'+secrets.token_hex(5);net=name+'-net';created=[]
def run(*parts):
 r=subprocess.run(['docker',*parts],capture_output=True,text=True)
 if r.returncode:raise RuntimeError('Disposable proxy command failed: '+parts[0])
 return r.stdout
backend='''from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  auth=self.path=='/internal/desktop-auth'
  self.send_response(200 if not auth or self.headers.get('Cookie')=='synthetic=allowed' else 401)
  self.end_headers();self.wfile.write(b'synthetic backend')
 def log_message(self,*args):pass
HTTPServer(('0.0.0.0',8000),Handler).serve_forever()
'''
try:
 run('network','create','--internal',net);created.append(net)
 for alias,port in [('web',8000),('obsidian',3000)]:
  container=name+'-'+alias
  run('run','-d','--name',container,'--network',net,'--network-alias',alias,'forgetfulme-app:local','python','-c',backend.replace("8000),Handler)",str(port)+'),Handler)'));created.append(container)
 proxy=name+'-caddy'
 mount=['--mount','type=bind,source='+str(ROOT/'infra/Caddyfile')+',target=/etc/caddy/Caddyfile,readonly']
 run('run','--rm','--network','none',*mount,'-e','SITE_ADDRESS=:80',args.image,'caddy','validate','--config','/etc/caddy/Caddyfile','--adapter','caddyfile')
 run('run','-d','--name',proxy,'--network',net,'--network-alias','proxy',*mount,'-e','SITE_ADDRESS=:80',args.image);created.append(proxy)
 check='''import time,urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
opener=urllib.request.build_opener(NoRedirect)
for _ in range(30):
 try:opener.open('http://proxy/',timeout=2);break
 except Exception:time.sleep(1)
for path,cookie,status,frame in [('/',None,200,'DENY'),('/obsidian',None,308,None),('/obsidian/',None,401,'SAMEORIGIN'),('/obsidian/','synthetic=allowed',200,'SAMEORIGIN')]:
 request=urllib.request.Request('http://proxy'+path,headers={'Cookie':cookie} if cookie else {})
 try:response=opener.open(request,timeout=3)
 except urllib.error.HTTPError as error:response=error
 assert response.code==status,(path,response.code)
 if frame:assert response.headers.get('X-Frame-Options')==frame
print('PASS config, app routing/security headers, desktop redirect/auth denial/authenticated routing')
'''
 print(run('exec',name+'-web','python','-c',check).strip())
 report={'image':args.image,'real_caddyfile':True,'internal_network':True,'production_mounts':False,'provider_calls':False,'routing_and_auth_headers':'passed'}
 (ROOT/'reports/proxy-candidate-check-2026-10-07.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
 for resource in reversed(created):
  subprocess.run(['docker','network','rm',resource] if resource==net else ['docker','rm','-f',resource],capture_output=True)
