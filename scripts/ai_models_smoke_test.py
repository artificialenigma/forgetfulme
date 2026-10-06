"""Fetch the real local model catalog through the authenticated app while paused."""
import html
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
csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
client.open(base+'/login',data=urllib.parse.urlencode({'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD'],'csrf':csrf}).encode(),timeout=10).close()
page=get()
assert '<option value="ollama" selected' in page
assert 'name="enabled" value="1" checked' not in page
params={name:html.unescape(re.search(r'id="'+name+r'"[^>]*value="([^"]*)"',page)[1]) for name in ['base_url','model','temperature','max_tokens','context_size']}
params.update(provider='ollama',csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',page)[1])
original=params.copy()
try:
    post({**params,'model':'','action':'models'})
    for _ in range(30):
        page=get()
        if 'id="available_model"' in page:break
        time.sleep(1)
    else:raise AssertionError('Model discovery did not complete')
    assert '<option value="qwen2.5:3b">qwen2.5:3b</option>' in page
    assert 'name="enabled" value="1" checked' not in page
    page=post({**params,'model':'','available_model':'qwen2.5:3b','action':'save'})
    assert 'id="model" name="model" value="qwen2.5:3b"' in page
    try:post({**params,'available_model':'invented-model'});raise AssertionError('Unknown catalog selection accepted')
    except urllib.error.HTTPError as error:assert error.code==400
    try:post({**params,'csrf':'invalid','action':'models'});raise AssertionError('Invalid CSRF accepted')
    except urllib.error.HTTPError as error:assert error.code==403
    print('Live catalog fetch with blank model, selector save, unknown selection and CSRF checks passed; AI stayed paused')
finally:
    post(original)
