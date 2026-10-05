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


def upload(content, filename='history.csv', token=csrf, skip_invalid=False):
    boundary = 'forgetfulme-test-boundary'
    parts = []
    for name, value in [('csrf',token),('source',source),('skip_invalid_safari','yes' if skip_invalid else 'no')]:
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
    # Exceed the former app/proxy limits with valid JSON whitespace padding.
    padded = json.dumps({'visits':equivalent}).encode() + b' ' * (6 * 1024 * 1024)
    assert '1 duplicates skipped' in upload(padded, 'history.json')
    safari = {'metadata': {'browser_name':'Safari','data_type':'history','schema_version':1}, 'history':[{'url':'https://example.com/safari-import-test','time_usec':1774258180789274,'visit_count':1,'latest_visit_was_load_failure':True}]}
    assert '1 visits imported' in upload(json.dumps(safari).encode(),'History.json')
    assert '1 duplicates skipped' in upload(json.dumps(safari).encode(),'History.json')
    equivalent_safari = [{'url':'https://example.com/safari-import-test','visited_at':'2026-03-23T09:29:40.789274Z'}]
    assert '1 duplicates skipped' in upload(json.dumps(equivalent_safari).encode(),'history.json')
    safari['history'][0]['time_usec'] = '1774258180789274'
    assert 'No visits were saved' in upload(json.dumps(safari).encode(),'History.json')
    all_invalid = upload(json.dumps(safari).encode(),'History.json',skip_invalid=True)
    assert 'No valid visits found' in all_invalid and 'No visits were saved' in all_invalid
    safari['history'] = [{'url':'https://example.com/safari-mixed','time_usec':1774258180789274},{'url':'file:///private/safari-test','time_usec':1774258180789274},{'url':'https://example.com/safari-bad-time','time_usec':-1}]
    assert 'No visits were saved' in upload(json.dumps(safari).encode(),'History.json')
    mixed = upload(json.dumps(safari).encode(),'History.json',skip_invalid=True)
    assert '1 visits imported' in mixed and '2 unsupported or invalid entries skipped' in mixed
    assert 'Safari history entry 2: url:' in mixed and 'Safari history entry 3: time_usec' in mixed
    assert '/private/safari-test' not in mixed
    retry = upload(json.dumps(safari).encode(),'History.json',skip_invalid=True)
    assert '1 duplicates skipped' in retry
    safari['metadata']['schema_version'] = 2
    assert 'Unsupported Safari export' in upload(json.dumps(safari).encode(),'History.json')
    large = {'metadata': {'browser_name':'Safari','data_type':'history','schema_version':1}, 'history':[{'url':f'https://example.com/large-safari/{i}','time_usec':1774258180789274+i} for i in range(10001)]}
    assert '10,001 visits imported' in upload(json.dumps(large).encode(),'History.json')
    assert '10,001 duplicates skipped' in upload(json.dumps(large).encode(),'History.json')
    first_page = read('/history')
    second_page = read('/history?page=2')
    assert first_page.count('<tr>') == 51 and second_page.count('<tr>') == 51
    assert 'Page 2 of' in second_page and 'UTC+05:00' in second_page
    assert 'href="/history?page=2"' in first_page
    assert 'dashboard.css' in first_page and first_page != second_page
    assert 'The file contains no history entries' in upload(b'{"visits": []}','history.json')
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
