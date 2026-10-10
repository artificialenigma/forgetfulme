"""Isolated FM-05 parser/jobs/page-citation regressions; preserves PDF originals."""
import hashlib
import io
import json
import re
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject
from app.db import connect, require_isolated_test
from app import library, pdf_extract, wiki

require_isolated_test()


def pdf_fixture(texts=None, scanned=False, encrypted=False):
    writer=PdfWriter()
    for content in texts or ['']:
        page=writer.add_blank_page(width=612,height=792)
        if scanned:
            image=DecodedStreamObject();image.set_data(bytes([255,255,255]))
            image.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),
                NameObject('/Width'):NumberObject(1),NameObject('/Height'):NumberObject(1),
                NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im0'):writer._add_object(image)})})
            stream=DecodedStreamObject();stream.set_data(b'q 100 0 0 100 50 50 cm /Im0 Do Q')
            page[NameObject('/Contents')]=writer._add_object(stream)
        elif content:
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 50 700 Td ('+content.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode())
            page[NameObject('/Contents')]=writer._add_object(stream)
    if encrypted:writer.encrypt('fixture-secret')
    output=io.BytesIO();writer.write(output)
    return output.getvalue()


def execute(sql,params=(),all=False):
    with connect() as db:
        result=db.execute(sql,params)
        return result.fetchall() if all else result.fetchone() if result.description else None


def job(identity,revision):
    return execute('SELECT * FROM library_pdf_jobs WHERE document_id=%s AND revision=%s',(identity,revision))


text_pdf=pdf_fixture(['FM05PAGEONE reliable planet evidence','FM05PAGETWO reliable moon evidence'])
original_digest=hashlib.sha256(text_pdf).hexdigest()
parsed=pdf_extract.extract_bytes(text_pdf)
assert parsed['state']=='succeeded',parsed
assert parsed['pages_total']==2 and parsed['pages_with_text']==2
assert parsed['pages'][1]['page']==2 and 'FM05PAGETWO' in parsed['pages'][1]['text']
assert hashlib.sha256(text_pdf).hexdigest()==original_digest
assert pdf_extract.extract_bytes(b'<html>Not a PDF</html>')['state']=='not_pdf'
assert pdf_extract.extract_bytes(b'%PDF-1.7\ncorrupt\n%%EOF')['state']=='corrupt'
assert pdf_extract.extract_bytes(pdf_fixture(scanned=True))['state']=='ocr_required'
assert pdf_extract.extract_bytes(pdf_fixture(['Secret'],encrypted=True))['state']=='encrypted'
for limits in ({'max_bytes':len(text_pdf)-1},{'max_pages':1},{'max_text':5},{'max_stream':32},{'wall':0.0001},{'memory':16*1024*1024}):
    result=pdf_extract.extract_bytes(text_pdf,limits)
    assert result['state']=='budget_exceeded',(limits,result)
for invalid in ({'max_pages':pdf_extract.MAX_PAGES+1},{'cpu':0},{'memory':-1},{'wall':float('nan')},{'unknown':1}):
    try:pdf_extract.extract_bytes(text_pdf,invalid);raise AssertionError('Invalid/expanded limit accepted')
    except ValueError:pass
print('PASS: isolated PDF child text/page extraction, scanned/encrypted/corrupt/signature states, byte/page/text/stream/time/memory budgets')

with connect() as db:db.execute(pdf_extract.PDF_SCHEMA)
with tempfile.TemporaryDirectory() as temporary:
    vault=Path(temporary);relative='Forgetful Me/Imported PDF fixture.pdf'
    source=vault/relative;source.parent.mkdir(parents=True);source.write_bytes(text_pdf)
    assert library.scan(vault)>=1
    document=next(row for row in library.documents() if row['path']==relative)
    identity=document['document_id'];revision=document['content_hash']
    assert revision==original_digest and document['evidence_scope']=='imported'
    assert not library.search('FM05PAGETWO',for_ai=True)
    assert not job(identity,revision)  # Imports never implicitly select extraction.
    job_id=pdf_extract.queue(identity,vault=vault)
    assert job(identity,revision)['state']=='pending'
    assert pdf_extract.process_one(vault)
    assert job(identity,revision)['state']=='succeeded'
    pages=execute('SELECT * FROM library_pdf_pages WHERE document_id=%s AND revision=%s ORDER BY page',(identity,revision),all=True)
    assert len(pages)==2 and pages[1]['page']==2 and 'FM05PAGETWO' in pages[1]['text']
    assert source.read_bytes()==text_pdf
    library.scan(vault)
    hits=library.search('FM05PAGETWO',scope='all',for_ai=True)
    assert hits and hits[0]['page_number']==2 and hits[0]['document_id']==identity
    assert hits[0]['content_hash']==revision and hits[0]['path']==relative
    assert not library.search('FM05PAGETWO',scope='archive',for_ai=True)
    # Parent exclusions and disabling extraction reject already-indexed PDF text immediately.
    execute('INSERT INTO library_overrides(path,excluded) VALUES (%s,true)',(relative,))
    assert not library.search('FM05PAGETWO',for_ai=True)
    execute('UPDATE library_overrides SET excluded=false WHERE path=%s',(relative,))
    pdf_extract.disable(identity)
    assert not library.search('FM05PAGETWO',for_ai=True)
    assert source.read_bytes()==text_pdf
    pdf_extract.queue(identity,vault=vault);library.scan(vault)
    assert job(identity,revision)['id']==job_id and job(identity,revision)['attempts']==1
    assert library.search('FM05PAGETWO',for_ai=True)
    assert execute('SELECT text_hash FROM library_pdf_pages WHERE document_id=%s AND revision=%s ORDER BY page',(identity,revision),all=True)==[{'text_hash':page['text_hash']} for page in pages]
    # Requested AI receives only allowed page text and saves the correct page/revision citation.
    execute("UPDATE wiki_questions SET state='failed' WHERE state='pending'")
    question=uuid.uuid4();execute("INSERT INTO wiki_questions(id,question,scope) VALUES (%s,'FM05PAGETWO','all')",(question,))
    def fake_chat(messages,schema):
        content=messages[-1]['content']
        assert 'FM05PAGETWO' in content and 'PAGE: 2' in content
        ids=re.findall(r'SOURCE ID: (chunk-\d+)',content)
        return json.dumps({'answer':'Fixture moon evidence from PDF page two','source_ids':ids[:1]})
    with patch('app.ai_provider.settings',return_value={'enabled':True}),patch.object(wiki,'ollama_chat',fake_chat):
        assert wiki.answer_one(vault)
    answer=execute('SELECT * FROM wiki_questions WHERE id=%s',(question,))
    assert answer['state']=='complete',answer['error']
    citation=answer['citations'][0]
    assert citation['page_number']==2 and citation['revision']==revision and citation['document_id']==str(identity)
    assert 'FM05PAGETWO' in citation['excerpt']
    # Selected source updates create a new extraction revision, preserving old page text.
    updated=pdf_fixture(['FM05NEWONE new evidence','FM05NEWTWO changed evidence']);source.write_bytes(updated)
    library.scan(vault)
    new_revision=hashlib.sha256(updated).hexdigest()
    assert new_revision!=revision and not library.search('FM05PAGETWO',for_ai=True)
    assert job(identity,new_revision)['state']=='pending'
    assert pdf_extract.process_one(vault);library.scan(vault)
    assert library.search('FM05NEWTWO',for_ai=True)[0]['page_number']==2
    assert source.read_bytes()==updated
    assert execute('SELECT text_hash FROM library_pdf_pages WHERE document_id=%s AND revision=%s ORDER BY page',(identity,revision),all=True)==[{'text_hash':page['text_hash']} for page in pages]
    assert execute('SELECT citations FROM wiki_questions WHERE id=%s',(question,))['citations']==answer['citations']
    # Clear asynchronous errors are visible in persisted jobs and preserve every original.
    fixtures=[('scanned.pdf',pdf_fixture(scanned=True),'ocr_required'),('encrypted.pdf',pdf_fixture(['Secret'],encrypted=True),'encrypted'),
              ('corrupt.pdf',b'%PDF-1.7\ncorrupt\n%%EOF','corrupt'),('html.pdf',b'<html>Not a PDF</html>','not_pdf')]
    for filename,data,expected in fixtures:
        file=vault/filename;file.write_bytes(data);library.scan(vault)
        row=next(row for row in library.documents() if row['path']==filename)
        pdf_extract.queue(row['document_id'],vault=vault)
        assert pdf_extract.process_one(vault)
        state=job(row['document_id'],row['content_hash'])
        assert state['state']==expected and state['error'],state
        assert file.read_bytes()==data
    # A disable saved while the parser is running cancels publication.
    cancelling=pdf_fixture(['FM05CANCEL selected evidence']);source.write_bytes(cancelling);library.scan(vault)
    cancelling_revision=hashlib.sha256(cancelling).hexdigest()
    def disable_during_parse(data):
        pdf_extract.disable(identity)
        return parsed
    with patch.object(pdf_extract,'extract_bytes',disable_during_parse):assert pdf_extract.process_one(vault)
    assert job(identity,cancelling_revision)['state']=='cancelled'
    assert not execute('SELECT page FROM library_pdf_pages WHERE document_id=%s AND revision=%s',(identity,cancelling_revision))
    assert source.read_bytes()==cancelling
print('PASS: selected-only asynchronous extraction, exact PDF revision/page citations, imported scope/exclusions, cancellation, immutable page history and original preservation')
