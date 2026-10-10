"""Authenticated knowledge queue and source-grounded local questions."""
import html
import uuid
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.browser_history import admin, csrf, form
from app.db import connect
from app.layout import render_page

router = APIRouter()


@router.get('/vault/wiki', dependencies=[Depends(admin)], response_class=HTMLResponse)
def knowledge(request: Request):
    with connect() as db:
        counts = db.execute("SELECT ai_state,count(*) AS count FROM page_captures WHERE state='complete' GROUP BY ai_state").fetchall()
        indexed = db.execute("SELECT count(*) AS count FROM page_captures WHERE wiki_indexed_at IS NOT NULL").fetchone()['count']
        worker = db.execute("SELECT last_seen > now()-interval '90 seconds' AS healthy FROM service_status WHERE service='wiki-worker'").fetchone()
        questions = db.execute('SELECT * FROM wiki_questions ORDER BY created_at DESC LIMIT 10').fetchall()
    body = '<section class="panel content-panel"><h2>Your linked knowledge library</h2><p>Open <strong>Forgetful Me/Home</strong> in the <a href="/vault">Obsidian desktop</a>. Browse readable source records, full captured pages and dated history. Automatic concept/entity expansion is disabled.</p>'
    if not indexed:
        body='<section class="panel content-panel"><h2>Your personal vault</h2><p>The vault is ready for your own notes. <a href="/vault/import">Import your local vault</a> or <a href="/vault">open Obsidian</a>. Generated archive indexes will appear only when automatic processing is enabled and new browsing pages are captured.</p>'

    body += f'<p><strong>{indexed:,} sources indexed</strong> · Wiki worker: {"running" if worker and worker["healthy"] else "waiting"}</p><ul>'
    body += ''.join('<li>AI '+html.escape(row['ai_state'])+': '+f'{row["count"]:,}'+'</li>' for row in counts)+'</ul><p>AI drafts use bounded excerpts. Summaries are optional; AI processing can be paused in AI settings. Add <code>reviewed: true</code> to a generated note’s frontmatter to protect your edits. Existing captures are preserved.</p></section>'
    body += '<section class="panel content-panel"><p><a href="/library">Search the unified library</a> · <a href="/library/questions">Open research questions</a> · <a href="/library/health">Vault health</a></p><h2>Ask your sources</h2><p><a href="/settings/ai">Configure AI provider →</a></p><p>Local search works without AI. Asking AI sends up to six relevant sections to your configured provider. Choose browsing captures only, or explicitly include imported personal notes. Answers retain the exact cited excerpts and source revisions. Saved AI answers are never reused as evidence.</p>'
    from app import library
    projects=sorted({r['effective_project'] for r in library.documents() if r['effective_project']})
    project=request.query_params.get('project','')[:100]
    document=request.query_params.get('document_id','')
    scope=request.query_params.get('scope','archive')
    chosen=' selected' if scope=='all' else ''
    project_control='<label for="project">Project</label><select id="project" name="project"><option value="">All projects</option>'+''.join('<option value="'+html.escape(p,quote=True)+'"'+(' selected' if p==project else '')+'>'+html.escape(p)+'</option>' for p in projects)+'</select>'
    source_control='<input type="hidden" name="document_id" value="'+html.escape(document,quote=True)+'">'
    if document:body+='<p>Evidence is restricted to the chosen source. <a href="/vault/wiki">Clear source restriction</a></p>'
    body += f'<form method="post" action="/vault/wiki/questions"><input type="hidden" name="csrf" value="{csrf(request)}"><label for="question">Question</label><input id="question" name="question" required maxlength="1000" placeholder="What do my sources say about Docker?"><label for="scope">Evidence scope</label><select id="scope" name="scope"><option value="archive">Browsing captures only</option><option value="all"{chosen}>Include my imported notes — send matching excerpts to the configured AI provider</option></select>{project_control}{source_control}<button type="submit">Ask AI</button><button type="submit" formmethod="get" formaction="/vault/wiki/evidence">Preview evidence locally</button></form><p>Reload this page to see completed answers.</p></section>'
    for item in questions:
        body += '<section class="panel content-panel"><h2>'+html.escape(item['question'])+'</h2><p>'+html.escape(item['state'])+'</p>'
        if item['answer']:
            body += '<p class="wiki-answer">'+html.escape(item['answer']).replace('\n','<br>')+'</p><ul>'
            body += ''.join('<li><a href="'+html.escape(c['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(c['title'])+'</a> · Obsidian source ID: <code>'+html.escape(c['id'])+'</code></li>' for c in item['citations'])+'</ul><p>Answer saved in Forgetful Me/wiki/queries.</p>'
        if item['error']: body += '<p role="alert">'+html.escape(item['error'])+'</p>'
        body += '</section>'
    return render_page(body,'Knowledge wiki','/vault/wiki')


@router.post('/vault/wiki/questions', dependencies=[Depends(admin)])
async def ask(request: Request):
    data = await form(request)
    question = data.get('question',[''])[0].strip()
    if not question or len(question)>1000: raise HTTPException(400,'Provide a question up to 1,000 characters')
    scope=data.get('scope',[''])[0]
    if scope not in ('archive','all'):raise HTTPException(400,'Choose an evidence scope')
    project=data.get('project',[''])[0].strip()
    document=data.get('document_id',[''])[0].strip()
    if len(project)>100:raise HTTPException(400,'Project is too long')
    try:source_id=uuid.UUID(document) if document else None
    except ValueError:raise HTTPException(400,'Invalid source identity')
    from app.ai_provider import settings
    if not settings()['enabled']:raise HTTPException(400,'AI is paused. Use local Library search, or enable AI in settings.')
    with connect() as db:
        if source_id and not db.execute('SELECT document_id FROM library_documents WHERE document_id=%s AND present',(source_id,)).fetchone():raise HTTPException(400,'Source unavailable')
        pending = db.execute("SELECT count(*) AS count FROM wiki_questions WHERE state='pending'").fetchone()['count']
        if pending>=10: raise HTTPException(429,'Wait for queued questions to finish')
        db.execute('INSERT INTO wiki_questions(id,question,scope,project,source_document_id) VALUES (%s,%s,%s,%s,%s)',(uuid.uuid4(),question,scope,project,source_id))
    return RedirectResponse('/vault/wiki',status_code=303)


@router.get('/vault/wiki/evidence',dependencies=[Depends(admin)],response_class=HTMLResponse)
def preview_evidence(request:Request):
    from app import library
    from app.evidence import revalidate
    from app.retrieval import select_evidence,selection_report
    from app.ai_provider import settings
    q=request.query_params.get('question','')[:1000]
    scope=request.query_params.get('scope','')
    if scope not in ('archive','all'):raise HTTPException(400,'Choose an evidence scope')
    project=request.query_params.get('project','')[:100]
    document=request.query_params.get('document_id','')
    config=settings()
    budget=max(1,min(3500,config['context_size']-config['max_tokens']-800-len(q.encode())//3))
    candidates=library.search(q,scope=scope,project=project,document_id=document,limit=24,for_ai=True)
    with connect() as db:rows=select_evidence(revalidate(candidates,scope,db),token_budget=budget)
    report=selection_report(rows,budget)
    esc=lambda value:html.escape(str(value),quote=True)
    body='<section class="panel content-panel"><h2>Local evidence preview</h2><p>No provider request was made. A queued answer retrieves again and follows current exclusions.</p><p>'+esc(report['sources'])+' sources · '+esc(report['sections'])+' sections · '+esc(report['estimated_tokens'])+' estimated tokens</p>'
    if not rows:body+='<p>No relevant permitted evidence. Try a narrower question or another explicit scope.</p>'
    for row in rows:
        body+='<article class="library-result"><h3>'+esc(row['title'])+'</h3><p>'+esc(row['path'])+' · '+esc(row['heading'])+'</p><pre class="note-content">'+esc(row['content'])+'</pre></article>'
    body+='<p><a href="/vault/wiki?'+esc(urlencode(dict(scope=scope,project=project,document_id=document)))+'">Return to Ask</a></p></section>'
    return render_page(body,'Evidence preview','/vault/wiki')
