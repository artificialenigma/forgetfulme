"""Exercise the modern API boundary with an offline loopback response fixture."""
import json,os,threading,urllib.error
from http.server import BaseHTTPRequestHandler,HTTPServer
from unittest.mock import patch
from app.db import require_isolated_test
from app.crawl4ai_client import extract_html
require_isolated_test()
requests=[];mode='success'
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  requests.append((self.path,self.headers.get('Authorization'),payload))
  if mode=='redirect':self.send_response(302);self.send_header('Location','/unexpected');self.end_headers();return
  self.send_response(200);self.end_headers()
  result={'success':mode=='success','results':[{'success':True,'markdown':{'raw_markdown':'Synthetic readable extracted content containing enough characters for the test.'}}]}
  self.wfile.write(json.dumps(result).encode())
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with patch.dict(os.environ,{'CRAWL4AI_URL':'http://127.0.0.1:'+str(server.server_port),'CRAWL4AI_API_TOKEN':'synthetic-test-token'}):
  html='<main><p>Readable Café text</p><a href="../evidence">Source</a><a href="javascript:alert(1)">Unsafe link</a><img src="https://invalid.example/track"><script>fetch("/leak")</script><p onclick="alert(1)">Text</p></main>'
  assert 'Synthetic readable' in extract_html(html,'https://synthetic.invalid/folder/source')
  path,authorization,payload=requests[-1]
  assert path=='/crawl' and authorization=='Bearer synthetic-test-token'
  assert 'base_url' not in payload['crawler_config']['params']
  assert payload['browser_config']['params']['java_script_enabled'] is False
  safe=payload['urls'][0]
  assert 'https://synthetic.invalid/evidence' in safe
  assert all(x not in safe for x in ['javascript:','<script','<img','onclick','fetch('])
  mode='redirect'
  try:extract_html(html,'https://synthetic.invalid/source')
  except urllib.error.HTTPError as error:assert error.code==302
  else:raise AssertionError('Redirect followed')
  mode='failed'
  try:extract_html(html,'https://synthetic.invalid/source')
  except ValueError:pass
  else:raise AssertionError('Failed extraction accepted')
 print('PASS modern crawler request boundary: bearer token, safe raw HTML, absolute links, forbidden config omission and redirect/failure rejection')
finally:server.shutdown();server.server_close();thread.join(timeout=5)
