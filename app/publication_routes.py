"""Review immutable publication proposals; never overwrite either revision."""
import hashlib
import html
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from app.browser_history import admin,csrf,form
from app.db import connect
from app.layout import render_page
from app.publication import vault_key,read_note,protected
from app.library import safe_path

router=APIRouter(dependencies=[Depends(admin)])
esc=lambda value:html.escape(str(value),quote=True)


@router.get('/library/publications',response_class=HTMLResponse)
def publications(request:Request):
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    with connect() as db:
        rows=db.execute("SELECT * FROM library_publications WHERE vault_key=%s AND state IN ('pending','conflict') ORDER BY id DESC LIMIT 31 OFFSET %s",(vault_key('/vault'),(page-1)*30)).fetchall()
    body='<section class="panel content-panel"><h2>Publication review</h2><p>Updates create separate revisions. Original notes and edits are retained. Activating a proposal changes the app’s preferred revision; it does not replace the prior file.</p>'
    for row in rows[:30]:
        body+='<article class="library-result"><h3>'+esc(row['logical_path'])+'</h3><p>'+esc(row['state'])+' · '+esc(row['error'] or 'Recovery pending')+'</p><p>Prior: '+esc(row['previous_path'])+'<br>Proposal: '+esc(row['destination_path'])+'</p><details><summary>Preview proposed note</summary><pre class="note-content">'+esc(row['content'])+'</pre></details>'
        body+='<form method="post" action="/library/publications/action"><input type="hidden" name="csrf" value="'+esc(csrf(request))+'"><input type="hidden" name="id" value="'+str(row['id'])+'"><button name="action" value="activate">Use proposed revision</button><button name="action" value="dismiss">Keep current revision</button></form></article>'
    if not rows:body+='<p>No pending publication conflicts.</p>'
    if page>1:body+='<a href="?page='+str(page-1)+'">Previous</a> '
    if len(rows)>30:body+='<a href="?page='+str(page+1)+'">Next</a>'
    return render_page(body+'</section>','Publication review','/library/health')


@router.post('/library/publications/action')
async def publication_action(request:Request):
    data=await form(request)
    try:identity=int(data.get('id',[''])[0])
    except ValueError:raise HTTPException(400,'Invalid publication')
    action=data.get('action',[''])[0]
    with connect() as db:
        row=db.execute("SELECT * FROM library_publications WHERE id=%s AND vault_key=%s AND state='conflict' FOR UPDATE",(identity,vault_key('/vault'))).fetchone()
        if not row:raise HTTPException(409,'Publication no longer needs review')
        if action=='dismiss':
            db.execute("UPDATE library_publications SET state='dismissed',completed_at=now() WHERE id=%s",(identity,))
        elif action=='activate':
            if row['metadata'].get('identity_conflict'):raise HTTPException(409,'Conflicting source identity cannot be activated')
            try:
                destination=safe_path(row['destination_path'])
                content=read_note(destination)
            except (OSError,ValueError):raise HTTPException(409,'Proposal unavailable; originals retained')
            if content is None or hashlib.sha256(content).hexdigest()!=row['content_hash']:raise HTTPException(409,'Proposal changed; review the current file in Obsidian')
            if protected(db,row['destination_path'],Path('/vault')):raise HTTPException(409,'Proposal is imported, reviewed, or edited; originals retained')
            db.execute("UPDATE library_publications SET state='published',error=NULL,completed_at=now(),applied_at=NULL WHERE id=%s",(identity,))
        else:raise HTTPException(400,'Unknown publication action')
    from app.publication import apply_publications
    from app.library_index import request_scan
    apply_publications();request_scan()
    return RedirectResponse('/library/publications',303)
