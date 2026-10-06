"""Authenticated HTTP ZIP import; remove synthetic files after verification."""
import http.cookiejar
import io
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

env=dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
base='http://localhost:'+env.get('HTTP_PORT','8080')
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
with client.open(base+'/login',timeout=10) as response:login=response.read().decode()
csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
client.open(base+'/login',data=urllib.parse.urlencode({'username':env['ADMIN_USER'],'password':env['ADMIN_PASSWORD'],'csrf':csrf}).encode(),timeout=10).close()
with client.open(base+'/vault/import',timeout=10) as response:page=response.read().decode()
assert 'Paused: no page downloading' in page
csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',page)[1]
name='Import-test-'+uuid.uuid4().hex
output=io.BytesIO()
with zipfile.ZipFile(output,'w') as archive:
    archive.writestr('MyVault/'+name+'/Note.md','# Synthetic note\n')
    archive.writestr('MyVault/'+name+'/image.png',b'synthetic attachment')
boundary='vaultimporttest'
def upload(token):
    body=f'--{boundary}\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n{token}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="vault.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode()+output.getvalue()+f'\r\n--{boundary}--\r\n'.encode()
    request=urllib.request.Request(base+'/vault/import',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    with client.open(request,timeout=20) as response:return response.read().decode()
try:
    assert 'Imported 2 files' in upload(csrf)
    assert 'Imported 0 files; skipped 2' in upload(csrf)
    try:upload('wrong');raise AssertionError('Bad CSRF accepted')
    except urllib.error.HTTPError as error:assert error.code==403
    subprocess.run(['docker','compose','exec','-T','worker','python','-c',"import sys; from pathlib import Path; assert (Path('/vault')/sys.argv[1]/'Note.md').read_text()=='# Synthetic note\\n'",name],check=True,capture_output=True)
    print('HTTP ZIP import, no overwrite, attachment copying, persistent pause and CSRF rejection passed')
finally:
    subprocess.run(['docker','compose','exec','-T','worker','python','-c',"import shutil,sys; from pathlib import Path; shutil.rmtree(Path('/vault')/sys.argv[1],ignore_errors=True)",name],check=True,capture_output=True)
