"""Exercise the running local stack, including an isolated database restore."""
import base64
import http.cookiejar
import json
import re
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import urllib.parse

root = Path(__file__).resolve().parent.parent
env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if line and not line.startswith('#'))
base = f"http://localhost:{env.get('HTTP_PORT', '8080')}"
credentials = base64.b64encode(f"{env['ADMIN_USER']}:{env['ADMIN_PASSWORD']}".encode()).decode()


def get(path, authenticated=False):
    headers = {'Authorization': f'Basic {credentials}'} if authenticated else {}
    with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=10) as response:
        return response.read()


assert json.loads(get('/health/ready'))['status'] == 'ready'
with urllib.request.urlopen(base.replace('localhost', '127.0.0.1') + '/health/ready', timeout=10) as response:
    assert json.loads(response.read())['status'] == 'ready'
for path in ['/api/status']:
    try:
        get(path)
    except urllib.error.HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('Protected route allowed unauthenticated access')
assert b'Forgetful Me' in get('/', True)
assert b'Username' in get('/') and b'Stack status' not in get('/')
jar = http.cookiejar.CookieJar()
browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
with browser.open(base + '/login') as response:
    csrf = re.search(r'name="csrf" value="([a-f0-9]+)"', response.read().decode()).group(1)
form = urllib.parse.urlencode({'username': env['ADMIN_USER'], 'password': env['ADMIN_PASSWORD'], 'csrf': csrf}).encode()
with browser.open(base + '/login', data=form) as response:
    assert b'Stack status' in response.read()
session = next(cookie for cookie in jar if cookie.name == 'forgetfulme_session')
assert session.has_nonstandard_attr('HttpOnly')
assert session.get_nonstandard_attr('SameSite') == 'strict'
with browser.open(base + '/api/status') as response:
    assert 'services' in json.loads(response.read())
with browser.open(base + '/vault') as response:
    assert b'Obsidian vault desktop' in response.read()
with browser.open(base + '/api/vault') as response:
    vault = json.loads(response.read())
    assert vault['mounted'] and vault['markdown_files'] >= 1
with browser.open(base + '/obsidian/') as response:
    assert response.status == 200
    assert b'<html' in response.read().lower()
assert b'Username' in get('/obsidian/')
try:
    browser.open(urllib.request.Request(base + '/obsidian/', headers={'Origin': 'https://foreign.invalid'}))
except urllib.error.HTTPError as error:
    assert error.code == 403
else:
    raise AssertionError('Desktop accepted a foreign Origin')
try:
    browser.open(base + '/login', data=urllib.parse.urlencode({'username': env['ADMIN_USER'], 'password': env['ADMIN_PASSWORD']}).encode())
except urllib.error.HTTPError as error:
    assert error.code == 403
else:
    raise AssertionError('Login accepted without CSRF protection')
with browser.open(base + '/login') as response:
    csrf = re.search(r'name="csrf" value="([a-f0-9]+)"', response.read().decode()).group(1)
try:
    browser.open(base + '/login', data=urllib.parse.urlencode({'username': env['ADMIN_USER'], 'password': 'invalid-test-password', 'csrf': csrf}).encode())
except urllib.error.HTTPError as error:
    assert error.code == 401
else:
    raise AssertionError('Login accepted an incorrect password')
try:
    urllib.request.urlopen(urllib.request.Request(base + '/api/status', headers={'Cookie': 'forgetfulme_session=invalid'}))
except urllib.error.HTTPError as error:
    assert error.code == 401
else:
    raise AssertionError('API accepted an invalid session')
for attempt in range(20):
    state = json.loads(get('/api/status', True))
    if {s['service'] for s in state['services'] if s['healthy']} == {'worker', 'scheduler'} and state['jobs']['completed'] > 0:
        break
    time.sleep(2)
else:
    raise AssertionError('Background services did not complete a scheduled job')

# Restore only into a disposable database; never touch the application's database.
restore = '''set -eu
latest=$(find /backups -mindepth 1 -maxdepth 1 -type d ! -name '.pending-*' | sort | tail -n 1)
test -n "$latest"
tar -tzf "$latest/content.tar.gz" >/dev/null
tar -tzf "$latest/vault.tar.gz" | grep -q Welcome.md
tar -tzf "$latest/obsidian-config.tar.gz" >/dev/null
createdb forgetfulme_restore_test
trap 'dropdb --if-exists forgetfulme_restore_test' EXIT
pg_restore --exit-on-error --no-owner --dbname=forgetfulme_restore_test "$latest/database.dump"
psql --dbname=forgetfulme_restore_test -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM jobs; SELECT count(*) FROM service_status;'
'''
subprocess.run(['docker', 'compose', 'exec', '-T', 'backup', 'sh', '-c', restore], cwd=root, check=True)
print('PASS: readiness, authentication, dashboard, vault/desktop access, scheduler, worker, backup archives, and database restore')
