"""Local section retrieval, import fidelity, diagnostics and source preservation."""
import contextlib
import io
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from app import library
from app.vault_import import import_zip
from app.db import require_isolated_test

require_isolated_test()

assert library.open_questions('## Open questions\n- First question with\n  a continuation?\n- Second question?\n')==['First question with a continuation?','Second question?']
assert 'ދިވެހި' in library.tokens('ދިވެހި café')
assert library.repaired_name('TryHackMe ΓÇö KAPE.md')=='TryHackMe — KAPE.md'
meta,body,first=library.frontmatter('---\ntitle: "Test"\ntags:\n  - esp32\n  - iot\nreviewed: true\n---\n# Late\n')
assert meta['tags']==['esp32','iot'] and meta['reviewed'] is True and first==8
assert library.capture_problem('https://accounts.google.com/signin','Sign in','x'*100)
assert not library.capture_problem('https://example.com/article','Article','This is meaningful readable content on a useful topic. '*20)
long='# Intro\n'+('irrelevant paragraph\n'*1400)+'## Relevant late section\nUnique evidence for café and ދިވެހި.\n'
parts=library.chunks(long)
assert any('Unique evidence' in c['content'] and c['start_line']>1400 for c in parts)
assert all(len(c['content'])<5500 for c in parts)
assert 'Unique evidence' in library.summary_excerpt(long)
assert len(library.summary_excerpt(long))<=18000
assert not any('BASE64SECRET' in c['content'] for c in library.chunks('![](data:image/png;base64,BASE64SECRET)\nUseful evidence'))
assert library.resolve_link('wiki/concepts/test.md','sources/a',{'wiki/sources/a.md','raw/a.md'})==['wiki/sources/a.md']
with tempfile.TemporaryDirectory() as temp:
    v=Path(temp);(v/'link').symlink_to('/tmp')
    for p in ('../private','.obsidian/config','link/secret'):
        try:library.safe_path(p,v);raise AssertionError('Unsafe path accepted')
        except ValueError:pass
    # Simulate a legacy ZIP containing UTF-8 name bytes without UTF-8 flag.
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:archive.writestr('Vault/Développement — test.md','# Unicode note')
    data=bytearray(output.getvalue())
    for sig,offset in [(b'PK\x03\x04',6),(b'PK\x01\x02',8)]:
        loc=data.index(sig);flags=struct.unpack_from('<H',data,loc+offset)[0];struct.pack_into('<H',data,loc+offset,flags & ~0x800)
    assert import_zip(bytes(data),v)==(1,0)
    assert (v/'Développement — test.md').read_text()=='# Unicode note'
print('Unicode imports, safe paths, chunk coverage and capture-quality checks passed')

# Exercise actual PostgreSQL ranking and incremental indexing in a rolled-back transaction.
from app.db import connect
with tempfile.TemporaryDirectory() as temp,connect() as db:
    v=Path(temp);(v/'wiki').mkdir();(v/'wiki/a.md').write_text('---\ntitle: "Café research"\ntags: [esp32, iot]\n---\n'+long)
    (v/'wiki/b.md').write_text('---\ntitle: "Other research"\ntags: [esp32, iot]\n---\n# Source\n'+('Useful hardware evidence. '*30))
    (v/'bad.pdf').write_text('<html>blocked</html>')
    original=(v/'wiki/a.md').read_bytes()
    @contextlib.contextmanager
    def same_connection():yield db
    with db.transaction(force_rollback=True),patch.object(library,'connect',same_connection):
        assert library.scan(v)==3
        hits=library.search('ދިވެހި café')
        assert any(h['start_line']>1400 and 'Unique evidence' in h['content'] for h in hits)
        assert library.search('café',scope='archive')==[]
        rows=library.documents();assert any(i['kind']=='capture' and i['path']=='bad.pdf' for i in library.health(rows))
        assert library.suggestions('wiki/a.md',rows)[0]['path']=='wiki/b.md'
        db.execute("INSERT INTO library_overrides(path,excluded) VALUES ('wiki/a.md',true) ON CONFLICT(path) DO UPDATE SET excluded=true")
        assert library.search('café')==[]
        db.execute("UPDATE library_overrides SET excluded=false WHERE path='wiki/a.md'")
        db.execute("UPDATE wiki_questions SET state='failed' WHERE state='pending'")
        import uuid,re
        from app import wiki
        question_id=uuid.uuid4()
        db.execute("INSERT INTO wiki_questions(id,question,scope) VALUES (%s,'Unique evidence café','all')",(question_id,))
        def fake_chat(messages,schema):
            evidence=messages[-1]['content']
            assert 'Unique evidence' in evidence and 'LINES:' in evidence
            ids=re.findall(r'SOURCE ID: (chunk-\d+)',evidence)
            return json.dumps({'answer':'Supported fixture answer','source_ids':ids[:1]})
        with patch.object(wiki,'connect',same_connection),patch.object(wiki,'ollama_chat',fake_chat),patch('app.ai_provider.settings',return_value={'enabled':True}):
            assert wiki.answer_one(v)
        answer=db.execute('SELECT state,citations FROM wiki_questions WHERE id=%s',(question_id,)).fetchone()
        assert answer['state']=='complete' and answer['citations'][0]['path']=='wiki/a.md'
        assert answer['citations'][0]['start_line']>1400
        assert library.scan(v)==1
        assert library.scan(v)==0
        assert (v/'wiki/a.md').read_bytes()==original
print('PostgreSQL Unicode retrieval, late evidence, exclusion, suggestions, incremental index and source preservation passed')
