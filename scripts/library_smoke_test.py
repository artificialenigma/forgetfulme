"""Authenticated library flows in the disposable test stack only."""
import hashlib
import html
import http.cookiejar
import re
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from app.db import require_isolated_test
require_isolated_test()
env=os.environ
base=env['FM_TEST_BASE_URL']
assert base=='http://test-web:8000', 'Refusing a non-isolated HTTP target'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path):
    with client.open(base+path,timeout=20) as response:return response.read().decode()
def post(path,data):
    with client.open(base+path,data=urllib.parse.urlencode(data).encode(),timeout=20) as response:return response.read().decode()
def token(page):return re.search(r'name="csrf" value="([a-f0-9]+)"',page)[1]
def run(code,*args):
    guarded='from app.db import require_isolated_test;require_isolated_test();\n'+code
    result=subprocess.run([sys.executable,'-c',guarded,*args],check=True,capture_output=True,text=True)
    return result.stdout
login=get('/login');post('/login',dict(username=env['ADMIN_USER'],password=env['ADMIN_PASSWORD'],csrf=token(login)))
name='Library-test-'+uuid.uuid4().hex
path=name+'/Café.md';other=name+'/Other.md';broken=name+'/Try ΓÇö note.md';fixed=name+'/Try — note.md';question='Which hardware approach should this project use?';identity=''
setup="""import sys
from pathlib import Path
from app.library import scan
v=Path('/vault')/sys.argv[1];v.mkdir()
(v/'Café.md').write_text('---\\ntitle: "Café fixture"\\ntags: [fixture, hardware]\\n---\\n# Evidence\\n'+('Synthetic Unicode evidence for retrieval. '*30)+'\\n## Open questions\\n- Which hardware approach should this project use?\\n')
from app.wiki import note_header
(v/'Managed.md').write_text(note_header('source','Managed fixture')+'# Managed fixture\\n'+('Synthetic managed note. '*30))
(v/'Other.md').write_text('---\\ntitle: "Other fixture"\\ntags: [fixture, hardware]\\n---\\n# Evidence\\n'+('Companion synthetic hardware evidence. '*30))
(v/'Try ΓÇö note.md').write_text('# Filename fixture\\n'+('Only synthetic text. '*30))
scan()
"""
try:
    run(setup,name)
    page=get('/library?q='+urllib.parse.quote('Café'))
    assert 'Café fixture' in page
    note=get('/library/note?'+urllib.parse.urlencode({'path':path}));csrf=token(note)
    assert 'Shared tags: fixture, hardware' in note and 'line-' in note
    post('/library/preferences',dict(csrf=csrf,path=path,project=name,reviewed='1',excluded='1'))
    assert 'Café fixture' not in get('/library?q='+urllib.parse.quote('Café')+'&project='+name)
    post('/library/preferences',dict(csrf=csrf,path=path,project=name,reviewed='1'))
    assert 'Café fixture' in get('/library?project='+name+'&review=reviewed')
    post('/library/preferences',dict(csrf=csrf,path=name+'/Managed.md',reviewed='1'))
    run("import sys;from pathlib import Path;from app.wiki import atomic_note,note_header;p=Path('/vault')/sys.argv[1]/'Managed.md';original=p.read_bytes();assert not atomic_note(p,note_header('source','Changed')+'replacement');assert p.read_bytes()==original",name)
    post('/library/connections',dict(csrf=csrf,source=path,target=other))
    note=get('/library/note?'+urllib.parse.urlencode({'path':path}));assert 'Accepted connections' in note
    questions=get('/library/questions');assert question in questions
    question_article=next(block for block in re.findall(r'<article\b.*?</article>',questions,re.S) if question in html.unescape(block))
    identity=re.search(r'name="id" value="([a-f0-9]{64})"',question_article)[1]
    post('/library/questions/resolve',dict(csrf=csrf,id=identity,answer_path=other,state='resolved'))
    assert identity not in get('/library/questions')
    assert identity in get('/library/questions?state=all')
    health=get('/library/health?kind=encoding');assert 'Try — note.md' in health
    preview=get('/library/repair-preview?'+urllib.parse.urlencode({'path':broken}))
    assert 'Preview filename repair' in preview and 'Existing Markdown links are retained' in preview
    expected=re.search(r'name="expected_hash" value="([a-f0-9]{64})"',preview)[1]
    post('/library/repair-name',dict(csrf=csrf,path=broken,expected_hash=expected))
    run("import sys;from pathlib import Path;assert Path('/vault',sys.argv[1]).exists();assert not Path('/vault',sys.argv[2]).exists()",fixed,broken)
    try:post('/library/preferences',dict(csrf='invalid',path=path));raise AssertionError('Invalid CSRF accepted')
    except urllib.error.HTTPError as e:assert e.code==403
    for url in ['/library','/library/health','/library/questions','/library/note?path='+urllib.parse.quote(path)]:
        with urllib.request.urlopen(base+url,timeout=20) as response:assert '/login' in response.url
    try:post('/vault/wiki/questions',dict(csrf=csrf,question='Synthetic fixture query',scope='invalid'));raise AssertionError('Unknown scope accepted')
    except urllib.error.HTTPError as e:assert e.code==400
    capture_id=hashlib.sha256(name.encode()).hexdigest()
    run("import sys;from app.db import connect;db=connect();db.execute(\"INSERT INTO page_captures(url_hash,url,state,note_path,wiki_source_path) VALUES (%s,'https://example.invalid/fixture','blocked',%s,%s)\",(sys.argv[1],sys.argv[2],sys.argv[3]));db.commit()",capture_id,path,other)
    post('/history/capture/action',dict(csrf=csrf,id=capture_id,action='exclude'))
    run("import sys;from app.db import connect;db=connect();assert db.execute('SELECT excluded FROM page_captures WHERE url_hash=%s',(sys.argv[1],)).fetchone()['excluded']",capture_id)
    post('/history/capture/action',dict(csrf=csrf,id=capture_id,action='include'))
    run("import sys;from app.db import connect;db=connect();r=db.execute('SELECT state,excluded FROM page_captures WHERE url_hash=%s',(sys.argv[1],)).fetchone();assert not r['excluded'] and r['state']=='blocked'",capture_id)
    print('Live library search, project/review/exclusion, accepted connections, question resolution, filename recovery, login and CSRF passed')
finally:
    cleanup="""import sys,shutil,hashlib
from pathlib import Path
from app.db import connect
from app.library import scan
name=sys.argv[1];source=name+'/Café.md';digest=hashlib.sha256(source.encode()).hexdigest()[:24]
shutil.rmtree(Path('/vault')/name,ignore_errors=True)
(Path('/vault/Forgetful Me/Connections')/(digest+'.md')).unlink(missing_ok=True)
with connect() as db:
 db.execute('DELETE FROM page_captures WHERE url_hash=%s',(hashlib.sha256(name.encode()).hexdigest(),))
 db.execute('DELETE FROM library_overrides WHERE path LIKE %s',(name+'/%',))
 db.execute('DELETE FROM library_connections WHERE source LIKE %s OR target LIKE %s',(name+'/%',name+'/%'))
 db.execute('DELETE FROM library_question_status WHERE id=%s',(sys.argv[2],))
scan()
"""
    run(cleanup,name,identity)
