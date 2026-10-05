"""Exercise file uploads with synthetic history; remove fixtures afterwards."""
import json
import re
import runpy
import subprocess
import urllib.error
import urllib.request
import uuid

context = runpy.run_path('scripts/history_smoke_test.py')
client, base, read = (context[key] for key in ('client', 'base', 'read'))
source = 'Synthetic import smoke test'
device_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'forgetfulme:import:' + source.casefold()))
csrf = re.search(r'name="csrf" value="([a-f0-9]+)"', read('/history/import'))[1]


def upload(content, filename='history.csv', token=csrf):
    boundary = 'forgetfulme-test-boundary'
    parts = []
    for name, value in [('csrf',token),('source',source)]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + f'\r\n--{boundary}--\r\n'.encode())
    request = urllib.request.Request(base + '/history/import', data=b''.join(parts), headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    return client.open(request,timeout=15).read().decode()


try:
    csv = b'url,title,visited_at\nhttps://example.com/import-test,"Example, imported",2026-01-01T12:00:00Z\n'
    assert '1 visits imported' in upload(csv)
    assert '1 duplicates skipped' in upload(csv)
    equivalent = [{'url':'https://example.com/import-test','title':'Example','visited_at':'2026-01-01T13:00:00+01:00'}]
    assert '1 duplicates skipped' in upload(json.dumps({'visits':equivalent}).encode(),'history.json')
    bad = b'url,title,visited_at\nhttps://example.com/must-not-save,Good,2026-01-02T12:00:00Z\njavascript:alert(1),Bad,2026-01-02T12:00:00Z\n'
    assert 'No visits were saved' in upload(bad)
    assert 'must-not-save' not in read('/history')
    assert 'No visits were saved' in upload(b'{invalid','history.json')
    assert 'No visits were saved' in upload(b'url,title,visited_at\nhttps://example.com,No timezone,2026-01-01T12:00:00\n')
    try:
        upload(csv,token='wrong')
    except urllib.error.HTTPError as error:
        assert error.code == 403
    else:
        raise AssertionError('Invalid CSRF accepted')
    with urllib.request.urlopen(base+'/history/import', timeout=10) as response:
        assert '/login?next=/history/import' in response.url
        assert b'Sign in' in response.read()
    print('CSV/JSON upload, repeat/timezone deduplication, atomic validation, malformed input, CSRF and authentication passed')
finally:
    subprocess.run(['docker','compose','exec','-T','db','psql','-U','forgetfulme','-d','forgetfulme','-c',f"DELETE FROM browser_visits WHERE device_id='{device_id}'; DELETE FROM browser_devices WHERE id='{device_id}';"],check=True,stdout=subprocess.DEVNULL)
