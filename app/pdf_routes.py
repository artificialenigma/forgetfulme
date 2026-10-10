"""Authenticated, explicit selection controls for local PDF extraction."""
import html
from pathlib import Path
import uuid
from urllib.parse import quote, urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from app.browser_history import admin, csrf, form
from app.db import connect
from app.layout import render_page
from app import pdf_extract

router=APIRouter(dependencies=[Depends(admin)])
esc=lambda value:html.escape(str(value),quote=True)


def controls(request, document):
    """Append to a PDF note view. Original files and AI settings are preserved."""
    if Path(document['path']).suffix.lower()!='.pdf':return ''
    identity=document['document_id']
    with connect() as db:
        selection=db.execute('SELECT enabled FROM library_pdf_selections WHERE document_id=%s',(identity,)).fetchone()
        job=db.execute('SELECT * FROM library_pdf_jobs WHERE document_id=%s AND revision=%s',(identity,document['content_hash'])).fetchone()
    enabled=bool(selection and selection['enabled'])
    body='<h3>Local PDF text extraction</h3><p>Select this PDF to extract its text locally. No AI, cloud upload or OCR is used. Original PDF bytes are preserved.</p>'
    body+='<p>Limits: 25 MiB, 500 pages, 30 seconds per extraction. Image-only PDFs need OCR, which is disabled.</p>'
    if job:
        body+='<p role="status">'+esc(job['state'].replace('_',' '))+f" · {job['pages_with_text']} of {job['pages_total']} pages with text"+'</p>'
        if job['error']:body+='<p>'+esc(job['error'])+'</p>'
        if job['state']=='succeeded' and job['pages_with_text']<job['pages_total']:
            body+='<p>Some pages have no readable text layer; their content needs optional OCR.</p>'
    elif enabled:body+='<p>Selected PDF revision is waiting for a local index scan.</p>'
    else:body+='<p>This PDF has not been selected for local text extraction.</p>'
    hidden=f'<input type="hidden" name="csrf" value="{esc(csrf(request))}"><input type="hidden" name="document_id" value="{esc(identity)}">'
    if not enabled or not job or job['state'] not in {'pending','running','succeeded'}:
        body+='<form method="post" action="/library/pdf/select">'+hidden+'<button name="action" value="retry">'+('Retry local extraction' if enabled and job else 'Extract this PDF locally')+'</button></form>'
    if enabled:
        body+='<form method="post" action="/library/pdf/select">'+hidden+'<button name="action" value="disable">Disable PDF extraction and text search</button></form>'
    body+='<p><a href="/library/pdf">PDF extraction queue</a> · <a href="/library/pdf/original/'+esc(identity)+'">Download original PDF</a></p>'
    return body


@router.get('/library/pdf',response_class=HTMLResponse)
def overview(request:Request):
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    with connect() as db:
        rows=db.execute('''SELECT d.document_id,d.path,d.title,d.content_hash,s.enabled,j.state,j.error,j.pages_total,j.pages_with_text
            FROM library_documents d LEFT JOIN library_pdf_selections s USING(document_id)
            LEFT JOIN library_pdf_jobs j ON j.document_id=d.document_id AND j.revision=d.content_hash
            WHERE d.present AND right(lower(d.path),4)='.pdf' ORDER BY d.path LIMIT 51 OFFSET %s''',((page-1)*50,)).fetchall()
    body='<section class="panel content-panel"><h2>Local PDF extraction</h2><p>Only PDFs you select are processed. Extraction reads text layers locally, preserves originals and keeps page references. OCR and external upload are disabled.</p><p><a href="/library">Library</a></p>'
    if not rows:body+='<p>No indexed PDFs. Import a PDF with your vault and scan changed notes.</p>'
    for row in rows[:50]:
        link='/library/note?'+urlencode({'id':row['document_id']})
        body+='<article class="library-result"><h3><a href="'+esc(link)+'">'+esc(row['title'])+'</a></h3><p>'+esc(row['path'])+'</p><p>'+esc(row['state'] or 'Not selected')
        if row['state']:body+=f" · {row['pages_with_text']} of {row['pages_total']} pages with text"
        if row['enabled'] is False:body+=' · disabled'
        body+='</p>'
        if row['error']:body+='<p role="status">'+esc(row['error'])+'</p>'
        body+='<p>Open the PDF note to select, retry or disable extraction.</p></article>'
    if page>1:body+='<a href="?page='+str(page-1)+'">Previous</a> '
    if len(rows)>50:body+='<a href="?page='+str(page+1)+'">Next</a>'
    return render_page(body+'</section>','PDF extraction','/library')


@router.post('/library/pdf/select')
async def select_pdf(request:Request):
    data=await form(request)
    try:identity=uuid.UUID(data.get('document_id',[''])[0])
    except ValueError:raise HTTPException(400,'Choose an indexed PDF')
    action=data.get('action',[''])[0]
    try:
        if action=='disable':await run_in_threadpool(pdf_extract.disable,identity)
        elif action in {'select','retry'}:await run_in_threadpool(pdf_extract.queue,identity,action=='retry')
        else:raise HTTPException(400,'Unknown PDF extraction action')
    except (ValueError,OSError) as error:
        # Application errors are static and never include PDF text/parser errors.
        detail=str(error) if isinstance(error,ValueError) else 'PDF unavailable; scan changed notes and retry'
        raise HTTPException(409,detail)
    return RedirectResponse('/library/note?'+urlencode({'id':identity}),303)


@router.get('/library/pdf/original/{document_id}')
def download_original(document_id:uuid.UUID):
    from app.library import safe_path
    from app.library_index import snapshot
    with connect() as db:document=db.execute('SELECT path FROM library_documents WHERE document_id=%s AND present',(document_id,)).fetchone()
    if not document or Path(document['path']).suffix.lower()!='.pdf':raise HTTPException(404,'PDF not indexed')
    try:data,_=snapshot(safe_path(document['path']),pdf_extract.MAX_BYTES)
    except (ValueError,OSError):raise HTTPException(404,'Original PDF unavailable')
    if len(data)>pdf_extract.MAX_BYTES:raise HTTPException(413,'Open this large PDF in Obsidian')
    # Always download as opaque bytes so HTML disguised as PDF is never rendered.
    name=Path(document['path']).name
    return Response(data,media_type='application/octet-stream',headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),
        'X-Content-Type-Options':'nosniff',
    })
