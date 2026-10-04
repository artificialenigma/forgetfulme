"""Check the optional Archive Desk service without accessing any provider account."""
import json
import os
import urllib.error
import urllib.request

base = f"http://localhost:{os.environ.get('ARCHIVE_HTTP_PORT', '8766')}"
with urllib.request.urlopen(base + '/') as response:
    assert response.status == 200
    assert b'Archive Desk' in response.read()
with urllib.request.urlopen(base + '/api/bootstrap') as response:
    token = json.loads(response.read())['token']
    assert token
try:
    urllib.request.urlopen(base + '/api/jobs')
except urllib.error.HTTPError as error:
    assert error.code == 401
else:
    raise AssertionError('Archive API accepted a missing app token')
with urllib.request.urlopen(urllib.request.Request(base + '/api/jobs', headers={'X-App-Token': token})) as response:
    assert isinstance(json.loads(response.read())['jobs'], list)
with urllib.request.urlopen(f"http://localhost:{os.environ.get('ARCHIVE_BROWSER_PORT', '6080')}/vnc.html") as response:
    assert response.status == 200
    assert b'noVNC' in response.read()
print('PASS: Archive Desk UI, bootstrap, API token enforcement, job listing, and browser-view HTTP endpoint')
