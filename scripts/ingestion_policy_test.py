"""FM-06 policy boundaries with disposable DB/vault and synthetic HTTP data."""
import contextlib
import hashlib
import http.cookiejar
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from app import ingestion_policy as policy, browser_history, page_scraper, obsidian_export
from app.db import connect, require_isolated_test

require_isolated_test()
original_url = 'https://name:credential@example.invalid/report?year=2026&token=PRIVATE_MARKER&client_secret=OTHER_MARKER#access_token=FRAGMENT_MARKER'
display = policy.safe_display_url(original_url)
assert all(marker not in display for marker in ('credential','PRIVATE_MARKER','OTHER_MARKER','FRAGMENT_MARKER'))
assert urllib.parse.parse_qs(urllib.parse.urlsplit(display).query)['year'] == ['2026']
assert policy.normalize_domain('Café.Example') == 'xn--caf-dma.example'
for bad in ('https://example.com','example.com/path','*.example.com','example.com:80','example..com'):
    try:policy.normalize_domain(bad);raise AssertionError('Invalid domain accepted')
    except ValueError:pass

with connect() as db, tempfile.TemporaryDirectory(dir='/vault') as temporary:
    @contextlib.contextmanager
    def same_connection():yield db
    with db.transaction(force_rollback=True),patch.object(policy,'connect',same_connection),patch.object(page_scraper,'connect',same_connection),patch.object(browser_history,'connect',same_connection),patch.object(obsidian_export,'connect',same_connection):
        db.execute('DELETE FROM page_captures');db.execute('DELETE FROM ingestion_domains');db.execute('DELETE FROM capture_attempt_log');db.execute('DELETE FROM capture_domain_state')
        db.execute('UPDATE ingestion_controls SET visits_enabled=NULL,history_exports_enabled=NULL,downloads_enabled=NULL,local_index_enabled=NULL,ai_enabled=NULL,capture_mode=\'all\' WHERE id=1')
        inherited = policy.controls(db)
        legacy = db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()['automation_enabled']
        assert inherited['visits'] and inherited['local_index']
        assert inherited['downloads'] == legacy and inherited['history_exports'] == legacy
        db.execute('UPDATE ingestion_controls SET downloads_enabled=false,history_exports_enabled=false,visits_enabled=false WHERE id=1')
        assert obsidian_export.export_pending(Path(temporary)) == 0
        with patch.object(page_scraper,'scrape_page') as fetch:
            assert not page_scraper.process_page();fetch.assert_not_called()
        from app.browser_history import Visit
        visit = Visit(event_id='synthetic-policy',url='https://example.invalid/fixture',visited_at=datetime(2026,1,1,tzinfo=timezone.utc))
        before = db.execute('SELECT count(*) AS n FROM browser_visits').fetchone()['n']
        try:browser_history.save_import('Paused fixture',[visit]);raise AssertionError('Paused import accepted')
        except Exception as error:assert getattr(error,'status_code',None) == 409
        assert db.execute('SELECT count(*) AS n FROM browser_visits').fetchone()['n'] == before

        db.execute("UPDATE ingestion_controls SET downloads_enabled=true,capture_mode='all',requests_per_minute=60,hourly_budget=1000,domain_delay_seconds=30 WHERE id=1")
        db.execute("INSERT INTO ingestion_domains(domain,rule) VALUES ('blocked.invalid','block'),('allowed.invalid','allow')")
        assert not policy.allowed(db,'https://blocked.invalid/a',True)[0]
        assert not policy.allowed(db,'https://child.blocked.invalid/a',True)[0]
        assert policy.allowed(db,'https://blocked.invalid.evil/a',True)[0]
        db.execute("UPDATE ingestion_controls SET capture_mode='allowlisted' WHERE id=1")
        assert policy.allowed(db,'https://child.allowed.invalid/a')[0]
        assert not policy.allowed(db,'https://other.invalid/a')[0]
        db.execute("INSERT INTO ingestion_domains(domain,rule) VALUES ('child.allowed.invalid','block')")
        assert not policy.allowed(db,'https://child.allowed.invalid/a',True)[0]
        db.execute("UPDATE ingestion_controls SET capture_mode='selected' WHERE id=1")
        assert not policy.allowed(db,'https://allowed.invalid/a')[0]
        assert policy.allowed(db,'https://allowed.invalid/a',True)[0]

        def add(url, selected=True, cancelled=False, excluded=False):
            identity=hashlib.sha256(url.encode()).hexdigest()
            db.execute('INSERT INTO page_captures(url_hash,url,selected,cancelled,excluded) VALUES (%s,%s,%s,%s,%s)',(identity,url,selected,cancelled,excluded))
            return identity
        blocked = add('https://blocked.invalid/a')
        waiting = add('https://allowed.invalid/unselected',False)
        cancelled = add('https://allowed.invalid/cancelled',True,True)
        excluded = add('https://allowed.invalid/excluded',True,False,True)
        selected = add('https://allowed.invalid/selected')
        db.execute("UPDATE page_captures SET next_attempt_at=now()-interval '1 minute' WHERE url_hash=%s",(blocked,))
        job = policy.claim_capture(db)
        assert job['url_hash'] == selected
        assert db.execute('SELECT policy_state FROM page_captures WHERE url_hash=%s',(blocked,)).fetchone()['policy_state'] == 'waiting'
        policy.finish_capture(db,job,'retry')
        assert db.execute('SELECT failures,next_allowed_at>now() AS deferred FROM capture_domain_state WHERE domain=%s',('allowed.invalid',)).fetchone() == {'failures':1,'deferred':True}
        assert policy.claim_capture(db) is None
        db.execute('DELETE FROM page_captures');db.execute('DELETE FROM capture_domain_state');db.execute('DELETE FROM capture_attempt_log')
        db.execute("UPDATE ingestion_controls SET capture_mode='all',requests_per_minute=1,hourly_budget=1000 WHERE id=1")
        add('https://first.invalid/a');add('https://second.invalid/a')
        assert policy.claim_capture(db)
        assert policy.claim_capture(db) is None
        db.execute('DELETE FROM capture_attempt_log');db.execute('DELETE FROM capture_domain_state')
        db.execute('UPDATE ingestion_controls SET requests_per_minute=60,hourly_budget=1 WHERE id=1')
        assert policy.claim_capture(db)
        assert policy.claim_capture(db) is None

        # Redirects are checked against the same server-side policy before fetch.
        db.execute('DELETE FROM page_captures');db.execute('DELETE FROM capture_attempt_log');db.execute('DELETE FROM capture_domain_state')
        db.execute('UPDATE ingestion_controls SET hourly_budget=1000 WHERE id=1')
        redirect = add('https://allowed.invalid/redirect')
        def redirect_fixture(url,digest):
            page_scraper._FETCH_POLICY_GUARD.get()('https://blocked.invalid/target')
            raise AssertionError('Blocked redirect passed its fetch guard')
        with patch.object(page_scraper,'scrape_page',redirect_fixture):assert page_scraper.process_page()
        row=db.execute('SELECT state,error FROM page_captures WHERE url_hash=%s',(redirect,)).fetchone()
        assert row['state']=='blocked' and row['error']=='Domain blocked by ingestion policy'

        # Reimport retains repeat visits, source identity, cancellation and exclusions.
        db.execute('UPDATE ingestion_controls SET visits_enabled=true,history_exports_enabled=true WHERE id=1')
        first=Visit(event_id='first-event',url='https://example.invalid/report?year=2026&token=RAW_IDENTITY_MARKER',visited_at=datetime(2026,1,1,tzinfo=timezone.utc))
        second=Visit(event_id='second-event',url=first.url,visited_at=datetime(2026,1,2,tzinfo=timezone.utc))
        assert browser_history.save_import('Policy reimport fixture',[first,second]) == 2
        identity=hashlib.sha256(first.url.encode()).hexdigest()
        db.execute("UPDATE page_captures SET excluded=true,cancelled=true,state='blocked',error='Vault cleared; waiting for a new browsing import' WHERE url_hash=%s",(identity,))
        # Simulate the first HTTP request's transaction ending (ON COMMIT DROP).
        db.execute('DROP TABLE import_visits')
        assert browser_history.save_import('Policy reimport fixture',[first,second]) == 0
        row=db.execute('SELECT url,excluded,cancelled,state FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()
        assert row=={'url':first.url,'excluded':True,'cancelled':True,'state':'blocked'}
        assert obsidian_export.export_pending(Path(temporary)) == 2
        exported='\n'.join(path.read_text() for path in Path(temporary).rglob('*.md'))
        assert 'RAW_IDENTITY_MARKER' not in exported and 'year=2026' in exported
        assert db.execute('SELECT url FROM browser_visits WHERE event_id=%s',('first-event',)).fetchone()['url'] == first.url
print('FM-06 inheritance, pauses, domain boundaries, explicit selection, minute/hour budgets, backoff, redirects, reimport and URL redaction passed')

# Signed-in forms target only the separate fixture HTTP service.
import os
base=os.environ['FM_TEST_BASE_URL'];assert base=='http://test-web:8000'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path):
    with client.open(base+path,timeout=20) as response:return response.read().decode()
def post(path,data):
    with client.open(base+path,data=urllib.parse.urlencode(data).encode(),timeout=20) as response:return response.read().decode()
login=get('/login');token=re.search(r'name="csrf" value="([a-f0-9]+)"',login)[1]
post('/login',{'username':os.environ['ADMIN_USER'],'password':os.environ['ADMIN_PASSWORD'],'csrf':token})
with connect() as db:
    initial=db.execute('SELECT * FROM ingestion_controls WHERE id=1').fetchone()
identity=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
domain='fixture-'+uuid.uuid4().hex+'.invalid'
try:
    page=get('/settings/ingestion');token=re.search(r'name="csrf" value="([a-f0-9]+)"',page)[1]
    assert 'Ingestion controls' in page and 'Site policies' in page and 'Capture queue' in page
    settings={name:'inherit' for name in policy.CONTROL_NAMES}
    settings.update(csrf=token,capture_mode='selected',requests_per_minute='4',hourly_budget='25',domain_delay_seconds='15')
    post('/settings/ingestion/controls',settings)
    post('/settings/ingestion/domain',dict(csrf=token,domain=domain,rule='block',include_subdomains='1',action='save'))
    with connect() as db:db.execute("INSERT INTO page_captures(url_hash,url) VALUES (%s,%s)",(identity,'https://'+domain+'/synthetic?token=HIDDEN_HTTP_MARKER'))
    assert 'HIDDEN_HTTP_MARKER' not in get('/settings/ingestion')
    post('/settings/ingestion/queue',dict(csrf=token,id=identity,action='select'))
    post('/settings/ingestion/queue',dict(csrf=token,id=identity,action='cancel'))
    with connect() as db:assert db.execute('SELECT selected,cancelled FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()=={'selected':True,'cancelled':True}
    post('/settings/ingestion/queue',dict(csrf=token,id=identity,action='retry'))
    with connect() as db:assert not db.execute('SELECT cancelled FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()['cancelled']
    try:post('/settings/ingestion/controls',{**settings,'csrf':'invalid'});raise AssertionError('Invalid CSRF accepted')
    except urllib.error.HTTPError as error:assert error.code==403
    try:urllib.request.urlopen(base+'/settings/ingestion/queue',data=b'action=cancel',timeout=10);raise AssertionError('Unsigned action accepted')
    except urllib.error.HTTPError as error:assert error.code==401
    with urllib.request.urlopen(base+'/settings/ingestion',timeout=10) as response:assert '/login' in response.url
finally:
    with connect() as db:
        names=[name for name in initial if name not in ('id','updated_at')]
        db.execute('UPDATE ingestion_controls SET '+','.join(name+'=%s' for name in names)+' WHERE id=1',tuple(initial[name] for name in names))
        db.execute('DELETE FROM ingestion_domains WHERE domain=%s',(domain,));db.execute('DELETE FROM page_captures WHERE url_hash=%s',(identity,))
print('FM-06 authenticated/CSRF settings, domain rules, queue selection/cancel/retry and redacted HTTP displays passed')
