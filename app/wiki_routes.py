"""Authenticated knowledge queue and source-grounded local questions."""
import html
import uuid
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
    body += '<section class="panel content-panel"><h2>Ask your sources</h2><p><a href="/settings/ai">Configure AI provider →</a></p><p>Your configured AI provider answers cite up to three relevant compiled sources. Retrieval matches question words against source summaries; processing runs in the background. Short, focused questions work best. Review answers against the linked sources.</p>'
    body += f'<form method="post" action="/vault/wiki/questions"><input type="hidden" name="csrf" value="{csrf(request)}"><label for="question">Question</label><input id="question" name="question" required maxlength="1000" placeholder="What do my sources say about Docker?"><button type="submit">Ask AI</button></form><p>Reload this page to see completed answers.</p></section>'
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
    with connect() as db:
        pending = db.execute("SELECT count(*) AS count FROM wiki_questions WHERE state='pending'").fetchone()['count']
        if pending>=10: raise HTTPException(429,'Wait for queued questions to finish')
        db.execute('INSERT INTO wiki_questions(id,question) VALUES (%s,%s)',(uuid.uuid4(),question))
    return RedirectResponse('/vault/wiki',status_code=303)
