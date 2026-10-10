"""Check network boundaries, extraction and retry behavior without personal data."""
import hashlib
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from app import page_scraper as module

public = [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
with patch.object(module.socket,'getaddrinfo',return_value=public):
    for address in ['file:///tmp/private','http://localhost:8080','https://user:password@example.com']:
        try: module.public_target(address)
        except module.Blocked: pass
        else: raise AssertionError('Unsafe target accepted')
with patch.object(module.socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]):
    try: module.public_target('https://example.com')
    except module.Blocked: pass
    else: raise AssertionError('Private DNS address accepted')
article = ('<html><head><title>Public test article</title></head><body><nav>Navigation clutter</nav><article><h1>Public test article</h1><p>' + 'This article contains readable information about browser archiving and durable Markdown capture. '*12 + '</p><h2>Useful section</h2><p>' + 'A second paragraph describes how notes become available in the shared vault. '*10 + '</p></article><script>SECRET_SCRIPT_CONTENT</script></body></html>').encode()
with TemporaryDirectory() as temp, patch.object(module,'public_target',return_value=None), patch.object(module,'fetch',return_value=(200,'text/html',article,'https://example.com/article')):
    path, final, engine = module.scrape_page('https://example.com/article','test-note',Path(temp))
    note = (Path(temp)/path).read_text()
    assert 'readable information' in note and 'Useful section' in note
    assert 'SECRET_SCRIPT_CONTENT' not in note and 'Navigation clutter' not in note
    assert path=='Forgetful Me/Pages/test-note.md'
    module.scrape_page('https://example.com/article','test-note',Path(temp))
    assert len(list(Path(temp).rglob('*.md')))==1
with patch.object(module,'public_target',return_value=None), patch.object(module,'fetch',return_value=(200,'application/pdf',b'pdf','https://example.com/article')):
    try: module.scrape_page('https://example.com/article','test-note')
    except module.Blocked: pass
    else: raise AssertionError('Unsupported page type accepted')
parser=module.RobotFileParser();parser.parse(['User-agent: *','Disallow: /private'])
module._ROBOTS['https://example.com']=(module.time.monotonic(),parser)
try: module.check_robots('https://example.com/private')
except module.Blocked: pass
else: raise AssertionError('Robots restriction ignored')
class Result:
    def __init__(self,row): self.row=row
    def fetchone(self): return self.row
class DB:
    def __init__(self,attempts=0): self.attempts=attempts;self.update=None
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params=None):
        if sql.startswith('UPDATE'):self.update=(sql,params);return Result(None)
        return Result({'url_hash':'hash','url':'https://example.com','attempts':self.attempts})
def process_fixture():
    # Scheduling/budgets are covered by ingestion_policy_test; this fixture
    # targets fetch outcomes and revision processing with a synthetic row.
    with patch('app.ingestion_policy.claim_capture',side_effect=lambda db:db.execute('SELECT fixture').fetchone()):
        return module.process_page()
for attempts,expected in [(0,'retry'),(2,'failed')]:
    db=DB(attempts)
    with patch.object(module,'connect',return_value=db),patch.object(module,'scrape_page',side_effect=module.FetchFailed('Connection or TLS failure')):
        assert process_fixture()
        assert db.update[1][0]==expected
print('Public-address checks, extraction, boilerplate removal, deduped files, robots, content-type and retry tests passed')

db=DB()
with TemporaryDirectory() as temp:
    fixture=Path(temp)/'capture.md';fixture.write_text('# Fixture\n\n---\n\nSource evidence')
    with patch.object(module,'connect',return_value=db),patch.object(module,'scrape_page',return_value=('Forgetful Me/Pages/hash.md','https://example.com','Trafilatura')),patch('app.library.safe_path',return_value=fixture):
        process_fixture()
        assert "state='complete'" in db.update[0] and db.update[1][1]=='Forgetful Me/Pages/hash.md'
db=DB()
with patch.object(module,'connect',return_value=db),patch.object(module,'scrape_page',side_effect=module.Blocked('Private address')):
    process_fixture()
    assert "state='blocked'" in db.update[0]
