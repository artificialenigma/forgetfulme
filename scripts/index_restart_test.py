"""Kill a real disposable large scan; verify transaction/progress/restart boundaries."""
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from app.db import connect,require_isolated_test
from app import library
from app.library_index import request_scan
require_isolated_test()
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)/'vault';root.mkdir();marker=Path(directory)/'blocked'
    for index in range(1000):(root/f'{index:04}.md').write_text(f'# Fixture {index}\nStable original index evidence {index}.\n')
    library.scan(root,force=True)
    with connect() as db:
        before={r['path']:(str(r['document_id']),r['content_hash']) for r in db.execute('SELECT path,document_id,content_hash FROM library_documents WHERE present').fetchall()}
        db.execute("UPDATE library_index_jobs SET state='failed',error='Synthetic setup superseded' WHERE state='queued'")
    for index in range(10):(root/f'{index:04}.md').write_text(f'# Changed {index}\nChanged revision evidence {index}.\n')
    request_scan('full')
    with connect() as db:job=db.execute("SELECT id FROM library_index_jobs WHERE state='queued' AND mode='full'").fetchone()['id']
    child_code='''import sys,time
from pathlib import Path
from app.db import require_isolated_test
require_isolated_test()
from app import library,library_index
original=library_index.snapshot
count=0
def blocked(path,limit):
 global count
 data=original(path,limit);count+=1
 if count==100:
  Path(sys.argv[2]).write_text('ready')
  time.sleep(60)
 return data
library_index.snapshot=blocked
library.scan(Path(sys.argv[1]),force=True)
'''
    child=subprocess.Popen([sys.executable,'-c',child_code,str(root),str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+25
        while not marker.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.05)
        assert marker.exists(),'Large scan did not reach interruption boundary'
        with connect() as db:
            state=db.execute('SELECT state,seen FROM library_index_jobs WHERE id=%s',(job,)).fetchone()
            assert state['state']=='running' and state['seen']>=80
            assert {r['path']:(str(r['document_id']),r['content_hash']) for r in db.execute('SELECT path,document_id,content_hash FROM library_documents WHERE present').fetchall()}==before
        child.kill();child.communicate(timeout=5)
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=5)
    # Process death rolled back catalog writes; durable progress remains visible.
    with connect() as db:
        assert db.execute('SELECT state FROM library_index_jobs WHERE id=%s',(job,)).fetchone()['state']=='running'
        assert {r['path']:(str(r['document_id']),r['content_hash']) for r in db.execute('SELECT path,document_id,content_hash FROM library_documents WHERE present').fetchall()}==before
    library.scan(root,force=True)
    with connect() as db:
        interrupted=db.execute('SELECT state,error FROM library_index_jobs WHERE id=%s',(job,)).fetchone()
        assert interrupted['state']=='failed' and 'interrupted' in interrupted['error']
        newest=db.execute('SELECT state,seen,failed FROM library_index_jobs ORDER BY id DESC LIMIT 1').fetchone()
        assert newest=={'state':'succeeded','seen':1000,'failed':0}
        after={r['path']:(str(r['document_id']),r['content_hash']) for r in db.execute('SELECT path,document_id,content_hash FROM library_documents WHERE present').fetchall()}
        assert all(after[path][0]==before[path][0] for path in before)
        assert sum(after[path][1]!=before[path][1] for path in before)==10
    assert library.scan(root)==0
    (root/'0999.md').unlink();library.scan(root)
    with connect() as db:
        row=db.execute("SELECT document_id,present FROM library_documents WHERE path='0999.md'").fetchone()
        assert not row['present'] and str(row['document_id'])==before['0999.md'][0]
print('PASS 1k index restart: real process kill, durable progress, atomic catalog rollback, interrupted job recovery, stable identities, changed revisions and retained deleted identity')
