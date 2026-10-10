"""Safe reading and recoverable, reversible connection workflow fixtures."""
import tempfile
import hashlib
from pathlib import Path
from app.db import require_isolated_test,connect
from app import library
from app.reading import render
from app.connection_export import queue,process_one
from app.library_identity import rename_note
require_isolated_test()
malicious='<script>alert(1)</script>\n\n![remote](https://example.invalid/pixel?token=PRIVATE)\n\n[bad](javascript:alert(1))\n\n[ok](https://example.invalid/path?token=SECRET)'
output=render(malicious)
assert '<script>' not in output and '<img' not in output and 'href="javascript:' not in output and 'SECRET' not in output
assert 'href="https://example.invalid/' in render('[positive](https://example.invalid/)')
assert '<h1>' in render('# Fixture') and '<table>' in render('a | b\n--- | ---\n1 | 2')
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);(root/'a.md').write_text('---\ntags: [fixture, shared]\n---\n# Alpha\nSynthetic source evidence.');(root/'b.md').write_text('---\ntags: [fixture, shared]\n---\n# Beta\nSynthetic destination evidence.')
    library.scan(root)
    with connect() as db:
        db.execute("INSERT INTO library_connections(source,target) VALUES ('a.md','b.md') ON CONFLICT DO NOTHING");queue(db,'a.md')
    assert not library.suggestions('a.md')
    assert process_one(root)
    with connect() as db:export=db.execute("SELECT e.* FROM library_connection_exports e JOIN library_documents d USING(document_id) WHERE d.path='a.md'").fetchone()
    assert export['state']=='published' and 'b|' in (root/export['path']).read_text()
    original=(root/export['path']).read_bytes()
    rename_note('b.md','renamed.md',root)
    assert process_one(root)
    with connect() as db:updated=db.execute('SELECT * FROM library_connection_exports WHERE document_id=%s',(export['document_id'],)).fetchone()
    assert updated['path']!=export['path'] and 'renamed|' in (root/updated['path']).read_text()
    assert (root/export['path']).read_bytes()==original
    aliases=library.path_aliases()
    assert library.resolve_link('a.md','b',{'a.md','renamed.md'},aliases)==['renamed.md']
    with connect() as db:
        db.execute("DELETE FROM library_connections WHERE source='a.md'");queue(db,'a.md')
    assert process_one(root)
    assert library.suggestions('a.md')[0]['path']=='renamed.md'
print('PASS workflow: safe Markdown/media suppression, accepted suggestion hiding, reversible exports, rename recovery and historical links')

# Signed-in project/question/health/evidence paths against the disposable web app.
import http.cookiejar,os,re,urllib.request,urllib.parse,urllib.error,uuid
base=os.environ['FM_TEST_BASE_URL'];assert base=='http://test-web:8000'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(url):
    with client.open(base+url,timeout=20) as response:return response.read().decode()
def post(url,data):
    with client.open(base+url,data=urllib.parse.urlencode(data).encode(),timeout=20) as response:return response.read().decode()
login=get('/login');csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
post('/login',dict(csrf=csrf,username=os.environ['ADMIN_USER'],password=os.environ['ADMIN_PASSWORD']))
csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',get('/settings/ingestion'))[1]
name='workflow-'+uuid.uuid4().hex
with tempfile.TemporaryDirectory(dir='/vault',prefix=name) as directory:
    root=Path(directory);relative=str((root/'question.md').relative_to('/vault'))
    root.joinpath('question.md').write_text('---\nproject: '+name+'\n---\n# Fixture\n## Open questions\n- '+name+' question?\n\n[[missing-fixture-link]]\n')
    root.joinpath('answer.md').write_text('---\ntitle: Fixture answer\nproject: '+name+'\n---\n# Answer\nSynthetic answer evidence.')
    library.scan()
    project=get('/library/projects?'+urllib.parse.urlencode({'project':name}));assert name in project and 'Project questions' in project
    questions=get('/library/questions?'+urllib.parse.urlencode({'project':name}))
    identity=re.search(r'name="id" value="([a-f0-9]{64})"',questions)[1]
    answers=library.documents();answer=next(r for r in answers if r['path']==str((root/'answer.md').relative_to('/vault')))
    post('/library/questions/resolve',dict(csrf=csrf,id=identity,answer_note=answer['title']+' · '+str(answer['document_id'])[:8],state='resolved'))
    assert identity not in get('/library/questions?'+urllib.parse.urlencode({'project':name}))
    assert identity in get('/library/questions?'+urllib.parse.urlencode({'project':name,'state':'all'}))
    post('/library/questions/resolve',dict(csrf=csrf,id=identity,state='dismissed'))
    post('/library/questions/resolve',dict(csrf=csrf,id=identity,state='open'))
    assert identity in get('/library/questions?'+urllib.parse.urlencode({'project':name}))
    note=get('/library/note?'+urllib.parse.urlencode({'path':relative}));assert 'Ask about this source' in note and 'Raw source and line evidence' in note
    preview=get('/vault/wiki/evidence?'+urllib.parse.urlencode({'question':'Synthetic answer','scope':'all','project':name}))
    assert 'No provider request was made' in preview and 'Synthetic answer evidence' in preview
    finding=hashlib.sha256(('link\0Unresolved link: missing-fixture-link').encode()).hexdigest()
    post('/library/health/dismiss',dict(csrf=csrf,path=relative,finding=finding,action='dismiss'))
    with connect() as db:assert db.execute('SELECT finding FROM library_health_dismissals WHERE finding=%s',(finding,)).fetchone()
    post('/library/health/dismiss',dict(csrf=csrf,path=relative,finding=finding,action='reopen'))
    with connect() as db:assert not db.execute('SELECT finding FROM library_health_dismissals WHERE finding=%s',(finding,)).fetchone()
    for url in ['/library/pdf','/settings/ingestion','/library/publications','/library/projects']:
        assert '<main id="main">' in get(url)
        with urllib.request.urlopen(base+url,timeout=20) as response:assert '/login' in response.url
print('PASS signed-in workflow: project links, title answer picker, dismiss/reopen, safe reading, local evidence preview, revision health controls and authentication')

# Publication actions use real authenticated requests against synthetic files only.
from app import publication as publication
from app.wiki import note_header
with tempfile.TemporaryDirectory(dir='/vault',prefix='publication-actions-') as directory:
    root=Path(directory);vault=Path('/vault');rows=[]
    def proposal(label):
        target=root/(label+'.md')
        content=note_header('index','Fixture publication')+'# Fixture\n'+label+'\n'
        first=publication.publish_note(target,content,vault=vault)
        target.write_bytes(target.read_bytes()+b'Human annotation\n')
        result=publication.publish_note(target,content+'Proposal\n',vault=vault)
        assert result['state']=='conflict';rows.append(result['id'])
        return target,result,vault/result['path']
    def action(identity,command='activate',token=csrf,expected=200):
        try:
            post('/library/publications/action',dict(csrf=token,id=identity,action=command))
            assert expected==200
        except urllib.error.HTTPError as error:assert error.code==expected,(error.code,expected)
    target,result,destination=proposal('activate');before=target.read_bytes();draft=destination.read_bytes()
    action(result['id'],token='invalid',expected=403)
    with connect() as db:assert db.execute('SELECT state FROM library_publications WHERE id=%s',(result['id'],)).fetchone()['state']=='conflict'
    action(result['id']);action(result['id'],expected=409)
    assert target.read_bytes()==before and destination.read_bytes()==draft
    target,result,destination=proposal('dismiss');before=target.read_bytes();draft=destination.read_bytes()
    action(result['id'],'dismiss');action(result['id'],expected=409)
    with connect() as db:assert db.execute('SELECT state FROM library_publications WHERE id=%s',(result['id'],)).fetchone()['state']=='dismissed'
    assert target.read_bytes()==before and destination.read_bytes()==draft
    for label in ('edited','missing','imported','reviewed','identity','symlink'):
        target,result,destination=proposal(label);before=target.read_bytes()
        if label=='edited':destination.write_bytes(destination.read_bytes()+b'Edited proposal\n')
        elif label=='missing':destination.unlink()
        elif label=='symlink':destination.unlink();destination.symlink_to(target)
        with connect() as db:
            if label=='imported':db.execute("INSERT INTO library_import_origins(path) VALUES (%s)",(result['path'],))
            elif label=='reviewed':db.execute('INSERT INTO library_overrides(path,reviewed) VALUES (%s,true)',(result['path'],))
            elif label=='identity':db.execute("UPDATE library_publications SET metadata=metadata || '{\"identity_conflict\":true}'::jsonb WHERE id=%s",(result['id'],))
        action(result['id'],expected=409)
        assert target.read_bytes()==before
        action(result['id'],'dismiss')
    action('invalid',expected=400)
    with connect() as db:
        db.execute('DELETE FROM library_import_origins WHERE path LIKE %s',(str(root.relative_to(vault))+'/%',))
        db.execute('DELETE FROM library_overrides WHERE path LIKE %s',(str(root.relative_to(vault))+'/%',))
        db.execute('DELETE FROM library_publications WHERE id=ANY(%s)',(rows,))
print('PASS publication HTTP: CSRF, activate/dismiss idempotence, edited/missing/imported/reviewed/identity/symlink proposals preserve originals')

# Rename preview exposes inbound relationships/collisions and rejects stale approval.
with tempfile.TemporaryDirectory(dir='/vault',prefix='rename-preview-') as directory:
    root=Path(directory);old=root/'Try ΓÇö note.md';new=root/'Try — note.md';old.write_text('# Fixture\nOriginal source.\n')
    reference=root/'ref.md';relative=str(old.relative_to('/vault'));fixed=str(new.relative_to('/vault'))
    reference.write_text('# Reference\n[['+relative+']]\n')
    library.scan()
    with connect() as db:
        db.execute('INSERT INTO library_connections(source,target) VALUES (%s,%s)',(str(reference.relative_to('/vault')),relative))
    preview=get('/library/repair-preview?'+urllib.parse.urlencode({'path':relative}))
    assert '1 notes link to this source' in preview and '1 accepted connections' in preview and 'ref.md' in preview
    expected=re.search(r'name="expected_hash" value="([a-f0-9]{64})"',preview)[1]
    old.write_bytes(old.read_bytes()+b'Human edit after preview\n');before=old.read_bytes()
    try:post('/library/repair-name',dict(csrf=csrf,path=relative,expected_hash=expected));raise AssertionError('Stale preview accepted')
    except urllib.error.HTTPError as error:assert error.code==409
    assert old.read_bytes()==before and not new.exists()
    new.write_text('Destination collision\n');saved=new.read_bytes()
    preview=get('/library/repair-preview?'+urllib.parse.urlencode({'path':relative}))
    assert 'Destination file or app records conflict' in preview and 'name="expected_hash"' not in preview
    assert old.read_bytes()==before and new.read_bytes()==saved
    new.unlink()
    with connect() as db:db.execute('INSERT INTO library_overrides(path,reviewed) VALUES (%s,true)',(fixed,))
    preview=get('/library/repair-preview?'+urllib.parse.urlencode({'path':relative}));assert 'Destination file or app records conflict' in preview
    with connect() as db:db.execute('DELETE FROM library_overrides WHERE path=%s',(fixed,))
    preview=get('/library/repair-preview?'+urllib.parse.urlencode({'path':relative}));expected=re.search(r'name="expected_hash" value="([a-f0-9]{64})"',preview)[1]
    post('/library/repair-name',dict(csrf=csrf,path=relative,expected_hash=expected))
    assert not old.exists() and new.read_bytes()==before and relative in reference.read_text()
    with connect() as db:
        assert db.execute('SELECT target FROM library_connections WHERE target=%s',(fixed,)).fetchone()
        db.execute('DELETE FROM library_connections WHERE source=%s',(str(reference.relative_to('/vault')),))
print('PASS rename preview: inbound links/connections, filesystem/catalog collisions, stale preview preserves edits, accepted rename preserves embedded links')

# Paginated failure history and guarded retries, confined to the disposable DB.
with connect() as db:
    identities=[db.execute("INSERT INTO library_index_jobs(mode,state,error) VALUES ('full','failed','Synthetic retry fixture') RETURNING id").fetchone()['id'] for _ in range(31)]
assert 'Next' in get('/library/jobs') and 'Previous' in get('/library/jobs?page=2')
assert 'Last successful scan:' in get('/library/jobs') and 'Local worker:' in get('/library/jobs') and 'UTC+05:00' in get('/library/jobs')
post('/library/jobs/retry',dict(csrf=csrf,id=identities[0]))
with connect() as db:
    assert db.execute("SELECT id FROM library_index_jobs WHERE state='queued' AND mode='full'").fetchone()
    db.execute("INSERT INTO library_index_errors(path,category) VALUES ('retry-fixture.md','Synthetic read failure')")
post('/library/jobs/retry',dict(csrf=csrf,path='retry-fixture.md'))
try:post('/library/jobs/retry',dict(csrf='invalid',id=identities[0]));raise AssertionError('CSRF retry accepted')
except urllib.error.HTTPError as error:assert error.code==403
with tempfile.TemporaryDirectory(dir='/vault',prefix='rename-retry-') as directory:
    root=Path(directory);source=root/'source.md';destination=root/'destination.md';source.write_text('# Source\nSynthetic retry source.');library.scan()
    old=str(source.relative_to('/vault'));new=str(destination.relative_to('/vault'));original=source.read_bytes()
    with connect() as db:
        document=db.execute('SELECT document_id FROM library_documents WHERE path=%s',(old,)).fetchone()['document_id']
        operation=db.execute("INSERT INTO library_operations(document_id,old_path,new_path,content_hash,state) VALUES (%s,%s,%s,%s,'conflict') RETURNING id",(document,old,new,hashlib.sha256(original).hexdigest())).fetchone()['id']
    destination.write_text('Human destination collision')
    try:post('/library/jobs/retry-rename',dict(csrf=csrf,id=operation));raise AssertionError('Collision overwritten')
    except urllib.error.HTTPError as error:assert error.code==409
    assert source.read_bytes()==original and destination.read_text()=='Human destination collision'
    destination.unlink();post('/library/jobs/retry-rename',dict(csrf=csrf,id=operation))
    assert not source.exists() and destination.read_bytes()==original
    try:post('/library/jobs/retry-rename',dict(csrf=csrf,id=operation));raise AssertionError('Completed rename retried')
    except urllib.error.HTTPError as error:assert error.code==409
with connect() as db:
    db.execute('DELETE FROM library_index_jobs WHERE id=ANY(%s)',(identities,))
    db.execute("DELETE FROM library_index_errors WHERE path='retry-fixture.md'")
for url in ['/library/jobs','/library/jobs?section=errors','/library/jobs?section=renames']:
    assert '<main id="main">' in get(url)
    with urllib.request.urlopen(base+url,timeout=20) as response:assert '/login' in response.url
print('PASS failure workflow: job pagination, scan retries, CSRF/login, rename collision/retry/idempotence')

# Indexed diagnostic lookup preserves historical/exact/ambiguous resolution.
from collections import defaultdict
paths={'folder/note.md','other/note.md','folder/source.md','renamed.md'}
lookup=defaultdict(list)
for path in sorted(paths):
    parts=path.split('/')
    for index in range(1,len(parts)):lookup['/'.join(parts[index:])].append(path)
for target in ('note','folder/note','missing','note#heading','old'):
    aliases={'old.md':{'renamed.md'}}
    assert set(library.resolve_link('source.md',target,paths,aliases))==set(library.resolve_link('source.md',target,paths,aliases,lookup))
print('PASS health lookup: indexed suffix resolution preserves exact, ambiguous, missing and historical links')

# Display-origin refinement cannot confer new evidence rights.
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);history='Forgetful Me/Browsing History/2026/10/legacy.md';navigation='navigation.md';imported='imported.md'
    (root/history).parent.mkdir(parents=True);(root/history).write_text('# Legacy history\nDisplaylabel fixture.\n')
    content=note_header('index','Navigation fixture')+'# Navigation\nDisplaylabel fixture.\n'
    (root/navigation).write_text(content);(root/imported).write_text(content)
    with connect() as db:db.execute('INSERT INTO library_import_origins(path) VALUES (%s)',(imported,))
    library.scan(root)
    rows={r['path']:r for r in library.documents()}
    assert rows[history]['display_origin']=='generated' and rows[history]['origin']=='imported'
    assert rows[navigation]['display_origin']=='generated' and rows[navigation]['evidence_scope']=='none'
    assert rows[imported]['display_origin']=='imported' and rows[imported]['evidence_scope']=='none'
    assert {r['path'] for r in library.search('Displaylabel',origin='generated')}=={history,navigation}
    assert navigation not in {r['path'] for r in library.search('Displaylabel',for_ai=True)}
    with connect() as db:db.execute('DELETE FROM library_import_origins WHERE path=%s',(imported,))
print('PASS display origin: legacy history/generated navigation metrics, import provenance priority, unchanged AI evidence boundaries')
