"""Real isolated DB regressions for scopes, exclusions, IDs and retained evidence."""
import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
from starlette.requests import Request
from app.db import connect, require_isolated_test
from app import library, wiki, library_index
from app.library_identity import rename_note, question_id
from app.library_routes import show_citation

require_isolated_test()
MARKER='PRIVATE_FIXTURE_92386'


def execute(sql, params=(), all=False):
    with connect() as db:
        result=db.execute(sql,params)
        return result.fetchall() if all else result.fetchone() if result.description else None


def queue(question, scope):
    identity=uuid.uuid4()
    execute('INSERT INTO wiki_questions(id,question,scope) VALUES (%s,%s,%s)',(identity,question,scope))
    return identity


def request_citation(identity, source):
    from urllib.parse import urlencode
    return Request({'type':'http','method':'GET','path':'/library/citation','query_string':urlencode({'question':identity,'source':source}).encode(),'headers':[]})


with tempfile.TemporaryDirectory() as temporary:
    vault=Path(temporary)
    def write(path,body):
        target=vault/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
        return target
    raw='Forgetful Me/Captured pages/Archive.md';summary='Forgetful Me/wiki/sources/Archive.md'
    capture_id=hashlib.sha256(b'https://example.test/archive').hexdigest()
    write(raw,wiki.note_header('raw_source','Archive',source_id=capture_id)+'# Archive\nArchivefixture verified hardware evidence. '*20)
    write(summary,wiki.note_header('source','Archive',source_id=capture_id)+'# Source\nArchivefixture concise hardware evidence. '*20)
    private='Forgetful Me/personal.md'
    original=write(private,'---\ntitle: Café personal research\naliases: [ދިވެހި, ESP alias]\n---\n# Personal\n'+MARKER+' family planning evidence.\n## Open questions\n- Where is the fixture?\n').read_bytes()
    execute("INSERT INTO page_captures(url_hash,url,state,note_path,wiki_source_path) VALUES (%s,'https://example.test/archive','complete',%s,%s)",(capture_id,raw,summary))
    execute('INSERT INTO library_import_origins(path) VALUES (%s)',(private,))
    execute("UPDATE wiki_questions SET state='failed' WHERE state='pending'")
    assert library.scan(vault)>=3
    rows={r['path']:r for r in library.documents()}
    assert rows[private]['origin']=='imported' and rows[private]['evidence_scope']=='imported'
    assert rows[raw]['evidence_scope']=='archive'
    assert library.search('cafe',for_ai=True) and library.search('café',for_ai=True)
    assert library.search('cafe\u0301',for_ai=True) and library.search('ދިވެހި',for_ai=True)
    assert not library.search(MARKER,scope='archive',for_ai=True)
    all_id=queue(MARKER,'all');seen=[]
    def personal_chat(messages,schema):
        prompt=messages[-1]['content'];seen.append(prompt)
        assert MARKER in prompt
        ids=re.findall(r'SOURCE ID: (chunk-\d+)',prompt)
        return json.dumps({'answer':MARKER+' supported by personal fixture','source_ids':ids[:1]})
    with patch('app.ai_provider.settings',return_value={'enabled':True}),patch.object(wiki,'ollama_chat',personal_chat):
        assert wiki.answer_one(vault)
    answer=execute('SELECT * FROM wiki_questions WHERE id=%s',(all_id,))
    assert answer['state']=='complete',answer['error']
    citation=answer['citations'][0]
    assert citation['excerpt'] and citation['revision'] and citation['document_id']==str(rows[private]['document_id'])
    answer_path=wiki.WIKI+'/queries/'+str(all_id)+'.md'
    metadata,_,_=library.frontmatter((vault/answer_path).read_text())
    assert metadata['evidence_scope']=='all' and metadata['parent_document_ids']==[citation['document_id']]
    library.scan(vault)
    assert any(MARKER in r['content'] for r in library.search(MARKER))  # Local reading is allowed.
    assert all(r['path']!=answer_path for r in library.search(MARKER,for_ai=True))
    archive_id=queue('Archivefixture '+MARKER,'archive')
    def archive_chat(messages,schema):
        prompt=messages[-1]['content']
        # Question itself names the marker; it must not appear in source excerpts.
        assert MARKER not in prompt.split('SOURCE ID:',1)[-1]
        ids=re.findall(r'SOURCE ID: (chunk-\d+)',prompt)
        return json.dumps({'answer':'Supported archive evidence','source_ids':ids[:1]})
    with patch('app.ai_provider.settings',return_value={'enabled':True}),patch.object(wiki,'ollama_chat',archive_chat):
        assert wiki.answer_one(vault)
    assert execute('SELECT state FROM wiki_questions WHERE id=%s',(archive_id,))['state']=='complete'
    # Historical answer with unknown lineage stays out even with forged metadata.
    write(wiki.WIKI+'/queries/legacy.md',wiki.note_header('query','Legacy')+'# Legacy\nLegacyonlymarker')
    # Explicit ZIP provenance outranks a coincidentally matching DB capture path.
    execute('INSERT INTO library_import_origins(path) VALUES (%s)',(summary,))
    library.scan(vault)
    assert not library.search('Legacyonlymarker',for_ai=True)
    assert next(r for r in library.documents() if r['path']==summary)['origin']=='imported'
    # Excluding raw source removes all derivatives without waiting for a scan.
    execute('INSERT INTO library_overrides(path,excluded) VALUES (%s,true)',(raw,))
    assert not library.search('Archivefixture',scope='archive',for_ai=True)
    execute('UPDATE library_overrides SET excluded=false WHERE path=%s',(raw,))
    assert library.search('Archivefixture',scope='archive',for_ai=True)
    # Previously trusted capture revisions retain family lineage after recapture.
    new_raw='Forgetful Me/Captured pages/Archive revision two.md'
    write(new_raw,wiki.note_header('raw_source','Archive revision two',source_id=capture_id)+'# Archive\nArchivefixture newer hardware evidence. '*20)
    execute('UPDATE page_captures SET note_path=%s WHERE url_hash=%s',(new_raw,capture_id))
    library.scan(vault)
    assert next(r for r in library.documents() if r['path']==raw)['source_id']==capture_id
    execute('UPDATE library_overrides SET excluded=true WHERE path=%s',(raw,))
    assert not library.search('Archivefixture',scope='archive',for_ai=True)
    from app.evidence import source_excluded
    with connect() as db:assert source_excluded(db,capture_id)
    execute('UPDATE library_overrides SET excluded=false WHERE path=%s',(raw,))
    old_hits=library.search(MARKER,for_ai=True)
    queued=queue(MARKER,'all')
    execute('INSERT INTO library_overrides(path,excluded) VALUES (%s,true)',(private,))
    # Emulate an exclusion saved after retrieval: prompt-time check must reject stale hits.
    with patch('app.ai_provider.settings',return_value={'enabled':True}),patch.object(library,'search',return_value=old_hits),patch.object(wiki,'ollama_chat') as provider:
        assert wiki.answer_one(vault)
        provider.assert_not_called()
    assert execute('SELECT state FROM wiki_questions WHERE id=%s',(queued,))['state']=='failed'
    execute('UPDATE library_overrides SET excluded=false WHERE path=%s',(private,))
    paused=queue(MARKER,'all')
    with patch('app.ai_provider.settings',return_value={'enabled':False}),patch.object(wiki,'ollama_chat') as provider:
        assert not wiki.answer_one(vault);provider.assert_not_called()
    assert execute('SELECT state FROM wiki_questions WHERE id=%s',(paused,))['state']=='pending'
    with patch('app.ai_provider.settings',side_effect=[{'enabled':True},{'enabled':False}]),patch.object(wiki,'ollama_chat') as provider:
        assert not wiki.answer_one(vault);provider.assert_not_called()
    execute("UPDATE wiki_questions SET state='failed' WHERE id=%s",(paused,))
    # Real provider diagnostics use only their synthetic prompt while paused.
    execute("UPDATE ai_settings SET enabled=false,test_state='pending' WHERE id=1")
    from app.ai_provider import test_pending
    def diagnostic(messages,schema,config):
        assert messages==[{'role':'user','content':'Return JSON with ok set to true.'}]
        assert config['enabled'] is True
        return '{"ok":true}'
    with patch('app.ai_provider.chat',side_effect=diagnostic):assert test_pending()
    assert (vault/private).read_bytes()==original
    # Stable preferences, legacy question resolution and connections survive rename.
    document_id=rows[private]['document_id'];question='Where is the fixture?'
    legacy=hashlib.sha256((private+'\0'+question).encode()).hexdigest()
    execute("UPDATE library_overrides SET project='Fixture project',reviewed=true WHERE path=%s",(private,))
    execute("INSERT INTO library_question_status(id,state,answer_path) VALUES (%s,'resolved',%s)",(legacy,private))
    execute('INSERT INTO library_connections(source,target) VALUES (%s,%s)',(private,raw))
    moved='Personal renamed.md'
    assert rename_note(private,moved,vault)==document_id
    assert not (vault/private).exists() and (vault/moved).read_bytes()==original
    assert execute('SELECT project FROM library_overrides WHERE path=%s',(moved,))['project']=='Fixture project'
    status=execute('SELECT * FROM library_question_status WHERE id=%s',(question_id(document_id,question),))
    assert status['state']=='resolved' and status['answer_path']==moved
    assert execute('SELECT source FROM library_connections WHERE target=%s',(raw,))['source']==moved
    assert 'Current catalog revision matches.' in show_citation(request_citation(all_id,citation['id']))
    # Recovery after atomic filesystem rename but before database change.
    new='Recovered personal.md'
    operation=execute('INSERT INTO library_operations(document_id,old_path,new_path,content_hash) VALUES (%s,%s,%s,%s) RETURNING id',(document_id,moved,new,hashlib.sha256(original).hexdigest()))
    from app.file_ops import rename_no_replace
    rename_no_replace(vault/moved,vault/new)
    library.scan(vault)
    assert not (vault/moved).exists() and (vault/new).read_bytes()==original
    assert execute('SELECT state FROM library_operations WHERE id=%s',(operation['id'],))['state']=='complete'
    assert execute('SELECT document_id FROM library_documents WHERE path=%s',(new,))['document_id']==document_id
    # Collision cannot overwrite either independent file.
    collision=write('collision.md','Human-owned destination')
    try:rename_note(new,'collision.md',vault);raise AssertionError('Collision accepted')
    except ValueError:pass
    assert collision.read_text()=='Human-owned destination' and (vault/new).read_bytes()==original
    # Edits/deletion retain exact evidence and indicate a changed/unavailable current file.
    (vault/new).write_text('# Updated\nChanged research evidence')
    library.scan(vault)
    view=show_citation(request_citation(all_id,citation['id']))
    assert MARKER in view and 'Current source has changed.' in view
    (vault/new).unlink();library.scan(vault)
    assert 'Current source is unavailable.' in show_citation(request_citation(all_id,citation['id']))
    assert execute('SELECT citations FROM wiki_questions WHERE id=%s',(all_id,))['citations']==answer['citations']
    # Missing root and unreadable traversal never mark unrelated docs absent.
    present_before={r['path'] for r in library.documents()}
    assert library.scan(vault/'missing')==0
    assert {r['path'] for r in library.documents()}==present_before
    real_walk=os.walk
    def incomplete_walk(root,**options):
        options['onerror'](PermissionError('Fixture unreadable subtree'))
        yield str(root),[],[]
    with patch.object(library_index.os,'walk',incomplete_walk):library.scan(vault)
    assert {r['path'] for r in library.documents()}==present_before
    # Per-file read failure leaves last good chunks and allows unrelated indexing.
    other=write('other.md','# Other\nOtherfixture evidence');library.scan(vault)
    before=execute('SELECT content_hash FROM library_documents WHERE path=%s',(raw,))['content_hash']
    (vault/raw).write_text('# Edited raw\nChanged archivefixture data')
    other.write_text('# Other\nNewotherfixture evidence')
    snapshot=library_index.snapshot
    def fail_one(path,limit):
        if path==vault/raw:raise PermissionError('Fixture read failure')
        return snapshot(path,limit)
    with patch.object(library_index,'snapshot',fail_one):assert library.scan(vault)>=1
    assert execute('SELECT content_hash FROM library_documents WHERE path=%s',(raw,))['content_hash']==before
    assert library.search('Newotherfixture')
    library.scan(vault);assert library.scan(vault)==0
    assert library.scan(vault,force=True)>=len(library.documents())
    # Identical independent documents never merge merely by content hash.
    write('duplicate1.md','# Duplicate\nSame independent content')
    write('duplicate2.md','# Duplicate\nSame independent content')
    library.scan(vault)
    duplicates=execute("SELECT document_id FROM library_documents WHERE path IN ('duplicate1.md','duplicate2.md')",all=True)
    assert len({r['document_id'] for r in duplicates})==2
print('PASS: explicit scopes, imported prefix, derivative suppression, immediate exclusions, paused AI/diagnostics, immutable citation excerpts, rename/recovery/collision, missing/incomplete scans and file-error isolation')
