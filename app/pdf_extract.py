"""Selected local PDFs: bounded child parsing and immutable page extraction.

No source-file writes, OCR, model downloads or external services. The parent
process passes only the selected PDF bytes into a scrubbed subprocess; parsing
never runs inside a web request or the application's database transaction.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 500
MAX_PAGE_STREAM = 8 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_PAGE_TEXT = 250_000
MEMORY_BYTES = 384 * 1024 * 1024
CPU_SECONDS = 20
WALL_SECONDS = 30
MAX_OUTPUT = 10 * 1024 * 1024
EXTRACTOR_VERSION = 'pypdf-6.19.0/text-v1'
STATES = {'pending','running','succeeded','failed','not_pdf','corrupt','encrypted','ocr_required','budget_exceeded','superseded','cancelled'}

PDF_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_pdf_selections (
 document_id uuid PRIMARY KEY REFERENCES library_documents(document_id) ON DELETE CASCADE,
 enabled boolean NOT NULL DEFAULT true, selected_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS library_pdf_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 document_id uuid NOT NULL REFERENCES library_documents(document_id) ON DELETE CASCADE,
 revision text NOT NULL CHECK(revision ~ '^[a-f0-9]{64}$'),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','succeeded','failed','not_pdf','corrupt','encrypted','ocr_required','budget_exceeded','superseded','cancelled')),
 attempts integer NOT NULL DEFAULT 0, pages_total integer NOT NULL DEFAULT 0,
 pages_with_text integer NOT NULL DEFAULT 0, text_chars integer NOT NULL DEFAULT 0,
 extractor_version text NOT NULL, error text,
 created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
 UNIQUE(document_id,revision)
);
CREATE INDEX IF NOT EXISTS library_pdf_pending ON library_pdf_jobs(created_at) WHERE state='pending';
CREATE TABLE IF NOT EXISTS library_pdf_pages (
 document_id uuid NOT NULL REFERENCES library_documents(document_id) ON DELETE CASCADE,
 revision text NOT NULL CHECK(revision ~ '^[a-f0-9]{64}$'), page integer NOT NULL CHECK(page>0),
 text text NOT NULL, text_hash text NOT NULL, words integer NOT NULL,
 extractor_version text NOT NULL,
 PRIMARY KEY(document_id,revision,page)
);
"""


def _result(state, error=None, pages=None, pages_total=0):
    pages = pages or []
    return dict(state=state, error=error, pages=pages, pages_total=pages_total,
                pages_with_text=sum(bool(re.search(r'[^\W_]', page['text'])) for page in pages),
                text_chars=sum(len(page['text']) for page in pages), extractor_version=EXTRACTOR_VERSION)


def _limits(overrides=None):
    defaults = dict(max_bytes=MAX_BYTES, max_pages=MAX_PAGES, max_stream=MAX_PAGE_STREAM,
                    max_text=MAX_TEXT_CHARS, max_page_text=MAX_PAGE_TEXT,
                    memory=MEMORY_BYTES, cpu=CPU_SECONDS, wall=WALL_SECONDS)
    for key, value in (overrides or {}).items():
        if key not in defaults or isinstance(value, bool) or not isinstance(value,(int,float)) or value<=0 or value>defaults[key] or not math.isfinite(value):
            raise ValueError('Extraction limits may only be lowered')
        if key != 'wall' and int(value) != value:
            raise ValueError('Extraction limits must be integer values')
        defaults[key] = value
    return defaults


def _parse_pdf(data, limits):
    # Only invoked in the resource-limited child. pypdf does not render JavaScript,
    # read embedded files or resolve hyperlinks; only page text streams are read.
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import LimitReachedError
    if len(data)>limits['max_bytes']:
        return _result('budget_exceeded','PDF exceeds the file-size extraction limit')
    if not re.match(br'^%PDF-[12]\.\d',data):
        return _result('not_pdf','File does not have a supported PDF signature')
    try:
        with apply_configuration(maximum_declared_stream_length=limits['max_stream'],
                array_based_stream_maximum_output_length=limits['max_stream'],
                zlib_maximum_output_length=limits['max_stream'],
                lzw_maximum_output_length=limits['max_stream'],
                run_length_maximum_output_length=limits['max_stream'],
                jbig2_maximum_output_length=limits['max_stream'],
                image_maximum_buffer_size=limits['max_stream'],
                zlib_maximum_recovery_input_length=min(1_000_000,limits['max_stream']),
                page_tree_maximum_entries=limits['max_pages']*10,page_tree_maximum_depth=32,
                xform_maximum_invocations_per_extraction=500,jbig2dec_binary=None):
            reader=PdfReader(io.BytesIO(data),strict=True,root_object_recovery_limit=2048)
            if reader.is_encrypted:
                return _result('encrypted','Encrypted PDF: unlock a copy before selecting it')
            count=len(reader.pages)
            if not count:
                return _result('corrupt','PDF contains no pages')
            if count>limits['max_pages']:
                return _result('budget_exceeded','PDF exceeds the page-count extraction limit',pages_total=count)
            pages=[];total=0
            for number,page in enumerate(reader.pages,1):
                stream=page.get_contents()
                if stream and len(stream.get_data())>limits['max_stream']:
                    return _result('budget_exceeded','PDF page content exceeds the decoded-stream limit',pages_total=count)
                text=page.extract_text() or ''
                text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','',text).replace('\r\n','\n').replace('\r','\n')
                total+=len(text)
                if len(text)>limits['max_page_text'] or total>limits['max_text']:
                    return _result('budget_exceeded','PDF extracted text exceeds the text-size limit',pages_total=count)
                pages.append(dict(page=number,text=text))
            if not any(re.search(r'[^\W_]',page['text']) for page in pages):
                return _result('ocr_required','No readable text layer; OCR is disabled',pages,count)
            return _result('succeeded',pages=pages,pages_total=count)
    except (MemoryError,LimitReachedError):
        return _result('budget_exceeded','PDF exceeds an extraction resource or stream limit')
    except Exception:
        # Parser diagnostics can include private PDF strings and must not be logged.
        return _result('corrupt','PDF is corrupt or uses unsupported content')


def _child(limits):
    if sys.platform != 'linux':
        return _result('failed','Bounded PDF extraction requires the Linux container runtime')
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(int(limits['memory']),int(limits['memory'])))
    resource.setrlimit(resource.RLIMIT_CPU,(int(limits['cpu']),int(limits['cpu'])))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    # There is no network feature in this parser. Refuse accidental networking
    # from dependencies as well, and the child receives no app credentials.
    import socket
    def no_network(*args,**kwargs):
        raise RuntimeError('PDF parser networking is disabled')
    socket.socket=no_network
    data=sys.stdin.buffer.read(int(limits['max_bytes'])+1)
    return _parse_pdf(data,limits)


def extract_bytes(data, limits=None):
    """Return bounded page results. This subprocess never receives vault paths."""
    limits=_limits(limits)
    if len(data)>limits['max_bytes']:
        return _result('budget_exceeded','PDF exceeds the file-size extraction limit')
    if not re.match(br'^%PDF-[12]\.\d',data):
        return _result('not_pdf','File does not have a supported PDF signature')
    try:
        child=subprocess.Popen([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--child',json.dumps(limits)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env={'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},start_new_session=True)
        try:
            output,_=child.communicate(data,timeout=limits['wall'])
        except subprocess.TimeoutExpired:
            child.kill();child.communicate()
            return _result('budget_exceeded','PDF exceeds the extraction time limit')
        if child.returncode<0 or len(output)>MAX_OUTPUT:
            return _result('budget_exceeded','PDF parser exhausted its resource budget')
        if child.returncode:
            if limits['memory']<MEMORY_BYTES or limits['cpu']<CPU_SECONDS:
                return _result('budget_exceeded','PDF parser terminated under the reduced resource budget')
            return _result('failed','Local PDF parser failed inside resource isolation')
        result=json.loads(output)
        if result.get('state') not in STATES or not isinstance(result.get('pages'),list):
            raise ValueError('Invalid child result')
        if len(result['pages'])>limits['max_pages'] or result.get('text_chars',0)>limits['max_text']:
            raise ValueError('Invalid child budget')
        return result
    except (OSError,ValueError,TypeError):
        return _result('failed','Local PDF parser unavailable or invalid')


def _identity(value):
    return uuid.UUID(str(value))


def _document(db, identity):
    return db.execute('''SELECT d.*,coalesce(o.excluded,false) OR
        EXISTS(SELECT 1 FROM page_captures p WHERE p.url_hash=d.source_id AND p.excluded) OR
        EXISTS(SELECT 1 FROM library_documents sibling JOIN library_overrides so USING(path)
            WHERE d.source_id<>'' AND sibling.source_id=d.source_id AND so.excluded) AS excluded
        FROM library_documents d LEFT JOIN library_overrides o USING(path)
        WHERE d.document_id=%s''',(identity,)).fetchone()


def queue(document_id, retry=False, vault=Path('/vault')):
    """Explicitly select a catalogued revision. Existing source bytes stay intact."""
    from app.db import connect
    from app.library import safe_path
    from app.library_index import snapshot
    identity=_identity(document_id)
    with connect() as db:
        doc=_document(db,identity)
        if not doc or not doc['present'] or Path(doc['path']).suffix.lower()!='.pdf':
            raise ValueError('Choose an indexed PDF')
        if doc['excluded']:
            raise ValueError('Include the PDF in library preferences before selecting extraction')
        data,_=snapshot(safe_path(doc['path'],vault),MAX_BYTES)
        if len(data)>MAX_BYTES:
            raise ValueError('PDF exceeds the 25 MiB extraction limit')
        revision=hashlib.sha256(data).hexdigest()
        if revision!=doc['content_hash']:
            raise ValueError('PDF changed; scan changed notes before selecting extraction')
        db.execute('''INSERT INTO library_pdf_selections(document_id,enabled) VALUES (%s,true)
            ON CONFLICT(document_id) DO UPDATE SET enabled=true,selected_at=now()''',(identity,))
        job=db.execute('''INSERT INTO library_pdf_jobs(document_id,revision,extractor_version) VALUES (%s,%s,%s)
            ON CONFLICT(document_id,revision) DO UPDATE SET
              state=CASE WHEN library_pdf_jobs.state IN ('cancelled','superseded') OR (%s AND library_pdf_jobs.state NOT IN ('running','succeeded')) THEN 'pending' ELSE library_pdf_jobs.state END,
              error=CASE WHEN library_pdf_jobs.state IN ('cancelled','superseded') OR (%s AND library_pdf_jobs.state NOT IN ('running','succeeded')) THEN NULL ELSE library_pdf_jobs.error END
            RETURNING id''',(identity,revision,EXTRACTOR_VERSION,retry,retry)).fetchone()
        db.execute("UPDATE library_documents SET fingerprint='' WHERE document_id=%s",(identity,))
    return job['id']


def disable(document_id):
    """Stop future extraction/retrieval without deleting originals or page history."""
    from app.db import connect
    identity=_identity(document_id)
    with connect() as db:
        document=_document(db,identity)
        if not document or Path(document['path']).suffix.lower()!='.pdf':
            raise ValueError('PDF not indexed')
        db.execute('''UPDATE library_pdf_selections SET enabled=false WHERE document_id=%s''',(identity,))
        db.execute("UPDATE library_pdf_jobs SET state='cancelled',error='PDF extraction disabled',completed_at=now() WHERE document_id=%s AND state IN ('pending','running')",(identity,))
        db.execute("UPDATE library_documents SET fingerprint='' WHERE document_id=%s",(identity,))


def refresh_selected(db):
    """Called after catalog updates; only opted-in, present revisions can queue."""
    db.execute('''INSERT INTO library_pdf_jobs(document_id,revision,extractor_version)
        SELECT d.document_id,d.content_hash,%s FROM library_documents d
        JOIN library_pdf_selections s USING(document_id) LEFT JOIN library_overrides o USING(path)
        WHERE s.enabled AND d.present AND right(lower(d.path),4)='.pdf'
          AND d.content_hash ~ '^[a-f0-9]{64}$' AND NOT coalesce(o.excluded,false)
        ON CONFLICT(document_id,revision) DO NOTHING''',(EXTRACTOR_VERSION,))


def process_one(vault=Path('/vault')):
    """Claim one job, parse outside locks, and publish immutable pages atomically."""
    from app.db import connect
    from app.library import safe_path,word_tokens
    from app.library_index import snapshot,request_scan
    with connect() as db:
        db.execute("UPDATE library_pdf_jobs SET state='failed',error='PDF worker interrupted; retry extraction',completed_at=now() WHERE state='running' AND started_at<now()-interval '2 minutes'")
        db.execute('''UPDATE library_pdf_jobs j SET state='superseded',error='Selected PDF revision changed or became unavailable',completed_at=now()
            WHERE j.state='pending' AND NOT EXISTS(SELECT 1 FROM library_documents d JOIN library_pdf_selections s USING(document_id)
                WHERE d.document_id=j.document_id AND s.enabled AND d.present AND d.content_hash=j.revision)''')
        job=db.execute('''SELECT j.* FROM library_pdf_jobs j JOIN library_pdf_selections s USING(document_id)
            WHERE j.state='pending' AND s.enabled ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1''').fetchone()
        if not job:return False
        doc=_document(db,job['document_id'])
        if not doc or doc['excluded']:
            db.execute("UPDATE library_pdf_jobs SET state='cancelled',error='PDF excluded from processing',completed_at=now() WHERE id=%s",(job['id'],))
            return True
        db.execute("UPDATE library_pdf_jobs SET state='running',attempts=attempts+1,started_at=now(),completed_at=NULL,error=NULL WHERE id=%s",(job['id'],))
    try:
        path=safe_path(doc['path'],vault)
        data,_=snapshot(path,MAX_BYTES)
        if len(data)>MAX_BYTES:
            result=_result('budget_exceeded','PDF exceeds the file-size extraction limit')
        elif hashlib.sha256(data).hexdigest()!=job['revision']:
            result=_result('superseded','Selected PDF revision changed before extraction')
        else:
            result=extract_bytes(data)
            current,_=snapshot(path,MAX_BYTES)
            if hashlib.sha256(current).hexdigest()!=job['revision']:
                result=_result('superseded','Selected PDF revision changed during extraction')
    except (OSError,ValueError):
        result=_result('failed','Selected PDF unavailable or changed; originals preserved')
    with connect() as db:
        current=_document(db,job['document_id'])
        state=db.execute('''SELECT j.state,s.enabled FROM library_pdf_jobs j
            JOIN library_pdf_selections s USING(document_id) WHERE j.id=%s FOR UPDATE OF j''',(job['id'],)).fetchone()
        if not state or state['state']!='running':return True
        if not state['enabled'] or not current or not current['present'] or current['excluded']:
            result=_result('cancelled','PDF selection disabled, excluded or unavailable')
        elif current['content_hash']!=job['revision']:
            result=_result('superseded','Selected PDF revision changed during extraction')
        if result['state'] in {'succeeded','ocr_required'}:
            for page in result['pages']:
                text_hash=hashlib.sha256(page['text'].encode()).hexdigest()
                db.execute('''INSERT INTO library_pdf_pages(document_id,revision,page,text,text_hash,words,extractor_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(document_id,revision,page) DO NOTHING''',
                    (job['document_id'],job['revision'],page['page'],page['text'],text_hash,len(word_tokens(page['text'])),EXTRACTOR_VERSION))
        db.execute('''UPDATE library_pdf_jobs SET state=%s,error=%s,pages_total=%s,pages_with_text=%s,text_chars=%s,completed_at=now() WHERE id=%s''',
            (result['state'],result['error'],result['pages_total'],result['pages_with_text'],result['text_chars'],job['id']))
        db.execute("UPDATE library_documents SET fingerprint='' WHERE document_id=%s",(job['document_id'],))
    request_scan('incremental')
    return True


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--child':
        raise SystemExit('PDF extraction is managed by the local worker')
    try:
        result=_child(_limits(json.loads(sys.argv[2])))
        sys.stdout.write(json.dumps(result,ensure_ascii=False))
    except MemoryError:
        sys.stdout.write('{"state":"budget_exceeded","error":"PDF exceeds extraction memory limit","pages":[],"pages_total":0,"pages_with_text":0,"text_chars":0}')
