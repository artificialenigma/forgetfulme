"""Incremental catalog jobs with complete-traversal deletion and snapshot reads."""
import hashlib
import json
import os
import stat as file_stat
from pathlib import Path
from app.db import connect
from app.evidence import classify
from app.library_identity import move_catalog, recover_operations, migrate_questions


def snapshot(path, limit):
    for _ in range(3):
        # Anchor every parent directory and refuse links at open time, so a
        # concurrent symlink replacement cannot redirect the read outside vault.
        parts=path.absolute().parts
        parent=os.open(parts[0],os.O_RDONLY|os.O_DIRECTORY)
        try:
            for component in parts[1:-1]:
                child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
                os.close(parent);parent=child
            fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            with os.fdopen(fd,'rb') as source:
                before=os.fstat(source.fileno())
                if not file_stat.S_ISREG(before.st_mode):raise OSError('Regular source file required')
                data=source.read(limit+1)
                after=os.fstat(source.fileno())
                current=os.stat(parts[-1],dir_fd=parent,follow_symlinks=False)
        finally:
            os.close(parent)
        key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
        if key(before)==key(after)==key(current):
            return data,after
    raise OSError('Concurrent file change')


def request_scan(mode='incremental', db_connect=connect):
    if mode not in {'incremental','full'}:
        raise ValueError('Unknown index mode')
    with db_connect() as db:
        if not db.execute("SELECT id FROM library_index_jobs WHERE mode=%s AND state='queued'",(mode,)).fetchone():
            db.execute('INSERT INTO library_index_jobs(mode) VALUES (%s)',(mode,))


def progress(job, seen, changed, failed, db_connect=connect):
    # Independent transaction: progress/heartbeat survives a failed catalog scan.
    with db_connect() as db:
        db.execute('UPDATE library_index_jobs SET seen=%s,changed=%s,failed=%s WHERE id=%s',(seen,changed,failed,job))
        db.execute("INSERT INTO service_status(service) VALUES ('library-worker') ON CONFLICT(service) DO UPDATE SET last_seen=now()")


def scan(vault=Path('/vault'), force=False, db_connect=connect):
    from app import library
    with db_connect() as db:
        job=db.execute("SELECT * FROM library_index_jobs WHERE state='queued' ORDER BY (mode='full') DESC,id LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
        if not job:
            job=db.execute('INSERT INTO library_index_jobs(mode) VALUES (%s) RETURNING *',('full' if force else 'incremental',)).fetchone()
        db.execute("UPDATE library_index_jobs SET state='running',started_at=now() WHERE id=%s",(job['id'],))
    force=force or job['mode']=='full'
    seen=[];changed=failed=0
    try:
        if not vault.is_dir() or vault.is_symlink() or (vault==Path('/vault') and not os.path.ismount(vault)):
            raise OSError('Vault unavailable')
        root_stat=vault.stat()
        with db_connect() as db:
            if not db.execute('SELECT pg_try_advisory_xact_lock(418245) AS locked').fetchone()['locked']:
                raise OSError('Index already running')
            db.execute("UPDATE library_index_jobs SET state='failed',error='Worker interrupted; scan will be retried',completed_at=now() WHERE state='running' AND id<>%s",(job['id'],))
            recover_operations(db,vault)
            existing={r['path']:r for r in db.execute('SELECT * FROM library_documents').fetchall()}
            imported={r['path'] for r in db.execute('SELECT path FROM library_import_origins').fetchall()}
            sources={}
            captures=db.execute('SELECT url_hash,note_path,wiki_source_path FROM page_captures').fetchall()
            known_sources={r['url_hash'] for r in captures}
            # Keep previously established lineage for immutable older captures.
            # Content/header claims alone never establish it; ZIP provenance
            # still overrides these trusted catalog records in classify().
            sources.update({p:r['source_id'] for p,r in existing.items() if r['source_id'] in known_sources and r['evidence_scope']=='archive'})
            for row in captures:
                for path in (row['note_path'],row['wiki_source_path']):
                    if path:sources[path]=row['url_hash']
            traversal_errors=[]
            for root,dirs,files in os.walk(vault,followlinks=False,onerror=traversal_errors.append):
                dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(root)/d).is_symlink()]
                for name in sorted(files):
                    target=Path(root)/name
                    if name.startswith('.') or target.is_symlink() or target.suffix.lower() not in ('.md','.pdf'):
                        continue
                    relative=str(target.relative_to(vault));seen.append(relative)
                    try:
                        with db.transaction():
                            stat=target.stat();fingerprint=f'{library.INDEX_VERSION}:{stat.st_mtime_ns}:{stat.st_size}'
                            old=existing.get(relative)
                            if not force and old and old['present'] and old['fingerprint']==fingerprint:
                                origin,scope,identity=classify(relative,{'type':old['kind'],'managed_by':old['metadata'].get('managed_by'),'source_id':old['metadata'].get('source_id')},sources,imported)
                                if (old['origin'],old['evidence_scope'],old['source_id'])!=(origin,scope,identity):
                                    db.execute('UPDATE library_documents SET origin=%s,evidence_scope=%s,source_id=%s WHERE path=%s',(origin,scope,identity,relative))
                                    changed+=1
                                continue
                            from app.pdf_extract import MAX_BYTES
                            is_pdf=target.suffix.lower()=='.pdf'
                            limit=MAX_BYTES if is_pdf else library.MAX_NOTE
                            data,stat=snapshot(target,limit)
                            fingerprint=f'{library.INDEX_VERSION}:{stat.st_mtime_ns}:{stat.st_size}'
                            file_key=f'{stat.st_dev}:{stat.st_ino}'
                            digest=hashlib.sha256(data).hexdigest() if len(data)<=limit else ''
                            if not old:
                                candidates=[r for p,r in existing.items() if r['file_key']==file_key and digest and r['content_hash']==digest and not (vault/p).exists()]
                                if len(candidates)==1:
                                    old=candidates[0];migrate_questions(db,old)
                                    move_catalog(db,old['path'],relative)
                                    imported.discard(old['path'])
                                    if db.execute('SELECT path FROM library_import_origins WHERE path=%s',(relative,)).fetchone():imported.add(relative)
                                    if old['path'] in sources:sources[relative]=sources.pop(old['path'])
                            if is_pdf or len(data)>library.MAX_NOTE:
                                issues=[]
                                if len(data)>limit:issues.append(dict(kind='size',detail=f'File exceeds {limit//(1024*1024)} MiB indexing limit'))
                                elif not data.startswith(b'%PDF-'):issues.append(dict(kind='capture',detail='PDF filename contains non-PDF data; recapture original document'))
                                doc=dict(path=relative,title=target.stem,origin='imported',kind='attachment' if target.suffix.lower()=='.pdf' else 'note',tags=[],project='',source_url='',reviewed=False,words=0,metadata={'issues':issues,'questions':[],'links':[]},searchable=False,chunks=[])
                                meta={}
                            else:
                                text=data.decode('utf-8',errors='replace');meta,_,_=library.frontmatter(text)
                                doc=library.inspect_note(relative,text)
                                if '\ufffd' in text:doc['metadata']['issues'].append(dict(kind='encoding',detail='Invalid UTF-8 content; review original file'))
                            if old:migrate_questions(db,old)
                            origin,scope,source_id=classify(relative,meta,sources,imported)
                            doc['origin']=origin
                            if origin=='archive' and doc['kind'] in ('source','raw_source'):
                                _,body,_=library.frontmatter(data.decode('utf-8',errors='replace'))
                                problem=library.capture_problem(doc['source_url'],doc['title'],body)
                                if problem:
                                    doc['metadata']['issues'].append(dict(kind='capture',detail=problem));doc['searchable']=False
                            aliases=meta.get('aliases',[])
                            if isinstance(aliases,str):aliases=[aliases]
                            if not isinstance(aliases,list):aliases=[]
                            match_title=library.normalize_match_text(doc['title']+' '+' '.join(x for x in aliases if isinstance(x,str)))
                            db.execute('''INSERT INTO library_documents(path,title,origin,kind,tags,project,source_url,reviewed,words,metadata,searchable,fingerprint,content_hash,file_key,evidence_scope,source_id,index_version,match_title)
                                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT(path) DO UPDATE SET title=excluded.title,origin=excluded.origin,kind=excluded.kind,tags=excluded.tags,project=excluded.project,source_url=excluded.source_url,reviewed=excluded.reviewed,words=excluded.words,metadata=excluded.metadata,searchable=excluded.searchable,fingerprint=excluded.fingerprint,content_hash=excluded.content_hash,file_key=excluded.file_key,evidence_scope=excluded.evidence_scope,source_id=excluded.source_id,index_version=excluded.index_version,match_title=excluded.match_title,present=true,indexed_at=now()''',
                                tuple(doc[k] if k not in ('tags','metadata') else json.dumps(doc[k],ensure_ascii=False) for k in ('path','title','origin','kind','tags','project','source_url','reviewed','words','metadata','searchable'))+(fingerprint,digest,file_key,scope,source_id,library.INDEX_VERSION,match_title))
                            identity=db.execute('SELECT document_id FROM library_documents WHERE path=%s',(relative,)).fetchone()['document_id']
                            if is_pdf:
                                pdf_job=db.execute('''SELECT j.*,s.enabled FROM library_pdf_jobs j
                                    JOIN library_pdf_selections s USING(document_id)
                                    WHERE j.document_id=%s AND j.revision=%s''',(identity,digest)).fetchone()
                                if pdf_job:
                                    doc['metadata']['pdf_state']=pdf_job['state']
                                    doc['metadata']['extractor_version']=pdf_job['extractor_version']
                                    if pdf_job['error']:doc['metadata']['issues'].append(dict(kind='pdf',detail=pdf_job['error']))
                                    if pdf_job['enabled'] and pdf_job['state']=='succeeded':
                                        pages=db.execute('SELECT * FROM library_pdf_pages WHERE document_id=%s AND revision=%s ORDER BY page',(identity,digest)).fetchall()
                                        for page in pages:
                                            for chunk in library.chunks(page['text']):
                                                chunk.update(heading='Page '+str(page['page']),page_number=page['page'])
                                                doc['chunks'].append(chunk)
                                        doc['words']=sum(page['words'] for page in pages)
                                        doc['searchable']=bool(doc['chunks'])
                                db.execute('UPDATE library_documents SET metadata=%s::jsonb,words=%s,searchable=%s WHERE path=%s',
                                    (json.dumps(doc['metadata']),doc['words'],doc['searchable'],relative))
                            db.execute('''INSERT INTO library_path_history(document_id,path) VALUES (%s,%s)
                                ON CONFLICT(document_id,path) DO UPDATE SET last_seen=now()''',(identity,relative))
                            db.execute('DELETE FROM library_chunks WHERE path=%s',(relative,))
                            if doc['searchable']:
                                with db.cursor().copy('COPY library_chunks(path,heading,start_line,end_line,page_number,content,match_content) FROM STDIN') as copy:
                                    for chunk in doc['chunks']:copy.write_row((relative,chunk['heading'],chunk['start_line'],chunk['end_line'],chunk.get('page_number'),chunk['content'],library.normalize_match_text(chunk['content'])))
                            db.execute('DELETE FROM library_index_errors WHERE path=%s',(relative,))
                            changed+=1
                    except Exception:
                        failed+=1
                        db.execute('''INSERT INTO library_index_errors(path,category) VALUES (%s,'File unreadable, changed, or metadata invalid')
                            ON CONFLICT(path) DO UPDATE SET category=excluded.category,updated_at=now()''',(relative,))
                    if len(seen)%20==0:progress(job['id'],len(seen),changed,failed,db_connect)
            end_stat=vault.stat()
            complete=not traversal_errors and (root_stat.st_dev,root_stat.st_ino)==(end_stat.st_dev,end_stat.st_ino)
            if complete:
                db.execute('UPDATE library_documents SET present=false WHERE NOT (path=ANY(%s))',(seen,))
                from app.pdf_extract import refresh_selected
                refresh_selected(db)
            if complete and not failed:
                db.execute("INSERT INTO service_status(service) VALUES ('library-index') ON CONFLICT(service) DO UPDATE SET last_seen=now()")
            db.execute('''UPDATE library_index_jobs SET state=%s,seen=%s,changed=%s,failed=%s,error=%s,completed_at=now() WHERE id=%s''',
                ('succeeded' if complete and not failed else 'failed',len(seen),changed,failed,None if complete and not failed else 'Incomplete traversal or file failures; last good evidence retained',job['id']))
        return changed
    except Exception:
        with db_connect() as db:
            db.execute("UPDATE library_index_jobs SET state='failed',seen=%s,changed=%s,failed=%s,error='Vault unavailable, scan interrupted, or index busy; catalog retained',completed_at=now() WHERE id=%s",(len(seen),changed,failed,job['id']))
        return 0
