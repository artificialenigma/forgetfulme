"""Stable path identity and recoverable, no-overwrite filesystem operations."""
import hashlib
import os
from pathlib import Path
from app.db import connect
from psycopg import Error as DatabaseError
from app.file_ops import rename_no_replace


def question_id(document_id, question):
    return hashlib.sha256((str(document_id)+'\0'+question).encode()).hexdigest()


def preflight(db, old, new):
    if db.execute('''SELECT EXISTS(SELECT 1 FROM library_documents WHERE path=%s)
        OR EXISTS(SELECT 1 FROM library_overrides WHERE path=%s)
        OR EXISTS(SELECT 1 FROM library_import_origins WHERE path=%s)
        OR EXISTS(SELECT 1 FROM library_connections WHERE source=%s OR target=%s) AS conflict''',(new,new,new,new,new)).fetchone()['conflict']:
        raise ValueError('Destination catalog or preferences conflict')


def move_catalog(db, old, new):
    row = db.execute('SELECT * FROM library_documents WHERE path=%s FOR UPDATE', (old,)).fetchone()
    if not row:
        return
    preflight(db,old,new)
    from app.connection_export import queue
    affected=db.execute('SELECT source FROM library_connections WHERE target=%s OR source=%s',(old,old)).fetchall()
    for connection in affected:queue(db,connection['source'])
    db.execute('UPDATE library_documents SET path=%s WHERE path=%s', (new,old))
    db.execute('UPDATE library_overrides SET path=%s WHERE path=%s', (new,old))
    db.execute('UPDATE library_import_origins SET path=%s WHERE path=%s', (new,old))
    db.execute('UPDATE library_connections SET source=%s WHERE source=%s', (new,old))
    db.execute('UPDATE library_connections SET target=%s WHERE target=%s', (new,old))
    db.execute('UPDATE library_question_status SET answer_path=%s WHERE answer_path=%s', (new,old))
    db.execute('UPDATE page_captures SET note_path=%s WHERE note_path=%s', (new,old))
    db.execute('UPDATE page_captures SET wiki_source_path=%s WHERE wiki_source_path=%s', (new,old))
    db.execute('DELETE FROM library_index_errors WHERE path=%s', (old,))
    db.execute('''INSERT INTO library_path_history(document_id,path) VALUES (%s,%s)
        ON CONFLICT(document_id,path) DO UPDATE SET last_seen=now()''', (row['document_id'],new))


def migrate_questions(db, row):
    for question in row['metadata'].get('questions', []):
        legacy = hashlib.sha256((row['path']+'\0'+question).encode()).hexdigest()
        stable = question_id(row['document_id'], question)
        db.execute('''INSERT INTO library_question_status(id,state,answer_path,updated_at)
            SELECT %s,state,answer_path,updated_at FROM library_question_status WHERE id=%s
            ON CONFLICT(id) DO NOTHING''', (stable,legacy))


def source_digest(path):
    from app.library_index import snapshot
    from app.library import MAX_NOTE
    data,_=snapshot(path,MAX_NOTE)
    if len(data)>MAX_NOTE:raise ValueError('Source exceeds rename limit')
    return hashlib.sha256(data).hexdigest()


def finish_operation(db, operation, vault):
    from app.library import safe_path
    source = safe_path(operation['old_path'],vault)
    destination = safe_path(operation['new_path'],vault)
    preflight(db,operation['old_path'],operation['new_path'])
    if destination.exists():
        if source.exists():
            raise ValueError('Destination conflict')
        if source_digest(destination) != operation['content_hash']:
            raise ValueError('Source changed during rename')
    else:
        if not source.is_file() or source_digest(source) != operation['content_hash']:
            raise ValueError('Source missing or changed')
        destination.parent.mkdir(parents=True,exist_ok=True)
        rename_no_replace(source,destination)
        if destination.is_symlink() or source_digest(destination) != operation['content_hash']:
            raise ValueError('Source changed during rename')
    # A crash after the atomic rename leaves the new file and a pending journal;
    # recovery updates app relationships without deleting any source path.
    move_catalog(db,operation['old_path'],operation['new_path'])
    db.execute("UPDATE library_operations SET state='complete',error=NULL,completed_at=now() WHERE id=%s",(operation['id'],))


def recover_operations(db, vault):
    for operation in db.execute("SELECT * FROM library_operations WHERE state='pending' ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED").fetchall():
        try:
            with db.transaction():
                finish_operation(db,operation,vault)
        except (OSError,ValueError,DatabaseError):
            db.execute("UPDATE library_operations SET state='conflict',error='Rename conflict; inspect source and destination before retry' WHERE id=%s",(operation['id'],))


def rename_note(old, new, vault=Path('/vault'), expected_hash=None):
    from app.library import safe_path
    with connect() as db:
        # Session lock survives committing the journal before touching files.
        db.execute('SELECT pg_advisory_lock(418245)')
        row=db.execute('SELECT * FROM library_documents WHERE path=%s AND present',(old,)).fetchone()
        if not row or old==new:
            raise ValueError('Source not indexed')
        source=safe_path(old,vault);destination=safe_path(new,vault)
        preflight(db,old,new)
        if destination.exists() or db.execute('SELECT path FROM library_documents WHERE path=%s',(new,)).fetchone():
            raise ValueError('Destination exists')
        from app.library_index import snapshot
        from app.library import MAX_NOTE
        data,_=snapshot(source,MAX_NOTE)
        if len(data)>MAX_NOTE:raise ValueError('Source exceeds rename limit')
        digest=hashlib.sha256(data).hexdigest()
        if expected_hash is not None and digest!=expected_hash:raise ValueError('Source changed since preview')
        migrate_questions(db,row)
        operation=db.execute('''INSERT INTO library_operations(document_id,old_path,new_path,content_hash)
            VALUES (%s,%s,%s,%s) RETURNING *''',(row['document_id'],old,new,digest)).fetchone()
        db.commit()
        # Leave pending on interruption/failure: worker recovery is idempotent.
        finish_operation(db,operation,vault)
        return row['document_id']
