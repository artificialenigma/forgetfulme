"""Source publication, recapture revisions and inference conflicts in fixtures."""
import contextlib
import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from app import wiki, page_scraper
from app.db import connect, require_isolated_test

require_isolated_test()

def captured(body,stamp='first'):
    return '# Fixture article\n\nFetched: '+stamp+'\nExtractor: Fixture\n\n---\n\n'+body+'\n'

def source_id(index):
    return hashlib.sha256(('synthetic-source-'+str(index)).encode()).hexdigest()

assert page_scraper.capture_hash(captured('Stable evidence','one'))==page_scraper.capture_hash(captured('Stable evidence','two'))
assert page_scraper.capture_hash(captured('Changed evidence'))!=page_scraper.capture_hash(captured('Stable evidence'))
assert page_scraper.capture_hash(captured('Stable evidence').replace('\n','\r\n'))==page_scraper.capture_hash(captured('Stable evidence'))
assert 'Late source evidence' in page_scraper.capture_content(captured('Opening\n\n## Wiki record\n\nLate source evidence'))

with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'source.md'
    original=wiki.note_header('source','Fixture')+'# Fixture\nOriginal content\n'
    assert wiki.atomic_note(destination,original)
    saved=destination.read_bytes()
    expected=hashlib.sha256(saved).hexdigest()
    destination.write_bytes(saved+b'Human annotation\n')
    assert not wiki.atomic_note(destination,wiki.note_header('source','Fixture')+'# Proposed\n',expected_hash=expected)
    assert destination.read_bytes()==saved+b'Human annotation\n'
    assert list(destination.parent.glob('source — pending *.md'))
    destination.write_text('---\nmanaged_by: "forgetfulme spoof"\nreviewed: false\n---\nUser content')
    assert not wiki.atomic_note(destination,original)
    destination.unlink();destination.symlink_to(Path(temporary)/'user.md')
    assert not wiki.atomic_note(destination,original)
    collision=Path(temporary)/'collision.md'
    assert wiki.atomic_note(collision,wiki.note_header('source','Same title',source_id=source_id(1))+'First owned source')
    collision_bytes=collision.read_bytes()
    assert not wiki.atomic_note(collision,wiki.note_header('source','Same title',source_id=source_id(2))+'Different source')
    assert collision.read_bytes()==collision_bytes
print('Stable capture hashes, exact ownership, symlink protection and preserved conflict drafts passed')

with tempfile.TemporaryDirectory() as temporary,connect() as db:
    vault=Path(temporary)
    @contextlib.contextmanager
    def same_connection():yield db
    with db.transaction(force_rollback=True),patch.object(wiki,'connect',same_connection):
        db.execute('DELETE FROM page_captures')
        for index in range(24):
            relative='missing/'+str(index)+'.md'
            if index>=12:
                relative='reviewed/'+str(index)+'.md'
                target=vault/relative;target.parent.mkdir(exist_ok=True)
                target.write_text(wiki.note_header('raw_source','Reviewed',reviewed=True)+captured('Reviewed source evidence. '*30))
            db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at) VALUES (%s,'https://example.invalid/deferred','complete',%s,now()-interval '2 days')",(source_id(index),relative))
        valid_id=source_id(100)
        raw_relative='Forgetful Me/Pages/'+valid_id+'.md'
        original=vault/raw_relative;original.parent.mkdir(parents=True,exist_ok=True);original.write_text(captured('Useful source evidence. '*30))
        revision=page_scraper.capture_hash(original.read_text())
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at,capture_content_hash) VALUES (%s,'https://example.invalid/valid','complete',%s,now(),%s)",(valid_id,raw_relative,revision))
        assert wiki.refresh_sources(vault)==0
        assert db.execute("SELECT count(*) AS n FROM page_captures WHERE publication_state='missing'").fetchone()['n']==12
        assert wiki.refresh_sources(vault)==1
        record=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(valid_id,)).fetchone()
        assert record['publication_state']=='succeeded' and record['wiki_indexed_at'] is not None

        # A protected destination never receives an indexed-complete status.
        protected_id=source_id(101)
        protected_relative='Forgetful Me/Pages/'+protected_id+'.md'
        (vault/protected_relative).write_text(captured('Another valid source. '*30))
        protected_record=vault/wiki.source_path(protected_id,'Fixture article')
        protected_record.parent.mkdir(parents=True,exist_ok=True)
        reviewed=wiki.note_header('source','Fixture article',reviewed=True)+'Human reviewed summary\n'
        protected_record.write_text(reviewed)
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at) VALUES (%s,'https://example.invalid/protected','complete',%s,now())",(protected_id,protected_relative))
        assert wiki.refresh_sources(vault)==0
        protected=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(protected_id,)).fetchone()
        assert protected['publication_state']=='protected' and protected['wiki_indexed_at'] is None
        assert protected_record.read_text()==reviewed

        imported_id=source_id(104)
        imported_relative='Forgetful Me/Pages/'+imported_id+'.md'
        imported=vault/imported_relative;imported.write_text(captured('Imported original evidence. '*30))
        imported_bytes=imported.read_bytes()
        db.execute('INSERT INTO library_import_origins(path) VALUES (%s)',(imported_relative,))
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at) VALUES (%s,'https://example.invalid/imported','complete',%s,now())",(imported_id,imported_relative))
        assert wiki.refresh_sources(vault)==0
        assert db.execute('SELECT publication_state FROM page_captures WHERE url_hash=%s',(imported_id,)).fetchone()['publication_state']=='protected'
        assert imported.read_bytes()==imported_bytes
        unsafe_id=source_id(105)
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at) VALUES (%s,'https://example.invalid/unsafe','complete','../outside.md',now())",(unsafe_id,))
        assert wiki.refresh_sources(vault)==0
        assert db.execute('SELECT publication_state FROM page_captures WHERE url_hash=%s',(unsafe_id,)).fetchone()['publication_state']=='retry'

        failure_id=source_id(102)
        failure_relative='Forgetful Me/Pages/'+failure_id+'.md'
        (vault/failure_relative).write_text(captured('Publication failure evidence. '*30))
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at) VALUES (%s,'https://example.invalid/failure','complete',%s,now())",(failure_id,failure_relative))
        from app import publication
        writer=publication.publish_note
        def fail_record(path,content,**kwargs):
            return {'state':'conflict','path':str(path)} if '/wiki/sources/' in str(path) else writer(path,content,**kwargs)
        with patch.object(publication,'publish_note',fail_record):assert wiki.refresh_sources(vault)==0
        failed=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(failure_id,)).fetchone()
        assert failed['publication_state']=='conflict' and failed['wiki_indexed_at'] is None, {key:failed[key] for key in ('publication_state','publication_error','wiki_indexed_at')}

        # A human edit arriving while the provider runs is retained; no summary
        # is committed for a different destination or source revision.
        config={'enabled':True,'provider':'ollama','model':'fixture'}
        summary={'summary':'A supported fixture summary with enough detail.','key_points':[],'concepts':[],'entities':[]}
        source_record=vault/record['wiki_source_path']
        initial=source_record.read_bytes()
        with patch('app.ai_provider.settings',return_value={'enabled':False}),patch.object(wiki,'ollama_chat') as provider:
            assert not wiki.synthesize_one(vault);provider.assert_not_called()
        db.execute("INSERT INTO library_documents(path,title,origin,kind,fingerprint,source_id,evidence_scope) VALUES (%s,'Fixture','archive','raw_source','fixture',%s,'archive') ON CONFLICT(path) DO UPDATE SET source_id=excluded.source_id",(record['note_path'],valid_id))
        db.execute("INSERT INTO library_overrides(path,excluded) VALUES (%s,true) ON CONFLICT(path) DO UPDATE SET excluded=true",(record['note_path'],))
        # Even an old row labelled as published cannot confer outbound consent
        # on a path registered as imported personal content.
        db.execute("UPDATE page_captures SET publication_state='succeeded',wiki_indexed_at=now() WHERE url_hash=%s",(imported_id,))
        with patch('app.ai_provider.settings',return_value=config),patch.object(wiki,'ollama_chat') as provider:
            assert not wiki.synthesize_one(vault);provider.assert_not_called()
        db.execute("UPDATE page_captures SET publication_state='protected',wiki_indexed_at=NULL WHERE url_hash=%s",(imported_id,))
        db.execute('UPDATE library_overrides SET excluded=false WHERE path=%s',(record['note_path'],))
        def human_edit(messages,schema):
            source_record.write_bytes(initial+b'Human change during inference\n')
            return json.dumps(summary)
        with patch('app.ai_provider.settings',return_value=config),patch.object(wiki,'ollama_chat',human_edit):
            assert wiki.synthesize_one(vault)
        state=db.execute('SELECT ai_state,publication_state,summary_source_hash FROM page_captures WHERE url_hash=%s',(valid_id,)).fetchone()
        assert state['ai_state']=='retry' and state['publication_state']=='conflict' and state['summary_source_hash']=='',state
        assert source_record.read_bytes()==initial+b'Human change during inference\n'

        success_id=source_id(103)
        success_relative='Forgetful Me/Pages/'+success_id+'.md'
        success_capture=vault/success_relative;success_capture.write_text(captured('Current synthesis source evidence. '*30))
        success_hash=page_scraper.capture_hash(success_capture.read_text())
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,fetched_at,capture_content_hash) VALUES (%s,'https://example.invalid/success','complete',%s,now(),%s)",(success_id,success_relative,success_hash))
        assert wiki.refresh_sources(vault)==1
        with patch('app.ai_provider.settings',return_value=config),patch.object(wiki,'ollama_chat',return_value=json.dumps(summary)):
            assert wiki.synthesize_one(vault)
        succeeded=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(success_id,)).fetchone()
        assert succeeded['ai_state']=='complete' and succeeded['summary_source_hash']==success_hash
        assert summary['summary'] in (vault/succeeded['wiki_source_path']).read_text()
print('Deferred missing jobs, truthful publication completion, reviewed preservation and inference-time conflicts passed')

with tempfile.TemporaryDirectory(dir='/vault') as temporary,connect() as db:
    root=Path(temporary)
    relative=str((root/'capture.md').relative_to('/vault'))
    target=Path('/vault')/relative
    original_body='Original source evidence. '*30
    changed_body='Revised source evidence. '*30
    target.write_text(captured(original_body))
    old_hash=page_scraper.capture_hash(target.read_text())
    identity=source_id(200)
    @contextlib.contextmanager
    def same_connection():yield db
    def revision_claim(connection):
        return connection.execute("SELECT * FROM page_captures WHERE state='pending' ORDER BY url_hash LIMIT 1").fetchone()
    with db.transaction(force_rollback=True),patch.object(page_scraper,'connect',same_connection),patch('app.ingestion_policy.claim_capture',side_effect=revision_claim):
        db.execute('DELETE FROM page_captures')
        db.execute("INSERT INTO page_captures(url_hash,url,state,note_path,capture_content_hash,summary_source_hash,ai_state,ai_attempts,wiki_data,publication_state,wiki_indexed_at) VALUES (%s,'https://example.invalid/recapture','pending',%s,%s,%s,'complete',2,%s::jsonb,'succeeded',now())",(identity,relative,old_hash,old_hash,json.dumps({'title':'Fixture','summary':'Old summary belongs to original content'})))
        def unchanged(url,digest):
            target.write_text(captured(original_body,'new timestamp'));return relative,url,'Fixture'
        with patch.object(page_scraper,'scrape_page',unchanged):assert page_scraper.process_page()
        row=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()
        assert row['ai_state']=='complete' and row['wiki_data']['summary'] and row['summary_source_hash']==old_hash
        assert row['publication_state']=='succeeded' and row['wiki_indexed_at'] is not None
        db.execute("UPDATE page_captures SET state='pending' WHERE url_hash=%s",(identity,))
        def changed(url,digest):
            target.write_text(captured(changed_body));return relative,url,'Fixture'
        with patch.object(page_scraper,'scrape_page',changed):assert page_scraper.process_page()
        row=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()
        assert row['ai_state']=='pending' and row['ai_attempts']==0 and 'summary' not in row['wiki_data']
        assert row['capture_content_hash']!=old_hash and row['summary_source_hash']==''
        assert row['publication_state']=='pending' and row['wiki_indexed_at'] is None
print('Unchanged recapture avoids redundant summaries; changed content invalidates the old summary and queues publication passed')
