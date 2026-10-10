"""Outbound evidence rules; folder names and frontmatter never confer consent."""
import re

# Shared by retrieval and prompt-time revalidation. Excluding either a source
# record or raw capture applies to every catalogued derivative of that source.
ALLOWED = """d.present AND d.searchable AND NOT coalesce(o.excluded,false)
 AND (right(lower(d.path),4)<>'.pdf' OR EXISTS (
     SELECT 1 FROM library_pdf_selections s JOIN library_pdf_jobs j USING(document_id)
     WHERE s.document_id=d.document_id AND s.enabled AND j.revision=d.content_hash AND j.state='succeeded'))
 AND NOT EXISTS (SELECT 1 FROM page_captures p WHERE p.url_hash=d.source_id AND p.excluded)
 AND NOT EXISTS (SELECT 1 FROM library_documents sibling JOIN library_overrides so USING(path)
                 WHERE d.source_id<>'' AND sibling.source_id=d.source_id AND so.excluded)"""


def classify(path, meta, archive_sources, imported_paths):
    source_id = archive_sources.get(path, '')
    if source_id and meta.get('source_id') and str(meta['source_id'])!=source_id:
        source_id=''  # Conflicting identity claims never supply archive evidence.
    # ZIP provenance takes precedence over any user-supplied ownership marker.
    if path in imported_paths or not source_id:
        origin, scope, source_id = 'imported', 'imported', ''
    else:
        origin, scope = 'archive', 'archive'
    kind = str(meta.get('type') or '')
    # Answers and navigational/connection derivatives remain locally searchable
    # but never become AI evidence, including historical answers without lineage.
    if kind in {'query','connections','index','home','website','concept','entity'} and meta.get('managed_by') == 'forgetfulme':
        scope = 'none'
    if path.startswith(('Forgetful Me/wiki/queries/', 'Forgetful Me/Connections/')):
        scope = 'none'
    if meta.get('managed_by') == 'forgetfulme' and kind in {'source','raw_source'} and not source_id:
        scope = 'none'  # Unknown generated source: do not assume its parents.
    return origin, scope, source_id


def revalidate(rows, scope, db):
    if scope not in {'archive', 'all'}:
        raise ValueError('Explicit evidence scope required')
    if not rows:
        return []
    allowed_scopes = ['archive'] if scope == 'archive' else ['archive','imported']
    current = db.execute('''SELECT c.id,d.content_hash FROM library_chunks c
        JOIN library_documents d USING(path) LEFT JOIN library_overrides o USING(path)
        WHERE c.id=ANY(%s) AND d.evidence_scope=ANY(%s)
        AND (%s='all' OR NOT EXISTS(SELECT 1 FROM library_import_origins i WHERE i.path=d.path)) AND ''' + ALLOWED,
        ([r['id'] for r in rows], allowed_scopes, scope)).fetchall()
    good = {r['id']: r['content_hash'] for r in current}
    return [r for r in rows if good.get(r['id']) == r['content_hash']]


def source_excluded(db, identity):
    if not re.fullmatch(r'[a-f0-9]{64}', identity or ''):
        return True
    row = db.execute('''SELECT p.excluded OR EXISTS(
        SELECT 1 FROM library_documents d JOIN library_overrides o USING(path)
        WHERE d.source_id=p.url_hash AND o.excluded) AS excluded
        FROM page_captures p WHERE p.url_hash=%s''', (identity,)).fetchone()
    return not row or row['excluded']
