"""Test device pairing and ingestion against the stack, then delete synthetic records."""
import http.cookiejar
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

env = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
base = 'http://localhost:' + env.get('HTTP_PORT','8080')
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def read(path, data=None):
    return client.open(base+path, data=data,timeout=10).read().decode()
def post(path, data):
    return read(path, urllib.parse.urlencode(data).encode())
csrf = re.search(r'name="csrf" value="([a-f0-9]+)"',read('/login'))[1]
post('/login',{'csrf':csrf,'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD']})
csrf = re.search(r'name="csrf" type="hidden" value="([a-f0-9]+)"',read('/devices'))[1]
name='Synthetic add-on smoke test'
token=re.search(r'<code>([^<]+)</code>',post('/devices',{'csrf':csrf,'name':name}))[1]
try:
    devices=read('/devices')
    device_id=re.search(r'/devices/([a-f0-9-]+)/revoke',devices)[1]
    # Identify this device by its row rather than depending on creation order.
    row=next(row for row in devices.split('<tr>') if name in row)
    device_id=re.search(r'/devices/([a-f0-9-]+)/revoke',row)[1]
    visit={'event_id':'synthetic-1','url':'https://example.com/addon-test','title':'Synthetic visit','visited_at':datetime.now(timezone.utc).isoformat()}
    def ingest(payload, bearer=token, expected=200):
        req=urllib.request.Request(base+'/api/history/visits',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+bearer})
        try:
            with urllib.request.urlopen(req,timeout=10) as response:
                assert response.status==expected
                return json.load(response)
        except urllib.error.HTTPError as error:
            assert error.code==expected, (error.code,error.read())
    assert ingest({'visits':[visit]})['inserted']==1
    assert ingest({'visits':[visit]})['inserted']==0
    ingest({'visits':[visit]},bearer='invalid',expected=401)
    ingest({'visits':[{**visit,'url':'javascript:alert(1)'}]},expected=422)
    ingest({'visits':[visit]*101},expected=422)
    assert 'Synthetic visit' in read('/history')
    post('/devices/'+device_id+'/revoke',{'csrf':csrf})
    ingest({'visits':[visit]},expected=401)
    print('Pairing, ingestion, deduplication, URL validation, batch limits, history display and revocation passed')
finally:
    subprocess.run(['docker','compose','exec','-T','db','psql','-U','forgetfulme','-d','forgetfulme','-c',"DELETE FROM page_captures WHERE url='https://example.com/addon-test' AND NOT EXISTS (SELECT 1 FROM browser_visits v JOIN browser_devices d ON d.id=v.device_id WHERE v.url='https://example.com/addon-test' AND d.name<>'Synthetic add-on smoke test'); DELETE FROM browser_visits WHERE device_id IN (SELECT id FROM browser_devices WHERE name='Synthetic add-on smoke test'); DELETE FROM browser_devices WHERE name='Synthetic add-on smoke test';"],check=True,stdout=subprocess.DEVNULL)
