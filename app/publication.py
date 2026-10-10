"""Immutable generated-note publication with a durable filesystem journal.

Existing files are never replaced. A new revision is written under a new name;
changes to the old destination become visible conflicts retaining both versions.
"""
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from app.db import connect
from app.file_ops import directory_fd

PUBLICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_publications (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, vault_key text NOT NULL,
 logical_path text NOT NULL, previous_path text NOT NULL, destination_path text NOT NULL,
 expected_hash text NOT NULL, content_hash text NOT NULL, content text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}', state text NOT NULL DEFAULT 'pending'
 CHECK(state IN ('pending','published','conflict','dismissed')),
 error text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 UNIQUE(vault_key,logical_path,content_hash)
);
ALTER TABLE library_publications ADD COLUMN IF NOT EXISTS applied_at timestamptz;
"""


def vault_key(vault):
    return hashlib.sha256(str(Path(vault).absolute()).encode()).hexdigest()


def signed_content(content):
    from app.library import frontmatter,MAX_NOTE
    unsigned=unsigned_content(content)
    metadata,_,_=frontmatter(unsigned)
    if metadata.get('managed_by')!='forgetfulme' or metadata.get('reviewed') is not False or len(unsigned.encode())>MAX_NOTE:
        raise ValueError('Invalid generated note')
    digest=hashlib.sha256(unsigned.encode()).hexdigest()
    return unsigned.replace('---\n','---\ngenerated_content_hash: '+json.dumps(digest)+'\n',1)


def unsigned_content(content):
    """Remove only the generated frontmatter field; preserve body/code lines."""
    if not content.startswith('---\n'):raise ValueError('Generated frontmatter required')
    end=content.find('\n---\n',4,65536)
    if end<0:raise ValueError('Generated frontmatter required')
    header=re.sub(r'^generated_content_hash: [^\n]*(?:\n|$)','',content[4:end],count=1,flags=re.M)
    return '---\n'+header+content[end:]


def read_note(target):
    from app.library_index import snapshot
    from app.library import MAX_NOTE
    try:data,_=snapshot(target,MAX_NOTE)
    except FileNotFoundError:return None
    if len(data)>MAX_NOTE:raise ValueError('Publication file exceeds limit')
    return data


def immutable_write(path,content):
    """No-overwrite create anchored to no-follow directory descriptors."""
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Linked publication path')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=directory_fd(path.parent)
    temporary='.fm-publish-'+secrets.token_hex(16)
    try:
        output=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=fd)
        with os.fdopen(output,'wb') as stream:
            stream.write(content.encode());stream.flush();os.fsync(stream.fileno())
        try:os.link(temporary,path.name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
        except FileExistsError:
            current=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            with os.fdopen(current,'rb') as stream:
                import stat
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Regular publication file required')
                if stream.read(len(content.encode())+1)!=content.encode():raise ValueError('Publication destination conflict')
        os.fsync(fd)
    finally:
        try:os.unlink(temporary,dir_fd=fd)
        except FileNotFoundError:pass
        os.close(fd)


def protected(db,path,vault):
    from app.library import frontmatter,safe_path
    target=safe_path(path,vault)
    row=db.execute('''SELECT EXISTS(SELECT 1 FROM library_import_origins WHERE path=%s)
        OR EXISTS(SELECT 1 FROM library_overrides WHERE path=%s AND reviewed) AS protected''',(path,path)).fetchone()
    if row['protected']:return True
    existing=read_note(target)
    if existing is not None:
        content=existing.decode('utf-8')
        data,_,_=frontmatter(content)
        return data.get('managed_by')!='forgetfulme' or data.get('reviewed') is not False or bool(
            data.get('generated_content_hash') and hashlib.sha256(unsigned_content(content).encode()).hexdigest()!=data['generated_content_hash'])
    return False


def finish(db,row,vault):
    from app.library import safe_path
    destination=safe_path(row['destination_path'],vault)
    previous=safe_path(row['previous_path'],vault)
    before=read_note(previous)
    actual=hashlib.sha256(before).hexdigest() if before is not None else ''
    was_protected=protected(db,row['previous_path'],vault)
    immutable_write(destination,row['content'])
    if row['previous_path']!=row['destination_path']:
        current=read_note(previous)
        actual=hashlib.sha256(current).hexdigest() if current is not None else ''
    # The preserved prior file may change even after this check; no operation
    # below writes/unlinks it. That edit always survives at its original path.
    recovered_create=(row['previous_path']==row['destination_path'] and row['expected_hash']=='' and actual==row['content_hash'])
    conflict=(actual!=row['expected_hash'] and not recovered_create) or was_protected or row['metadata'].get('identity_conflict',False) or (row['previous_path']!=row['destination_path'] and protected(db,row['previous_path'],vault))
    db.execute('''UPDATE library_publications SET state=%s,error=%s,completed_at=now() WHERE id=%s''',
        ('conflict' if conflict else 'published','Prior note changed or is protected; both revisions retained' if conflict else None,row['id']))
    return dict(path=row['destination_path'],state='conflict' if conflict else 'published',id=row['id'])


def publish_note(path,content,expected_hash=None,vault=Path('/vault'),context=None):
    from app.library import safe_path,frontmatter
    path=Path(path);relative=str(path.relative_to(vault));key=vault_key(vault)
    content=signed_content(content);digest=hashlib.sha256(content.encode()).hexdigest()
    incoming,_,_=frontmatter(content)
    with connect() as db:
        db.execute('SELECT pg_advisory_lock(418248)')
        current=db.execute('''SELECT logical_path FROM library_publications
            WHERE vault_key=%s AND destination_path=%s ORDER BY id DESC LIMIT 1''',(key,relative)).fetchone()
        logical=current['logical_path'] if current else relative
        latest=db.execute('''SELECT destination_path FROM library_publications
            WHERE vault_key=%s AND logical_path=%s AND state='published' ORDER BY id DESC LIMIT 1''',(key,logical)).fetchone()
        previous=latest['destination_path'] if latest else relative
        target=safe_path(previous,vault)
        old_bytes=read_note(target)
        actual=hashlib.sha256(old_bytes).hexdigest() if old_bytes is not None else ''
        if old_bytes==content.encode():return dict(path=previous,state='published',id=None)
        destination=logical if old_bytes is None else str(Path(logical).with_name(Path(logical).stem[:160]+' — revision '+digest[:16]+Path(logical).suffix))
        metadata={k:incoming[k] for k in ('type','source_id','source_revision','summary_revision','parent_document_ids','parent_source_ids') if k in incoming}
        if context is not None:metadata['generation_data']=context
        if old_bytes is not None:
            old_meta,_,_=frontmatter(old_bytes.decode('utf-8',errors='replace'))
            if old_meta.get('source_id')!=incoming.get('source_id'):
                # Retain a proposal but never activate a different source family.
                metadata['identity_conflict']=True
        row=db.execute('''INSERT INTO library_publications(vault_key,logical_path,previous_path,destination_path,expected_hash,content_hash,content,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(vault_key,logical_path,content_hash)
            DO UPDATE SET metadata=library_publications.metadata RETURNING *''',
            (key,logical,previous,destination,actual if expected_hash is None else expected_hash,digest,content,json.dumps(metadata))).fetchone()
        # Journal is durable before creating the file; no capture row is updated
        # on this connection, so caller locks cannot deadlock publication.
        db.commit()
        if row['state'] in ('conflict','dismissed'):
            return dict(path=row['destination_path'],state=row['state'],id=row['id'])
        result=finish(db,row,vault)
        if row['metadata'].get('identity_conflict'):
            db.execute("UPDATE library_publications SET state='conflict',error='Source identity conflict; proposal retained' WHERE id=%s",(row['id'],))
            result['state']='conflict'
        return result


def recover_publications(vault=Path('/vault')):
    with connect() as db:
        if not db.execute('SELECT pg_try_advisory_xact_lock(418248) AS locked').fetchone()['locked']:return 0
        rows=db.execute("SELECT * FROM library_publications WHERE vault_key=%s AND state='pending' ORDER BY id LIMIT 20 FOR UPDATE SKIP LOCKED",(vault_key(vault),)).fetchall()
        count=0
        for row in rows:
            try:
                with db.transaction():
                    result=finish(db,row,vault)
                    if row['metadata'].get('identity_conflict'):
                        db.execute("UPDATE library_publications SET state='conflict',error='Source identity conflict; proposal retained' WHERE id=%s",(row['id'],))
                    elif result['state']=='published':count+=1
            except (OSError,ValueError):
                db.execute("UPDATE library_publications SET state='conflict',error='Publication destination unavailable or changed; originals retained',completed_at=now() WHERE id=%s",(row['id'],))
        return count


def apply_publications(vault=Path('/vault')):
    """Reconcile capture pointers after a journal/file commit and caller crash."""
    from app.evidence import source_excluded
    with connect() as db:
        rows=db.execute('''SELECT * FROM library_publications WHERE vault_key=%s
            AND state='published' AND applied_at IS NULL ORDER BY id LIMIT 20
            FOR UPDATE SKIP LOCKED''',(vault_key(vault),)).fetchall()
        for row in rows:
            metadata=row['metadata'];source=metadata.get('source_id')
            if source and metadata.get('type') in ('source','raw_source'):
                capture=db.execute('SELECT * FROM page_captures WHERE url_hash=%s FOR UPDATE SKIP LOCKED',(source,)).fetchone()
                if not capture:continue
                if metadata.get('source_revision','')==capture['capture_content_hash'] and not source_excluded(db,source):
                    destination=read_note(Path(vault)/row['destination_path'])
                    if destination is None or hashlib.sha256(destination).hexdigest()!=row['content_hash']:
                        db.execute("UPDATE library_publications SET state='conflict',error='Published proposal changed or is unavailable' WHERE id=%s",(row['id'],));continue
                    if metadata['type']=='raw_source':
                        db.execute('UPDATE page_captures SET note_path=%s WHERE url_hash=%s',(row['destination_path'],source))
                    else:
                        db.execute('UPDATE page_captures SET wiki_source_path=%s WHERE url_hash=%s',(row['destination_path'],source))
                        data=metadata.get('generation_data')
                        if data is not None and metadata.get('summary_revision')==capture['capture_content_hash']:
                            db.execute("UPDATE page_captures SET ai_state='complete',wiki_data=%s::jsonb,summary_source_hash=%s,ai_error=NULL WHERE url_hash=%s",(json.dumps(data),capture['capture_content_hash'],source))
            db.execute('UPDATE library_publications SET applied_at=now() WHERE id=%s',(row['id'],))
