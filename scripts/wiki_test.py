"""Knowledge note ownership, evidence and citation boundaries."""
import json
import tempfile
from pathlib import Path
from app.wiki import atomic_note, note_header, link, facet_path, validate_answer, retrieval_terms, Synthesis

with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary)/'note.md'
    assert atomic_note(path,note_header('source','Test')+'first')
    assert atomic_note(path,note_header('source','Test')+'second')
    path.write_text(note_header('source','Test',reviewed=True)+'human review')
    assert not atomic_note(path,note_header('source','Test')+'overwrite')
    assert 'human review' in path.read_text()
    path.write_text('User note')
    assert not atomic_note(path,note_header('source','Test')+'overwrite')
assert facet_path('concepts','Docker') == facet_path('concepts',' DOCKER ')
assert '|unsafe link' in link('safe.md','unsafe|[link]')
assert retrieval_terms('What do my sources say about Docker?') == 'docker'
valid=json.dumps({'answer':'Supported answer','source_ids':['known']})
assert validate_answer(valid,{'known'}).answer=='Supported answer'
try:
    validate_answer(valid,{'other'})
    raise AssertionError('Unknown citation was accepted')
except ValueError: pass
try:
    Synthesis.model_validate({'summary':'short','key_points':[],'concepts':[],'entities':[]})
    raise AssertionError('Malformed synthesis was accepted')
except ValueError: pass
print('Wiki ownership, reviewed notes, safe links, retrieval and citation validation passed')
from unittest.mock import MagicMock, patch
from app.wiki import rebuild_indexes, readable_name, source_body
from datetime import datetime, timezone
row={'url_hash':'a'*64,'url':'https://example.com/article','fetched_at':datetime.now(timezone.utc),'ai_state':'pending','wiki_data':{'title':'Readable article','concepts':[{'name':'Docker','description':'Draft','evidence':'Draft evidence quotation'}]}}
assert readable_name('a'*64,'My / article: title').startswith('My article title')
assert 'synthesis is queued' not in source_body(row)
assert '## Concepts' not in source_body(row)
with tempfile.TemporaryDirectory() as temporary:
    db=MagicMock();db.__enter__.return_value=db;db.execute.return_value.fetchall.return_value=[row]
    with patch('app.wiki.connect',return_value=db):assert rebuild_indexes(Path(temporary))==1
    notes=list(Path(temporary).rglob('*.md'))
    assert not any('concepts' in note.parts or 'entities' in note.parts for note in notes)
    assert any('Websites' in note.stem for note in notes)
print('Readable archive filenames, simple indexes and disabled concept/entity expansion passed')
