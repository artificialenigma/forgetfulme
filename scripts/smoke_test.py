"""Exercise the running local stack, including an isolated database restore."""
import base64
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parent.parent
env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if line and not line.startswith('#'))
base = f"http://localhost:{env.get('HTTP_PORT', '8080')}"
credentials = base64.b64encode(f"{env['ADMIN_USER']}:{env['ADMIN_PASSWORD']}".encode()).decode()


def get(path, authenticated=False):
    headers = {'Authorization': f'Basic {credentials}'} if authenticated else {}
    with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=10) as response:
        return response.read()


assert json.loads(get('/health/ready'))['status'] == 'ready'
for path in ['/', '/api/status']:
    try:
        get(path)
    except urllib.error.HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('Protected route allowed unauthenticated access')
assert b'Forgetful Me' in get('/', True)
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
createdb forgetfulme_restore_test
trap 'dropdb --if-exists forgetfulme_restore_test' EXIT
pg_restore --exit-on-error --no-owner --dbname=forgetfulme_restore_test "$latest/database.dump"
psql --dbname=forgetfulme_restore_test -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM jobs; SELECT count(*) FROM service_status;'
'''
subprocess.run(['docker', 'compose', 'exec', '-T', 'backup', 'sh', '-c', restore], cwd=root, check=True)
print('PASS: readiness, authentication, dashboard, scheduler, worker, backup archive, and database restore')
