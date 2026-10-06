"""Exercise settings persistence/key lifecycle on a fresh local configuration."""
import http.cookiejar
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

env=dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
base='http://localhost:'+env.get('HTTP_PORT','8080')
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get():
    with client.open(base+'/settings/ai',timeout=10) as response:return response.read().decode()
def post(data):
    with client.open(base+'/settings/ai',data=urllib.parse.urlencode(data).encode(),timeout=10) as response:return response.read().decode()
with client.open(base+'/login',timeout=10) as response:login=response.read().decode()
token=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
client.open(base+'/login',data=urllib.parse.urlencode({'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD'],'csrf':token}).encode(),timeout=10).close()
page=get()
assert 'No key is stored.' in page,'Run only with no existing provider key'
data={name:re.search(r'id="'+name+r'"[^>]*value="([^"]*)"',page)[1] for name in ['base_url','model','temperature','max_tokens','context_size']}
data['provider']=re.search(r'<option value="([^"]+)" selected',page)[1]
data['csrf']=re.search(r'name="csrf" value="([a-f0-9]+)"',page)[1]
if 'name="enabled" value="1" checked' in page:data['enabled']='1'
original=data.copy()
try:
    paused={key:value for key,value in data.items() if key!='enabled'}
    secret='synthetic-provider-test-key'
    page=post({**paused,'api_key':secret})
    assert 'A key is stored.' in page and secret not in page
    assert 'name="enabled" value="1" checked' not in page
    assert 'A key is stored.' in post({**paused,'api_key':''})
    page=post({**paused,'provider':'openai','base_url':'https://example.com/v1','api_key':''})
    assert 'No key is stored.' in page
    page=post({**original,'api_key':'','clear_key':'1','action':'test'})
    for _ in range(90):
        page=get()
        if 'Connected: model returned valid JSON.' in page:break
        if '<p>failed</p>' in page:raise AssertionError('Provider connection test failed')
        time.sleep(1)
    else:raise AssertionError('Connection test did not finish')
    print('Saved settings, key retention/redaction/clearing, pause and live Ollama connection test passed')
finally:
    post({**original,'api_key':'','clear_key':'1'})
for destination in ['/settings/ai','/settings/ai/retry']:
    try:
        client.open(base+destination,data=b'csrf=invalid',timeout=10)
        raise AssertionError('Invalid CSRF accepted')
    except urllib.error.HTTPError as error:assert error.code==403
print('Settings mutation CSRF boundaries passed; original provider restored')
