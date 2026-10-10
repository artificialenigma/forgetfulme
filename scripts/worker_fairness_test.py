"""Independent local queue scheduling and pause behavior without provider calls."""
import threading,time
from unittest.mock import patch
from app.db import require_isolated_test,connect
from app import library_worker,wiki
require_isolated_test()
with patch('app.library_worker.enabled',return_value=False),patch('app.library.scan') as scan,patch('app.pdf_extract.process_one') as pdf:
    assert library_worker.cycle(123)==123
    scan.assert_not_called();pdf.assert_not_called()
started=threading.Event();release=threading.Event()
def slow_scan():started.set();assert release.wait(10)
with connect() as db:db.execute("UPDATE wiki_questions SET state='failed' WHERE state='pending'")
with patch('app.library_worker.enabled',return_value=True),patch('app.library.scan',slow_scan),patch('app.pdf_extract.process_one',return_value=False),patch('app.ai_provider.settings',return_value={'enabled':True}):
    thread=threading.Thread(target=library_worker.cycle,args=(0,));thread.start()
    try:
        assert started.wait(5)
        before=time.monotonic();assert not wiki.answer_one();assert time.monotonic()-before<2
        library_worker.heartbeat()
        with connect() as db:assert db.execute("SELECT last_seen>now()-interval '5 seconds' AS fresh FROM service_status WHERE service='library-worker'").fetchone()['fresh']
    finally:release.set();thread.join(timeout=10)
    assert not thread.is_alive()
print('PASS independent local worker: indexing pause, PDF scheduling, responsive AI queue and heartbeat during a blocked scan')

from app.library_index import progress
with connect() as db:
    prior=db.execute("SELECT last_seen FROM service_status WHERE service='wiki-worker'").fetchone()
    job=db.execute("INSERT INTO library_index_jobs(mode) VALUES ('incremental') RETURNING id").fetchone()['id']
progress(job,1,1,0)
with connect() as db:
    assert db.execute("SELECT last_seen FROM service_status WHERE service='wiki-worker'").fetchone()==prior
    assert db.execute("SELECT last_seen>now()-interval '5 seconds' AS fresh FROM service_status WHERE service='library-worker'").fetchone()['fresh']
print('PASS index progress cannot mask an unavailable wiki worker')
