"""Synthetic journal, no-overwrite and interrupted-publication regressions."""
import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from app.db import connect,require_isolated_test
from app import publication as p
from app.wiki import note_header
require_isolated_test()


def note(value):return note_header('source','Fixture',source_id='a'*64,source_revision='b'*64)+'# Fixture\n\n'+value+'\n'


with tempfile.TemporaryDirectory() as folder:
    vault=Path(folder);target=vault/'generated.md'
    first=p.publish_note(target,note('first'),vault=vault)
    assert first['state']=='published'
    original=target.read_bytes()
    second=p.publish_note(target,note('second'),vault=vault)
    assert second['state']=='published' and second['path']!=first['path']
    assert target.read_bytes()==original
    assert p.publish_note(vault/second['path'],note('second'),vault=vault)['path']==second['path']
    code=note('```yaml\ngenerated_content_hash: a real code line\n```')
    assert 'generated_content_hash: a real code line' in p.signed_content(code)
    assert p.signed_content(p.signed_content(code))==p.signed_content(code)
    # External editor save at the last check cannot be overwritten.
    latest=vault/second['path'];before=latest.read_bytes();real_write=p.immutable_write
    def edit_during_write(path,content):
        latest.write_bytes(before+b'Human edit\n')
        return real_write(path,content)
    with patch.object(p,'immutable_write',edit_during_write):
        conflict=p.publish_note(latest,note('third'),expected_hash=hashlib.sha256(before).hexdigest(),vault=vault)
    assert conflict['state']=='conflict' and latest.read_bytes().endswith(b'Human edit\n')
    assert (vault/conflict['path']).exists()
    assert p.publish_note(latest,note('third'),vault=vault)['state']=='conflict'
    # Both sides of the filesystem/database commit boundary recover idempotently.
    for stage in ('before','after'):
        path=vault/(stage+'.md');real_finish=p.finish
        def interrupted(db,row,root):
            if stage=='after':real_finish(db,row,root)
            raise RuntimeError('Synthetic interrupted transaction')
        try:
            with patch.object(p,'finish',interrupted):p.publish_note(path,note(stage),vault=vault)
        except RuntimeError:pass
        else:raise AssertionError('Crash fixture did not interrupt')
        assert p.recover_publications(vault)==1
        with connect() as db:row=db.execute('SELECT state FROM library_publications WHERE vault_key=%s AND logical_path=%s',(p.vault_key(vault),path.name)).fetchone()
        assert row['state']=='published' and path.exists()
        assert p.recover_publications(vault)==0
    reviewed=vault/'reviewed.md';reviewed.write_text(note('protected').replace('reviewed: false','reviewed: true'))
    saved=reviewed.read_bytes()
    assert p.publish_note(reviewed,note('replacement'),vault=vault)['state']=='conflict'
    assert reviewed.read_bytes()==saved
    linked=vault/'linked.md';linked.symlink_to(reviewed)
    try:p.publish_note(linked,note('replacement'),vault=vault)
    except (OSError,ValueError):pass
    else:raise AssertionError('Symlink was accepted')
    fifo=vault/'fifo.md';os.mkfifo(fifo)
    from app.wiki import atomic_note
    assert not atomic_note(fifo,note('FIFO guard'))
    with connect() as db:db.execute('DELETE FROM library_publications WHERE vault_key=%s',(p.vault_key(vault),))
print('PASS publication: immutable revisions, body fidelity, editor saves, protected files, crash recovery, symlink guards')

# A committed generated file must reconcile a caller crash without repeating AI.
import json
with tempfile.TemporaryDirectory() as folder:
    vault=Path(folder);source=hashlib.sha256(b'publication-reconcile-fixture').hexdigest();revision='c'*64
    with connect() as db:
        db.execute("INSERT INTO page_captures(url_hash,url,state,capture_content_hash) VALUES (%s,'https://example.invalid/reconcile','complete',%s)",(source,revision))
    content=note_header('source','Recovered summary',source_id=source,source_revision=revision,summary_revision=revision)+'# Recovered\nSynthetic summary\n'
    result=p.publish_note(vault/'summary.md',content,vault=vault,context={'title':'Recovered summary','summary':'Synthetic summary'})
    p.apply_publications(vault);p.apply_publications(vault)
    with connect() as db:
        capture=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(source,)).fetchone()
        assert capture['wiki_source_path']==result['path'] and capture['summary_source_hash']==revision and capture['ai_state']=='complete'
        assert capture['wiki_data']['summary']=='Synthetic summary'
        db.execute("UPDATE page_captures SET capture_content_hash=%s,wiki_source_path=NULL,ai_state='pending' WHERE url_hash=%s",('d'*64,source))
        db.execute('UPDATE library_publications SET applied_at=NULL WHERE id=%s',(result['id'],))
    p.apply_publications(vault)
    with connect() as db:
        capture=db.execute('SELECT * FROM page_captures WHERE url_hash=%s',(source,)).fetchone()
        assert not capture['wiki_source_path'] and capture['ai_state']=='pending'
        db.execute('UPDATE page_captures SET capture_content_hash=%s,excluded=true WHERE url_hash=%s',(revision,source))
        db.execute('UPDATE library_publications SET applied_at=NULL WHERE id=%s',(result['id'],))
    p.apply_publications(vault)
    with connect() as db:
        assert not db.execute('SELECT wiki_source_path FROM page_captures WHERE url_hash=%s',(source,)).fetchone()['wiki_source_path']
        db.execute('UPDATE page_captures SET excluded=false WHERE url_hash=%s',(source,))
        db.execute('UPDATE library_publications SET applied_at=NULL WHERE id=%s',(result['id'],))
    (vault/result['path']).write_bytes((vault/result['path']).read_bytes()+b'Human edit\n')
    p.apply_publications(vault)
    with connect() as db:
        assert db.execute('SELECT state FROM library_publications WHERE id=%s',(result['id'],)).fetchone()['state']=='conflict'
        assert not db.execute('SELECT wiki_source_path FROM page_captures WHERE url_hash=%s',(source,)).fetchone()['wiki_source_path']
        db.execute('DELETE FROM library_publications WHERE vault_key=%s',(p.vault_key(vault),))
        db.execute('DELETE FROM page_captures WHERE url_hash=%s',(source,))
print('PASS publication reconciliation: caller crash, idempotence, stale revision, exclusion and post-publication edits')

# Interrupted rename journals retain changed/deleted/nonregular source revisions.
from app.library_identity import recover_operations
from app import library
with tempfile.TemporaryDirectory() as folder:
    vault=Path(folder)
    for label in ('edited','deleted','fifo','moved_edited'):
        source=vault/(label+'.md');destination=vault/(label+'-new.md');source.write_text('# Original\nSynthetic rename source.')
        library.scan(vault)
        before=source.read_bytes()
        with connect() as db:
            document=db.execute('SELECT document_id FROM library_documents WHERE path=%s',(source.name,)).fetchone()['document_id']
            identity=db.execute('INSERT INTO library_operations(document_id,old_path,new_path,content_hash) VALUES (%s,%s,%s,%s) RETURNING id',(document,source.name,destination.name,hashlib.sha256(before).hexdigest())).fetchone()['id']
        if label=='edited':source.write_bytes(before+b'Human edit\n')
        elif label=='deleted':source.unlink()
        else:
            source.unlink()
            if label=='fifo':os.mkfifo(destination)
            else:destination.write_bytes(before+b'Human edit after move\n')
        with connect() as db:recover_operations(db,vault)
        with connect() as db:assert db.execute('SELECT state FROM library_operations WHERE id=%s',(identity,)).fetchone()['state']=='conflict'
        if label=='edited':assert source.read_bytes().endswith(b'Human edit\n')
        if label=='moved_edited':assert destination.read_bytes().endswith(b'Human edit after move\n')
        if label=='fifo':destination.unlink()
print('PASS rename recovery: edited/deleted/FIFO/post-move edits preserve originals and stop unsafe reconciliation')

# A review preference changed at the filesystem boundary must become a conflict.
with tempfile.TemporaryDirectory() as folder:
    vault=Path(folder);target=vault/'review-race.md'
    p.publish_note(target,note('Original review race'),vault=vault);before=target.read_bytes();writer=p.immutable_write
    def review_during_write(path,content):
        writer(path,content)
        with connect() as db:db.execute('INSERT INTO library_overrides(path,reviewed) VALUES (%s,true) ON CONFLICT(path) DO UPDATE SET reviewed=true',(target.name,))
    with patch.object(p,'immutable_write',review_during_write):result=p.publish_note(target,note('Updated review race'),vault=vault)
    assert result['state']=='conflict' and target.read_bytes()==before
    with connect() as db:
        db.execute('DELETE FROM library_overrides WHERE path=%s',(target.name,))
        db.execute('DELETE FROM library_publications WHERE vault_key=%s',(p.vault_key(vault),))
print('PASS publication boundary: concurrent review preference retains prior bytes and visible conflict')
