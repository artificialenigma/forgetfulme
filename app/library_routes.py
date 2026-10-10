"""Authenticated unified library, evidence viewer and review tools."""
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.browser_history import admin, csrf, form
from app.db import connect
from app.layout import render_page
from app import library

router=APIRouter(dependencies=[Depends(admin)])
esc=lambda x:html.escape(str(x),quote=True)


def note_url(path,line=None):
    return '/library/note?'+urlencode({'path':path})+(f'#line-{line}' if line else '')


def citation_url(question, source):
    return '/library/citation?'+urlencode({'question':str(question),'source':source})


def hidden(request):return f'<input type="hidden" name="csrf" value="{csrf(request)}">'


def select(name,label,values,current):
    body=f'<div class="library-field"><label for="{name}">{label}</label><select id="{name}" name="{name}"><option value="">All</option>'
    for value in values:body+=f'<option value="{esc(value)}"'+(' selected' if value==current else '')+'>'+esc(value)+'</option>'
    return body+'</select></div>'


def summary():
    rows=library.documents(); issues=library.health(rows)
    return dict(notes=len(rows),searchable=sum(r['searchable'] and not r['excluded'] for r in rows),imported=sum(r['display_origin']=='imported' and r['kind']!='attachment' for r in rows),issues=len(issues),questions=sum(len(r['metadata'].get('questions',[])) for r in rows),reviewed=sum(r['effective_reviewed'] for r in rows),generated=sum(r['display_origin']=='generated' for r in rows))


@router.get('/library',response_class=HTMLResponse)
def browse(request:Request):
    q=request.query_params.get('q','')[:1000];filters={k:request.query_params.get(k,'')[:100] for k in ('origin','kind','tag','project','review')}
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    rows=library.documents()
    hits=library.search(q,**filters,limit=31,offset=(page-1)*30)
    body='<section class="panel content-panel"><h2>Your knowledge library</h2><p>Search imported notes and browsing captures locally. AI is only used when you explicitly ask a question.</p><p><a href="/library/health">Vault health</a> · <a href="/library/questions">Research questions</a> · <a href="/vault/wiki">Ask AI</a></p>'
    body+=f'<p>{sum(r["display_origin"]=="generated" for r in rows):,} generated navigation/history files · {sum(r["display_origin"]=="imported" and r["kind"]!="attachment" for r in rows):,} imported notes</p>'
    body+=f'<p>{len(rows):,} indexed files · {sum(r["searchable"] and not r["excluded"] for r in rows):,} searchable · {sum(r["effective_reviewed"] for r in rows):,} reviewed</p>'
    body+=f'<form method="get" class="library-filters"><div class="library-field"><label for="q">Search notes and sections</label><input id="q" name="q" value="{esc(q)}" maxlength="1000" placeholder="ESP32 intercom, Maldives, GBDK…"></div>'
    for name,label,values in [('origin','Origin',['imported','archive','generated']),('kind','Type',sorted({r['kind'] for r in rows})),('tag','Topic / tag',sorted({t for r in rows for t in r['tags']})),('project','Project',sorted({r['effective_project'] for r in rows if r['effective_project']})),('review','Review',['reviewed','draft'])]:body+=select(name,label,values,filters[name])
    body+='<button>Search / filter</button></form>'
    if not rows:body+='<p>The local index is being built. Refresh shortly, or reindex below.</p>'
    if not hits:body+='<p>No matching sections. Try broader terms or another filter.</p>'
    for row in hits[:30]:
        body+=f'<article class="library-result"><h3><a href="{esc(note_url(row["path"],row["start_line"]))}">{esc(row["title"])}</a></h3><p>{esc(row["display_origin"])} · {esc(row["kind"])} · {"Reviewed" if row["reviewed"] else "Unreviewed"} · {esc(row["heading"])} · lines {row["start_line"]}–{row["end_line"]}</p><p>{esc(row["content"][:450])}</p><small>{esc(row["path"])}</small></article>'
    args={'q':q,**filters};body+='<div class="pagination">'
    if page>1:body+=f'<a href="/library?{esc(urlencode({**args,"page":page-1}))}">Previous</a>'
    if len(hits)>30:body+=f'<a href="/library?{esc(urlencode({**args,"page":page+1}))}">Next</a>'
    body+='</div>'+f'<form method="post" action="/library/reindex">{hidden(request)}<button>Scan for changed notes</button></form><form method="post" action="/library/reindex?mode=full">{hidden(request)}<button>Rebuild every local note</button></form></section>'
    return render_page(body,'Library','/library')


@router.post('/library/reindex')
async def reindex(request:Request):
    await form(request)
    # Request a scan in the worker; avoid holding an HTTP request over large vaults.
    from app.library_index import request_scan
    request_scan('full' if request.query_params.get('mode')=='full' else 'incremental')
    return RedirectResponse('/library',303)


@router.get('/library/note',response_class=HTMLResponse)
def show_note(request:Request):
    path=request.query_params.get('path','');identity=request.query_params.get('id','')
    rows=library.documents();row=next((r for r in rows if str(r['document_id'])==identity),None) if identity else next((r for r in rows if r['path']==path),None)
    if row:path=row['path']
    if not row:raise HTTPException(404,'Note not indexed')
    try:target=library.safe_path(path)
    except ValueError:raise HTTPException(400,'Invalid note path')
    if not target.is_file():raise HTTPException(404,'Note no longer exists')
    body=f'<section class="panel content-panel"><h2>{esc(row["title"])}</h2><p><a href="/library">Library</a> · <a href="/vault">Obsidian desktop</a></p><p>{esc(path)} · {esc(row["kind"])} · {esc(row["display_origin"])} · {row["words"]:,} body words</p>'
    body+='<p><a href="'+esc('/vault/wiki?'+urlencode({'document_id':str(row['document_id']),'scope':'archive' if row['evidence_scope']=='archive' else 'all'}))+'">Ask about this source</a></p>'
    body+='<h3>Evidence and provenance</h3><dl>'
    for label,value in [('Original URL',__import__('app.ingestion_policy',fromlist=['safe_display_url']).safe_display_url(row['source_url']) if row['source_url'] else ''),('Review','Reviewed' if row['effective_reviewed'] else 'Unreviewed'),('Project',row['effective_project']),('AI evidence scope',row['evidence_scope']),*[(k,v) for k,v in row['metadata'].items() if k not in ('issues','links','questions','source_refs')]]:
        if value not in ('',None,[]):body+=f'<dt>{esc(label)}</dt><dd>{esc(value)}</dd>'
    body+='</dl>'
    for ref in row['metadata'].get('source_refs',[]):body+='<p>Source reference: '+esc(ref)+'</p>'
    for issue in row['metadata'].get('issues',[]):body+='<p role="status">'+esc(issue['detail'])+'</p>'
    body+=f'<form method="post" action="/library/preferences">{hidden(request)}<input type="hidden" name="path" value="{esc(path)}"><label for="project">Project</label><input id="project" name="project" value="{esc(row["effective_project"])}" maxlength="100"><label><input type="checkbox" name="reviewed" value="1"'+(' checked' if row['effective_reviewed'] else '')+'> Mark reviewed in app</label><label><input type="checkbox" name="excluded" value="1"'+(' checked' if row['excluded'] else '')+'> Exclude from search and AI</label><button>Save library preferences</button></form><p>Preferences stay in the app; your source note is preserved.</p>'
    with connect() as db:
        connections=db.execute('SELECT target FROM library_connections WHERE source=%s',(path,)).fetchall()
        export=db.execute('SELECT * FROM library_connection_exports WHERE document_id=%s',(row['document_id'],)).fetchone()
    if connections:
        body+='<h3>Accepted connections</h3><ul>'+''.join(f'<li><a href="{esc(note_url(c["target"]))}">{esc(c["target"])}</a></li>' for c in connections)+'</ul>'
    if export:body+='<p>Connection export: '+esc(export['state'])+' '+esc(export['error'] or '')+'</p>'
    for connection in connections:
        body+=f'<form method="post" action="/library/connections/remove">{hidden(request)}<input type="hidden" name="source" value="{esc(path)}"><input type="hidden" name="target" value="{esc(connection["target"])}"><button>Remove connection to {esc(connection["target"])}</button></form>'
    body+='<h3>Suggested connections</h3><p>Based on shared tags and projects. Review the destination before accepting.</p>'
    for candidate in library.suggestions(path,rows):
        body+=f'<p><a href="{esc(note_url(candidate["path"]))}">{esc(candidate["title"])}</a> · Shared tags: {esc(", ".join(candidate["tags"]))}</p><form method="post" action="/library/connections">{hidden(request)}<input type="hidden" name="source" value="{esc(path)}"><input type="hidden" name="target" value="{esc(candidate["path"])}"><button>Accept connection</button></form>'
    if row['source_id']:
        identity=row['source_id']
        with connect() as db:capture=db.execute('SELECT excluded,publication_state,publication_error,capture_content_hash FROM page_captures WHERE url_hash=%s',(identity,)).fetchone()
        if capture:
            if capture['publication_error']:body+='<p role="status">'+esc(capture['publication_error'])+'</p>'
            if row['metadata'].get('source_revision') and capture['capture_content_hash'] and row['metadata']['source_revision']!=capture['capture_content_hash']:
                body+='<p role="status">A newer capture exists. This note belongs to an older source revision.</p>'
            body+=f'<h3>Capture controls</h3><form method="post" action="/history/capture/action">{hidden(request)}<input type="hidden" name="id" value="{esc(identity)}"><button name="action" value="retry">Retry capture</button><button name="action" value="{"include" if capture["excluded"] else "exclude"}">{"Include capture" if capture["excluded"] else "Exclude capture"}</button></form>'
    body+='<h3>Related notes</h3><ul>' 
    paths={r['path'] for r in rows};aliases=library.path_aliases()
    for raw in row['metadata'].get('links',[]):
        for destination in library.resolve_link(path,raw,paths,aliases):
            body+=f'<li><a href="{esc(note_url(destination))}">{esc(raw.split("|")[-1])}</a></li>'
    from app.pdf_routes import controls as pdf_controls
    body+=pdf_controls(request,row)
    body+='</ul><h3>Note content</h3>' 
    if target.suffix.lower()=='.md' and target.stat().st_size<=library.MAX_NOTE:
        from app.library_index import snapshot
        from app.reading import render
        source,_=snapshot(target,library.MAX_NOTE)
        note_text=source.decode('utf-8',errors='replace')
        _,read_body,_=library.frontmatter(note_text)
        body+='<div class="reading-content">'+render(read_body)+'</div><details><summary>Raw source and line evidence</summary>'
        body+='<pre class="note-content">'+''.join(f'<span id="line-{i}" class="note-line"><a href="#line-{i}" aria-label="Line {i}">{i}</a> {esc(line)}\n</span>' for i,line in enumerate(note_text.splitlines(),1))+'</pre></details>'
    else:body+='<p>Open the original in Obsidian. Selected PDFs with successfully extracted text can be searched and used with an explicit AI evidence scope.</p>'
    return render_page(body+'</section>',row['title'],'/library')


@router.post('/library/preferences')
async def preferences(request:Request):
    data=await form(request);path=data.get('path',[''])[0];project=data.get('project',[''])[0].strip()
    if len(project)>100:raise HTTPException(400,'Project is too long')
    with connect() as db:
        if not db.execute('SELECT path FROM library_documents WHERE path=%s',(path,)).fetchone():raise HTTPException(404,'Note not indexed')
        db.execute('''INSERT INTO library_overrides(path,excluded,reviewed,project) VALUES (%s,%s,%s,%s)
            ON CONFLICT(path) DO UPDATE SET excluded=excluded.excluded,reviewed=excluded.reviewed,project=excluded.project''',(path,data.get('excluded')==['1'],data.get('reviewed')==['1'],project))
    return RedirectResponse(note_url(path),303)


@router.post('/library/connections')
async def accept_connection(request:Request):
    data=await form(request);source=data.get('source',[''])[0];target=data.get('target',[''])[0]
    rows=library.documents()
    if target not in {x['path'] for x in library.suggestions(source,rows)}:raise HTTPException(400,'Connection is no longer suggested')
    with connect() as db:db.execute('INSERT INTO library_connections(source,target) VALUES (%s,%s) ON CONFLICT DO NOTHING',(source,target))
    from app.connection_export import queue,process_one
    with connect() as db:queue(db,source)
    process_one()
    return RedirectResponse(note_url(source),303)


@router.get('/library/health',response_class=HTMLResponse)
def vault_health(request:Request):
    rows=library.documents();issues=library.health(rows);kind=request.query_params.get('kind','')
    indexed={r['path']:r for r in rows}
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    with connect() as db:dismissed={(str(r['document_id']),r['revision'],r['finding']) for r in db.execute('SELECT * FROM library_health_dismissals').fetchall()}
    visible=[]
    for issue in issues:
        row=indexed[issue['path']]
        finding=hashlib.sha256((issue['kind']+'\0'+issue['detail']).encode()).hexdigest()
        issue['finding']=finding
        hidden_issue=(str(row['document_id']),row['content_hash'],finding) in dismissed
        issue['dismissed']=hidden_issue
        if (not kind or issue['kind']==kind) and (request.query_params.get('dismissed')=='1' or not hidden_issue):visible.append(issue)
    with connect() as db:
        jobs=db.execute('SELECT * FROM library_index_jobs ORDER BY id DESC LIMIT 5').fetchall()
        errors=db.execute('SELECT * FROM library_index_errors ORDER BY updated_at DESC LIMIT 100').fetchall()
        publication=db.execute("SELECT publication_state,count(*) AS count FROM page_captures WHERE publication_state IN ('missing','protected','conflict','retry') GROUP BY publication_state").fetchall()
        operations=db.execute("SELECT old_path,new_path,state,error FROM library_operations WHERE state<>'complete' ORDER BY created_at LIMIT 100").fetchall()
    from collections import Counter
    counts=Counter(i['kind'] for i in issues)
    body='<section class="panel content-panel"><h2>Vault health</h2><p>Diagnostics are suggestions for review. Examples and scraped text can contain intentional unresolved links. Source files are preserved.</p><p><a href="/library">Library</a></p><p>'+ ' · '.join(f'<a href="?kind={esc(k)}">{esc(k)}: {n}</a>' for k,n in sorted(counts.items()))+'</p>'
    body+='<p><a href="/library/jobs">Index jobs and retry controls</a> · <a href="/library/publications">Review publication conflicts</a> · <a href="/library/pdf">PDF extraction queue</a></p><h3>Local index jobs</h3>'
    for job in jobs:
        body+='<p>'+esc(job['mode'])+' · '+esc(job['state'])+f" · {job['seen']:,} seen · {job['changed']:,} changed · {job['failed']:,} failures"+' · '+esc(job['completed_at'] or job['started_at'] or job['created_at'])+'</p>'
        if job['error']:body+='<p role="status">'+esc(job['error'])+'</p>'
    for error in errors:body+='<p>'+esc(error['path'])+': '+esc(error['category'])+'</p>'
    for row in publication:body+='<p>Source publication '+esc(row['publication_state'])+f": {row['count']:,}"+'</p>'
    for op in operations:body+='<p role="status">Rename '+esc(op['state'])+': '+esc(op['old_path'])+' → '+esc(op['new_path'])+' '+esc(op['error'] or 'Recovery pending')+'</p>'
    body+=f'<p>{len(visible):,} findings · page {page} · <a href="?dismissed=1">Include dismissed findings</a></p>'
    for issue in visible[(page-1)*50:page*50]:
        body+=f'<article class="library-result"><h3><a href="{esc(note_url(issue["path"]))}">{esc(issue["path"])}</a></h3><p>{esc(issue["kind"])}: {esc(issue["detail"])}</p>'
        if issue.get('target'):
            body+='<p>Suggested filename: '+esc(issue['target'])+'</p>'
            body+='<a class="button" href="/library/repair-preview?'+esc(urlencode({'path':issue['path']}))+'">Preview filename repair</a>' 
        body+=f'<form method="post" action="/library/health/dismiss">{hidden(request)}<input type="hidden" name="path" value="{esc(issue["path"])}"><input type="hidden" name="finding" value="{issue["finding"]}"><button name="action" value="{"reopen" if issue["dismissed"] else "dismiss"}">{"Reopen finding" if issue["dismissed"] else "Dismiss this revision’s finding"}</button></form></article>'
    args=dict(kind=kind,dismissed=request.query_params.get('dismissed',''))
    if page>1:body+='<a href="?'+esc(urlencode({**args,'page':page-1}))+'">Previous</a> '
    if len(visible)>page*50:body+='<a href="?'+esc(urlencode({**args,'page':page+1}))+'">Next</a>'
    body+='<p>For capture failures, open Page scraping to exclude or requeue a URL. For other findings, open the note to review its contents and edit in Obsidian.</p><a class="button" href="/history/capture">Capture controls</a></section>'
    return render_page(body,'Vault health','/library/health')


@router.get('/library/questions',response_class=HTMLResponse)
def research_questions(request:Request):
    rows=library.documents();project=request.query_params.get('project','')[:100]
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    requested=request.query_params.get('state','open')
    with connect() as db:statuses={r['id']:r for r in db.execute('SELECT * FROM library_question_status').fetchall()}
    from app.library_identity import question_id
    groups={}
    for row in rows:
        if project and row['effective_project']!=project:continue
        for question in row['metadata'].get('questions',[]):
            key=(row['effective_project'],library.normalize_match_text(question))
            identity=question_id(row['document_id'],question)
            status=statuses.get(identity,{'state':'open','answer_path':''})
            item=groups.setdefault(key,dict(question=question,row=row,id=identity,status=status,sources=[]))
            item['sources'].append(row)
            if status['state']=='open':item.update(row=row,id=identity,status=status)
    entries=[item for item in groups.values() if requested=='all' or item['status']['state']==requested]
    choices={r['title']+' · '+str(r['document_id'])[:8]:r for r in rows}
    body='<section class="panel content-panel"><h2>Research questions</h2><p>Questions are grouped by project and matching text. Pick an indexed answer by title; source paths are preserved.</p><p><a href="/library/questions">Open</a> · <a href="?state=all">All states</a></p><datalist id="answer-notes">'+''.join('<option value="'+esc(label)+'"></option>' for label in sorted(choices))+'</datalist>'
    body+=f'<p>{len(entries):,} questions · page {page}</p>'
    for item in entries[(page-1)*30:page*30]:
        row=item['row'];status=item['status'];identity=item['id']
        body+='<article class="library-result"><h3>'+esc(item['question'])+'</h3><p>'+esc(status['state'])+' · '+esc(row['effective_project'])+'</p><ul>'+''.join('<li><a href="'+esc(note_url(r['path']))+'">'+esc(r['title'])+'</a></li>' for r in item['sources'])+'</ul>'
        if status.get('answer_path'):body+='<p><a href="'+esc(note_url(status['answer_path']))+'">Saved answer</a></p>'
        body+=f'<form method="post" action="/library/questions/resolve">{hidden(request)}<input type="hidden" name="id" value="{identity}"><label for="answer-{identity}">Find answer note by title</label><input id="answer-{identity}" name="answer_note" list="answer-notes" maxlength="400"><button name="state" value="resolved">Resolve with answer</button><button name="state" value="dismissed">Dismiss</button><button name="state" value="open">Reopen</button></form><p><a href="'+esc('/vault/wiki?'+urlencode(dict(document_id=str(row['document_id']),scope='archive' if row['evidence_scope']=='archive' else 'all',project=row['effective_project'])))+'">Ask about the source</a></p></article>'
    args=dict(state=requested,project=project)
    if page>1:body+='<a href="?'+esc(urlencode({**args,'page':page-1}))+'">Previous</a> '
    if len(entries)>page*30:body+='<a href="?'+esc(urlencode({**args,'page':page+1}))+'">Next</a>'
    return render_page(body+'</section>','Research questions','/library/questions')


@router.post('/library/questions/resolve')
async def resolve_question(request:Request):
    data=await form(request);identity=data.get('id',[''])[0];answer=data.get('answer_path',[''])[0];state=data.get('state',[''])[0]
    rows=library.documents()
    from app.library_identity import question_id
    identities={question_id(r['document_id'],q):(r,q) for r in rows for q in r['metadata'].get('questions',[])}
    if identity not in identities or state not in ('open','resolved','dismissed'):raise HTTPException(400,'Unknown research question')
    if data.get('answer_note',[''])[0]:
        choices={r['title']+' · '+str(r['document_id'])[:8]:r['path'] for r in rows}
        answer=choices.get(data['answer_note'][0],'')
    if state=='resolved' and answer not in {r['path'] for r in rows}:raise HTTPException(400,'Choose an indexed answer note by title')
    if state!='resolved':answer=''
    selected,question=identities[identity]
    grouped=[key for key,(row,q) in identities.items() if row['effective_project']==selected['effective_project'] and library.normalize_match_text(q)==library.normalize_match_text(question)]
    with connect() as db:
        for key in grouped:
            db.execute('''INSERT INTO library_question_status(id,state,answer_path) VALUES (%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET state=excluded.state,answer_path=excluded.answer_path,updated_at=now()''',(key,state,answer))
    return RedirectResponse('/library/questions',303)


@router.get('/library/jobs',response_class=HTMLResponse)
def index_jobs(request:Request):
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    section=request.query_params.get('section','jobs')
    if section not in ('jobs','errors','renames'):raise HTTPException(400,'Unknown job section')
    with connect() as db:
        last_success=db.execute("SELECT completed_at,seen FROM library_index_jobs WHERE state='succeeded' ORDER BY completed_at DESC LIMIT 1").fetchone()
        current=db.execute("SELECT id,mode,seen,changed,failed FROM library_index_jobs WHERE state='running' ORDER BY id DESC LIMIT 1").fetchone()
        heartbeat=db.execute("SELECT last_seen,last_seen>now()-interval '120 seconds' AS fresh FROM service_status WHERE service='library-worker'").fetchone()
        if section=='jobs':rows=db.execute('SELECT * FROM library_index_jobs ORDER BY id DESC LIMIT 31 OFFSET %s',((page-1)*30,)).fetchall()
        elif section=='errors':rows=db.execute('SELECT * FROM library_index_errors ORDER BY updated_at DESC,path LIMIT 31 OFFSET %s',((page-1)*30,)).fetchall()
        else:rows=db.execute("SELECT * FROM library_operations WHERE state<>'complete' ORDER BY created_at,id LIMIT 31 OFFSET %s",((page-1)*30,)).fetchall()
    body='<section class="panel content-panel"><h2>Index jobs and recovery</h2><p><a href="?section=jobs">Jobs</a> · <a href="?section=errors">File errors</a> · <a href="?section=renames">Rename recovery</a></p><p>Retries preserve last good evidence and original files. Queued scans wait while local indexing is paused. Fix file permissions or conflicts before retrying.</p>'
    from zoneinfo import ZoneInfo
    timestamp=lambda value:value.astimezone(ZoneInfo('Indian/Maldives')).strftime('%Y-%m-%d %H:%M:%S UTC+05:00') if value else 'Not recorded'
    body+='<p>Last successful scan: '+esc(timestamp(last_success['completed_at']) if last_success else 'None recorded')+'</p>'
    if current:body+='<p role="status">Running job '+str(current['id'])+' · '+esc(current['mode'])+' · '+str(current['seen'])+' seen · '+str(current['changed'])+' changed · '+str(current['failed'])+' failures. Progress survives an interrupted scan.</p>'
    body+='<p role="status">Local worker: '+('recent heartbeat' if heartbeat and heartbeat['fresh'] else 'heartbeat stale or unavailable')+'. '+esc(timestamp(heartbeat['last_seen']) if heartbeat else 'Not recorded')+'</p>'
    for row in rows[:30]:
        body+='<article class="library-result">'
        if section=='jobs':
            body+='<h3>Job '+str(row['id'])+' · '+esc(row['mode'])+' · '+esc(row['state'])+'</h3><p>'+str(row['seen'])+' seen · '+str(row['changed'])+' changed · '+str(row['failed'])+' failures</p><p>'+esc(row['error'] or '')+'</p><p>Queued '+esc(timestamp(row['created_at']))+' · completed '+esc(timestamp(row['completed_at']))+'</p>'
            if row['state']=='failed':body+='<form method="post" action="/library/jobs/retry">'+hidden(request)+'<input type="hidden" name="id" value="'+str(row['id'])+'"><button>Queue another scan</button></form>'
        elif section=='errors':
            body+='<h3>'+esc(row['path'])+'</h3><p>'+esc(row['category'])+'</p><form method="post" action="/library/jobs/retry">'+hidden(request)+'<input type="hidden" name="path" value="'+esc(row['path'])+'"><button>Queue full scan to retry file</button></form>'
        else:
            body+='<h3>'+esc(row['old_path'])+' → '+esc(row['new_path'])+'</h3><p>'+esc(row['state'])+' · '+esc(row['error'] or 'Recovery pending')+'</p><p>Recovery uses the journaled source hash and never overwrites a destination. Changed files require a new reviewed repair.</p>'
            if row['state']=='conflict':body+='<form method="post" action="/library/jobs/retry-rename">'+hidden(request)+'<input type="hidden" name="id" value="'+str(row['id'])+'"><button>Retry journal recovery</button></form>'
        body+='</article>'
    if not rows:body+='<p>No records in this section.</p>'
    if page>1:body+='<a href="?'+esc(urlencode({'section':section,'page':page-1}))+'">Previous</a> '
    if len(rows)>30:body+='<a href="?'+esc(urlencode({'section':section,'page':page+1}))+'">Next</a>'
    return render_page(body+'</section>','Index jobs and recovery','/library/health')


@router.post('/library/jobs/retry')
async def retry_index_job(request:Request):
    data=await form(request)
    with connect() as db:
        if data.get('path',[''])[0]:
            row=db.execute('SELECT path FROM library_index_errors WHERE path=%s',(data['path'][0],)).fetchone();mode='full'
        else:
            try:identity=int(data.get('id',[''])[0])
            except ValueError:raise HTTPException(400,'Invalid job')
            row=db.execute("SELECT mode FROM library_index_jobs WHERE id=%s AND state='failed'",(identity,)).fetchone();mode=row['mode'] if row else 'incremental'
        if not row:raise HTTPException(409,'Failure no longer needs retry')
        from app.library_index import request_scan
        request_scan(mode,db_connect=lambda:connect())
    return RedirectResponse('/library/jobs',303)


@router.post('/library/jobs/retry-rename')
async def retry_rename(request:Request):
    import uuid
    data=await form(request)
    try:identity=uuid.UUID(data.get('id',[''])[0])
    except ValueError:raise HTTPException(400,'Invalid rename journal')
    with connect() as db:
        if not db.execute('SELECT pg_try_advisory_xact_lock(418245) AS locked').fetchone()['locked']:raise HTTPException(409,'Index or rename is busy; retry shortly')
        row=db.execute("SELECT * FROM library_operations WHERE id=%s AND state='conflict' FOR UPDATE",(identity,)).fetchone()
        if not row:raise HTTPException(409,'Rename no longer needs retry')
        from app.library_identity import finish_operation
        try:finish_operation(db,row,Path('/vault'))
        except (ValueError,OSError):raise HTTPException(409,'Rename still conflicts; originals retained')
    return RedirectResponse('/library/jobs?section=renames',303)


@router.get('/library/repair-preview',response_class=HTMLResponse)
def repair_preview(request:Request):
    path=request.query_params.get('path','');new=library.repaired_name(path)
    if not new:raise HTTPException(400,'No safe filename recovery available')
    try:
        from app.library_index import snapshot
        source=library.safe_path(path);destination=library.safe_path(new)
        data,_=snapshot(source,library.MAX_NOTE)
        if len(data)>library.MAX_NOTE:raise ValueError('Source exceeds limit')
    except (ValueError,OSError):raise HTTPException(409,'Source or destination unavailable; originals retained')
    rows=library.documents();paths={r['path'] for r in rows};aliases=library.path_aliases()
    inbound=[r['path'] for r in rows if any(path in library.resolve_link(r['path'],link,paths,aliases) for link in r['metadata'].get('links',[]))]
    conflict=destination.exists()
    with connect() as db:
        from app.library_identity import preflight
        try:preflight(db,path,new)
        except ValueError:conflict=True
        indexed=db.execute('SELECT path FROM library_documents WHERE path=%s AND present',(path,)).fetchone()
        connections=db.execute('SELECT count(*) AS count FROM library_connections WHERE source=%s OR target=%s',(path,path)).fetchone()['count']
        answers=db.execute('SELECT count(*) AS count FROM library_question_status WHERE answer_path=%s',(path,)).fetchone()['count']
    if not indexed:raise HTTPException(409,'Scan this source before repairing its filename')
    body='<section class="panel content-panel"><h2>Preview filename repair</h2><p>'+esc(path)+' → '+esc(new)+'</p>'
    body+='<p>'+str(len(inbound))+' notes link to this source · '+str(connections)+' accepted connections · '+str(answers)+' resolved answers reference it.</p>'
    body+='<p>App relationships and historical path aliases follow the rename. Existing Markdown links are retained; review those links in Obsidian after repair. Exact saved citations remain accessible.</p>'
    for referring in inbound[:50]:body+='<p><a href="'+esc(note_url(referring))+'">'+esc(referring)+'</a></p>'
    if len(inbound)>50:body+='<p>Showing the first 50 referring notes.</p>'
    if conflict:body+='<p role="status">Destination file or app records conflict. Resolve the collision before retrying; neither file will be overwritten.</p>'
    else:body+='<form method="post" action="/library/repair-name">'+hidden(request)+'<input type="hidden" name="path" value="'+esc(path)+'"><input type="hidden" name="expected_hash" value="'+hashlib.sha256(data).hexdigest()+'"><button>Apply this filename repair</button></form>'
    return render_page(body+'</section>','Preview filename repair','/library/health')


@router.post('/library/repair-name')
async def repair_name(request:Request):
    data=await form(request);path=data.get('path',[''])[0];new=library.repaired_name(path)
    if not new:raise HTTPException(400,'No safe filename recovery available')
    expected=data.get('expected_hash',[''])[0]
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise HTTPException(400,'Preview the current filename repair before applying it')
    try:
        from app.library_identity import rename_note
        rename_note(path,new,expected_hash=expected)
    except (ValueError,OSError):raise HTTPException(409,'Filename repair conflict; check vault health before retrying')
    return RedirectResponse('/library/health?kind=encoding',303)


@router.get('/library/citation',response_class=HTMLResponse)
def show_citation(request:Request):
    import uuid
    try:identity=uuid.UUID(request.query_params.get('question',''))
    except ValueError:raise HTTPException(400,'Invalid answer identity')
    source=request.query_params.get('source','')
    with connect() as db:
        answer=db.execute('SELECT citations FROM wiki_questions WHERE id=%s',(identity,)).fetchone()
        citation=next((c for c in (answer or {}).get('citations',[]) if c['id']==source),None)
        if not citation:raise HTTPException(404,'Citation unavailable')
        current=db.execute('SELECT * FROM library_documents WHERE document_id::text=%s AND present',(citation.get('document_id',''),)).fetchone()
    body='<section class="panel content-panel"><h2>'+esc(citation['title'])+'</h2><p>Evidence retained with the answer. Coordinates refer to the cited revision.</p>'
    body+='<p>'+('Page '+str(citation['page_number'])+' · ' if citation.get('page_number') else '')+esc(citation['path'])+' · '+esc(citation['heading'])+f" · lines {citation['start_line']}–{citation['end_line']}"+'</p>'
    if 'excerpt' in citation:
        body+='<pre class="note-content">'+esc(citation['excerpt'])+'</pre><p>Revision: '+esc(citation.get('revision',''))+'</p>'
    else:body+='<p>This historical answer predates retained excerpts. Its exact evidence is unavailable.</p>'
    if current:
        changed=current['content_hash']!=citation.get('revision')
        body+='<p>'+('Current source has changed.' if changed else 'Current catalog revision matches.')+' <a href="/library/note?'+esc(urlencode({'id':str(current['document_id'])}))+'">Open current source</a></p>'
    else:body+='<p>Current source is unavailable. The retained excerpt remains accessible.</p>'
    return render_page(body+'</section>','Retained evidence','/library')


@router.post('/library/connections/remove')
async def remove_connection(request:Request):
    data=await form(request);source=data.get('source',[''])[0];target=data.get('target',[''])[0]
    from app.connection_export import queue,process_one
    with connect() as db:
        db.execute('DELETE FROM library_connections WHERE source=%s AND target=%s',(source,target));queue(db,source)
    process_one()
    return RedirectResponse(note_url(source),303)


@router.post('/library/health/dismiss')
async def dismiss_finding(request:Request):
    data=await form(request);path=data.get('path',[''])[0];finding=data.get('finding',[''])[0];action=data.get('action',[''])[0]
    rows=library.documents();row=next((r for r in rows if r['path']==path),None)
    if not row or action not in ('dismiss','reopen'):raise HTTPException(400,'Unknown finding')
    known={hashlib.sha256((i['kind']+'\0'+i['detail']).encode()).hexdigest() for i in library.health(rows) if i['path']==path}
    if finding not in known:raise HTTPException(409,'Finding changed; reload vault health')
    with connect() as db:
        if action=='dismiss':db.execute('INSERT INTO library_health_dismissals(document_id,revision,finding) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(row['document_id'],row['content_hash'],finding))
        else:db.execute('DELETE FROM library_health_dismissals WHERE document_id=%s AND revision=%s AND finding=%s',(row['document_id'],row['content_hash'],finding))
    return RedirectResponse('/library/health',303)


@router.get('/library/projects',response_class=HTMLResponse)
def project_workspace(request:Request):
    rows=library.documents();projects=sorted({r['effective_project'] for r in rows if r['effective_project']});project=request.query_params.get('project','')[:100]
    body='<section class="panel content-panel"><h2>Project workspace</h2><ul>'+''.join('<li><a href="?'+esc(urlencode({'project':p}))+'">'+esc(p)+'</a></li>' for p in projects)+'</ul>'
    if project:
        notes=[r for r in rows if r['effective_project']==project]
        body+='<h3>'+esc(project)+'</h3><p>'+str(len(notes))+' notes · '+str(sum(r['effective_reviewed'] for r in notes))+' reviewed</p><p><a href="/library?'+esc(urlencode({'project':project}))+'">Search project</a> · <a href="/library/questions?'+esc(urlencode({'project':project}))+'">Project questions</a> · <a href="/vault/wiki?'+esc(urlencode({'project':project}))+'">Ask project sources</a></p><ul>'
        for row in sorted(notes,key=lambda r:r['indexed_at'],reverse=True)[:50]:body+='<li><a href="'+esc(note_url(row['path']))+'">'+esc(row['title'])+'</a> · '+('Reviewed' if row['effective_reviewed'] else 'Draft')+'</li>'
        body+='</ul>'
    else:body+='<p>Assign a project from a note’s library preferences to begin.</p>'
    return render_page(body+'</section>','Projects','/library/projects')
