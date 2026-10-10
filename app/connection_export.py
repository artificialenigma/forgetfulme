"""Recoverable companion exports; never modify source or destination notes."""
from pathlib import Path
from app.db import connect


def queue(db,source):
    db.execute('''INSERT INTO library_connection_exports(document_id)
        SELECT document_id FROM library_documents WHERE path=%s
        ON CONFLICT(document_id) DO UPDATE SET state='pending',error=NULL,updated_at=now()''',(source,))


def process_one(vault=Path('/vault')):
    from app.wiki import note_header,link
    from app.publication import publish_note
    with connect() as db:
        row=db.execute("SELECT e.*,d.path AS source FROM library_connection_exports e JOIN library_documents d USING(document_id) WHERE e.state='pending' AND d.present ORDER BY e.updated_at FOR UPDATE OF e SKIP LOCKED LIMIT 1").fetchone()
        if not row:return False
        targets=db.execute('SELECT target FROM library_connections WHERE source=%s ORDER BY target',(row['source'],)).fetchall()
        content=note_header('connections','Reviewed connections',parent_document_ids=[str(row['document_id'])],outbound_evidence='none')+'# Reviewed connections\n\n'+link(row['source'],Path(row['source']).stem)+'\n\n'+'\n'.join('- '+link(r['target'],Path(r['target']).stem) for r in targets)+'\n'
        destination=row['path'] or 'Forgetful Me/Connections/'+str(row['document_id'])+'.md'
        try:
            result=publish_note(vault/destination,content,vault=vault)
            db.execute('UPDATE library_connection_exports SET state=%s,path=%s,error=%s,updated_at=now() WHERE document_id=%s',
                       (result['state'],result['path'],None if result['state']=='published' else 'Companion publication requires review',row['document_id']))
        except (OSError,ValueError):
            db.execute("UPDATE library_connection_exports SET state='conflict',error='Companion unavailable; app relationships are saved',updated_at=now() WHERE document_id=%s",(row['document_id'],))
    return True
