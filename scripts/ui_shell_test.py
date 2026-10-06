"""Verify shared frame and navigation across signed-in HTTP pages."""
import http.cookiejar
import re
import urllib.parse
import urllib.request
from pathlib import Path

env=dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
base='http://localhost:'+env.get('HTTP_PORT','8080')
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
with client.open(base+'/login',timeout=10) as response:
    login=response.read().decode()
    assert '/static/dashboard.css' in login and '<style>' not in login
    csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
data=urllib.parse.urlencode({'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD'],'csrf':csrf}).encode()
client.open(base+'/login',data=data,timeout=10).close()
paths=['/','/history','/devices','/history/import','/history/capture','/vault','/vault/wiki','/settings/ai']
for path in paths:
    with client.open(base+path,timeout=10) as response: body=response.read().decode()
    assert '/static/dashboard.css' in body and '<style>' not in body
    assert '<aside class="sidebar">' in body and '<nav aria-label="Workspace">' in body
    assert f'href="{path}" class="active" aria-current="page"' in body
    for destination in paths: assert f'href="{destination}"' in body
    assert 'automatic note export is still planned' not in body
    if path=='/history/capture':
        assert '<table class="capture-table">' in body and '<thead>' in body and '<tbody>' in body
        assert 'Capture result' in body and 'Refresh status' in body
        if '<tr><td colspan="3"' not in body:
            assert 'capture-title' in body and 'capture-url' in body and 'class="badge ' in body
    if path=='/vault': assert '<iframe src="/obsidian/"' in body
    if path=='/history/import': csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',body)[1]
boundary='unified-ui-test'
body=f'--{boundary}\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n{csrf}\r\n--{boundary}\r\nContent-Disposition: form-data; name="source"\r\n\r\nUI test\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="empty.json"\r\nContent-Type: application/json\r\n\r\n[]\r\n--{boundary}--\r\n'.encode()
request=urllib.request.Request(base+'/history/import',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
with client.open(request,timeout=10) as response: error=response.read().decode()
assert 'No visits were saved' in error and '<aside class="sidebar">' in error
assert 'href="/history/import" class="active" aria-current="page"' in error
print('Shared stylesheet, sidebar, active navigation, vault frame, login and import error rendering passed')
# Knowledge routes must retain the app's authentication and CSRF boundaries.
with urllib.request.urlopen(base+'/vault/wiki',timeout=10) as response:
    assert '/login?next=/vault/wiki' in response.url
try:
    request=urllib.request.Request(base+'/vault/wiki/questions',data=urllib.parse.urlencode({'question':'Docker','csrf':'invalid'}).encode())
    client.open(request,timeout=10)
    raise AssertionError('Wiki question accepted an invalid CSRF token')
except urllib.error.HTTPError as error:
    assert error.code==403
try:
    urllib.request.urlopen(base+'/vault/wiki/questions',data=b'question=Docker',timeout=10)
    raise AssertionError('Wiki question accepted an unauthenticated request')
except urllib.error.HTTPError as error:
    assert error.code==401
print('Knowledge page login redirect and question authentication/CSRF checks passed')
