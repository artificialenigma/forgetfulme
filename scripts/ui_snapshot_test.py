"""Export populated, synthetic signed-in HTML for offline visual/a11y review."""
import base64,hashlib,json,os,re,tempfile,urllib.request,urllib.parse
from pathlib import Path
from app.db import require_isolated_test,connect
from app import library,publication
from app.auth import COOKIE,issue_session
from app.wiki import note_header
require_isolated_test()
base=os.environ['FM_TEST_BASE_URL'];assert base=='http://test-web:8000'
with tempfile.TemporaryDirectory(dir='/vault',prefix='ui-review-') as directory:
    root=Path(directory);project='Synthetic research project';source=root/'research.md'
    source.write_text('---\ntitle: Synthetic research evidence\nproject: '+project+'\ntags: [hardware, research]\n---\n# Research evidence\n\nUnicode: Café · ދިވެހި · Maldives.\n\n'+('LongIdentifier'*35)+'\n\n| Topic | Observation |\n| --- | --- |\n| Hardware | Synthetic evidence only |\n\n```c\n#include <stdio.h>\n```\n\n## Open questions\n- What does this synthetic source establish?\n\n[[missing-synthetic-source]]\n')
    (root/'answer.md').write_text('---\ntitle: Synthetic answer\nproject: '+project+'\n---\n# Answer\nSynthetic answer evidence.\n')
    broken=root/'Try ΓÇö note.md';broken.write_text('# Filename repair fixture\nSynthetic note.\n')
    pdf=root/'selected.pdf';pdf.write_bytes(b'%PDF-1.7\nSynthetic visual-only attachment')
    library.scan()
    with connect() as db:
        db.execute('INSERT INTO library_connections(source,target) VALUES (%s,%s)',(str(source.relative_to('/vault')),str((root/'answer.md').relative_to('/vault'))))
        document=db.execute('SELECT document_id,content_hash FROM library_documents WHERE path=%s',(str(pdf.relative_to('/vault')),)).fetchone()
        db.execute('INSERT INTO library_pdf_selections(document_id) VALUES (%s)',(document['document_id'],))
        db.execute("INSERT INTO library_pdf_jobs(document_id,revision,extractor_version,state,error) VALUES (%s,%s,'synthetic-visual-fixture','ocr_required','Scanned fixture needs optional OCR')",(document['document_id'],document['content_hash']))
        db.execute("INSERT INTO library_index_jobs(mode,state,seen,changed,failed,error) VALUES ('full','failed',1000,999,1,'Synthetic unreadable file; last good evidence retained')")
    target=root/'proposal.md';content=note_header('index','Synthetic publication proposal')+'# Proposal\nSynthetic generated draft.\n'
    publication.publish_note(target,content);target.write_bytes(target.read_bytes()+b'Human fixture annotation\n');publication.publish_note(target,content+'Updated fixture.\n')
    routes={'library':'/library?q=Synthetic','projects':'/library/projects?'+urllib.parse.urlencode({'project':project}),'note':'/library/note?'+urllib.parse.urlencode({'path':str(source.relative_to('/vault'))}),'questions':'/library/questions?'+urllib.parse.urlencode({'project':project}),'health':'/library/health','jobs':'/library/jobs','pdf':'/library/pdf','ingestion':'/settings/ingestion','publications':'/library/publications','repair':'/library/repair-preview?'+urllib.parse.urlencode({'path':str(broken.relative_to('/vault'))})}
    css=Path('/srv/app/static/dashboard.css').read_text();snapshots={}
    for name,route in routes.items():
        request=urllib.request.Request(base+route,headers={'Cookie':COOKIE+'='+issue_session()})
        with urllib.request.urlopen(request,timeout=30) as response:
            assert response.url==base+route
            body=response.read().decode()
        body=body.replace('<link rel="stylesheet" href="/static/dashboard.css">','<style>'+css+'</style>')
        body=re.sub(r'name="csrf" value="[^"]*"','name="csrf" value="synthetic-preview"',body)
        # Review snapshots are inert; no fixture or production state can be submitted.
        body=body.replace('</body>','<script>document.addEventListener("submit",e=>e.preventDefault());</script></body>')
        snapshots[name]=base64.b64encode(body.encode()).decode()
    print('UI_SNAPSHOTS '+json.dumps(snapshots))
print('PASS populated synthetic snapshots: ten authenticated screens, Unicode/long text/code/table, queues/conflict/repair; inert forms and no provider calls')
