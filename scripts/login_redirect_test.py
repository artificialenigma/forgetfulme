"""Check missing/invalid sessions and safe return-to-page navigation."""
import http.cookiejar
import re
import urllib.parse
import urllib.request
from pathlib import Path

env = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
base = 'http://localhost:' + env.get('HTTP_PORT', '8080')
for path in ['/devices', '/history', '/history/import', '/history/capture']:
    for headers in [{}, {'Cookie': 'forgetfulme_session=invalid'}]:
        with urllib.request.urlopen(urllib.request.Request(base+path, headers=headers),timeout=10) as response:
            assert response.url == base + '/login?next=' + path
            assert b'Sign in' in response.read()
for destination, expected in [('/history/import','/history/import'), ('https://evil.invalid','/'), ('//evil.invalid','/'), ('/\\evil.invalid','/')]:
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with client.open(base+'/login?'+urllib.parse.urlencode({'next':destination}),timeout=10) as response:
        csrf = re.search(r'name="csrf" value="([a-f0-9]+)"',response.read().decode())[1]
    data = urllib.parse.urlencode({'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD'],'csrf':csrf,'next':destination}).encode()
    with client.open(base+'/login',data=data,timeout=10) as response:
        assert response.url == base + expected
        assert b'Sign in to manage browser devices' not in response.read()
print('Missing/invalid session redirects, login return destination and external redirect rejection passed')
