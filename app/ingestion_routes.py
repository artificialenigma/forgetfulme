"""Signed-in ingestion choices, domain rules and reversible queue controls."""
import html
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.browser_history import admin, csrf, form
from app.db import connect
from app.layout import render_page
from app.ingestion_policy import CONTROL_NAMES, controls, normalize_domain, safe_display_url

router = APIRouter()


@router.get('/settings/ingestion', dependencies=[Depends(admin)])
def ingestion_page(request: Request):
    try:page=max(1,min(10000,int(request.query_params.get('page','1'))))
    except ValueError:page=1
    with connect() as db:
        config = controls(db)
        domains = db.execute('SELECT * FROM ingestion_domains ORDER BY domain').fetchall()
        jobs = db.execute("SELECT url_hash,url,state,selected,cancelled,excluded,policy_state,policy_reason,fetched_at,next_attempt_at FROM page_captures ORDER BY (state IN ('pending','retry')) DESC,next_attempt_at LIMIT 51 OFFSET %s",((page-1)*50,)).fetchall()
        counts = db.execute('SELECT state,count(*) AS count FROM page_captures GROUP BY state').fetchall()
        attempts = db.execute("SELECT count(*) AS count FROM capture_attempt_log WHERE started_at>now()-interval '1 hour'").fetchone()['count']
    token = csrf(request)
    hidden = f'<input type="hidden" name="csrf" value="{token}">'
    labels = {'visits':'Store new visits', 'history_exports':'Export visits to the vault',
              'downloads':'Download public pages', 'local_index':'Update local search index', 'ai':'Process content with AI'}
    body = '<section class="panel content-panel"><p>Each stage has its own switch. Inherit preserves your existing automation and AI settings; local search remains usable when indexing is paused. Downloads stop after bounded in-flight work. Disabling visit storage rejects new imports/extension batches and preserves existing visits.</p><form method="post" action="/settings/ingestion/controls">' + hidden
    for name in CONTROL_NAMES:
        override = config[name + '_enabled']
        value = 'inherit' if override is None else 'on' if override else 'off'
        body += f'<label for="{name}">{labels[name]} · currently {"on" if config[name] else "off"}</label><select id="{name}" name="{name}">'
        for option, label in [('inherit','Inherit existing settings'),('on','On'),('off','Off')]:
            body += f'<option value="{option}" {"selected" if value==option else ""}>{label}</option>'
        body += '</select>'
    body += '<label for="capture-mode">New page capture mode</label><select id="capture-mode" name="capture_mode">'
    for value, label in [('all','All permitted public pages'),('selected','Only pages selected below'),('allowlisted','Only explicitly allowed domains')]:
        body += f'<option value="{value}" {"selected" if config["capture_mode"]==value else ""}>{label}</option>'
    body += '</select>'
    for name, label, maximum in [('requests_per_minute','Capture starts per minute',60),('hourly_budget','Capture starts per hour',1000),('domain_delay_seconds','Minimum seconds between captures on a domain',3600)]:
        body += f'<label for="{name}">{label}</label><input type="number" id="{name}" name="{name}" min="1" max="{maximum}" required value="{config[name]}">'
    body += '<button>Save ingestion choices</button></form></section><section class="panel content-panel"><h2>Site policies</h2><p>A blocked domain also blocks its selected pages. Any matching block takes precedence over allow rules. Subdomains match only when selected.</p><form method="post" action="/settings/ingestion/domain">' + hidden
    body += '<label for="domain">Domain</label><input id="domain" name="domain" maxlength="253" placeholder="example.com" required><label for="rule">Rule</label><select id="rule" name="rule"><option value="block">Block</option><option value="allow">Allow</option></select><label><input type="checkbox" name="include_subdomains" value="1" checked> Include subdomains</label><label for="delay">Optional domain delay in seconds</label><input type="number" id="delay" name="delay_seconds" min="1" max="3600"><button name="action" value="save">Save rule</button></form><ul>'
    for domain in domains:
        body += '<li>' + html.escape(domain['domain']) + ' · ' + domain['rule'] + (' including subdomains' if domain['include_subdomains'] else '')
        body += f'<form method="post" action="/settings/ingestion/domain">{hidden}<input type="hidden" name="domain" value="{html.escape(domain["domain"],quote=True)}"><button name="action" value="remove">Remove rule</button></form></li>'
    body += '</ul></section><section class="panel content-panel"><h2>Capture queue</h2>'
    body += '<p>' + ' · '.join(f'{html.escape(row["state"])}: {row["count"]:,}' for row in counts) + f' · {attempts:,}/{config["hourly_budget"]:,} capture starts this hour.</p>'
    body += '<p>Showing up to 50 queue/results rows. Selection permits a page in selected mode. Cancel stops future attempts and preserves stored evidence; retry explicitly schedules a new attempt. Inclusion/exclusion is managed on <a href="/history/capture">capture status</a>. Exported URLs hide credential parameters; original visit/capture identities remain stored.</p><div class="table-scroll"><table><thead><tr><th>Page</th><th>State</th><th>Actions</th></tr></thead><tbody>'
    for job in jobs[:50]:
        url = safe_display_url(job['url'])
        state = 'cancelled' if job['cancelled'] else 'excluded' if job['excluded'] else 'downloads paused' if not config['downloads'] and job['state'] in ('pending','retry') else job['policy_reason'] or job['policy_state']
        body += '<tr><td>' + html.escape(url) + '</td><td>' + html.escape(state) + ' · ' + html.escape(job['state']) + '</td><td>'
        body += f'<form method="post" action="/settings/ingestion/queue">{hidden}<input type="hidden" name="id" value="{job["url_hash"]}"><button name="action" value="{"deselect" if job["selected"] else "select"}">{"Deselect" if job["selected"] else "Select"}</button><button name="action" value="cancel">Cancel future attempts</button><button name="action" value="retry">Retry selected page</button></form></td></tr>'
    body += '</tbody></table></div>'
    if page>1:body+='<a href="?page='+str(page-1)+'">Previous</a> '
    if len(jobs)>50:body+='<a href="?page='+str(page+1)+'">Next</a>'
    body+='</section>'
    return HTMLResponse(render_page(body,'Ingestion controls','/settings/ingestion'))


@router.post('/settings/ingestion/controls', dependencies=[Depends(admin)])
async def save_controls(request: Request):
    data = await form(request)
    values = {}
    for name in CONTROL_NAMES:
        value = data.get(name,[''])[0]
        if value not in ('inherit','on','off'):
            raise HTTPException(400,'Choose a value for every ingestion stage')
        values[name] = None if value == 'inherit' else value == 'on'
    mode = data.get('capture_mode',[''])[0]
    if mode not in ('all','selected','allowlisted'):
        raise HTTPException(400,'Choose a capture mode')
    limits = []
    try:
        for name, maximum in [('requests_per_minute',60),('hourly_budget',1000),('domain_delay_seconds',3600)]:
            value = int(data.get(name,[''])[0])
            if not 1 <= value <= maximum:
                raise ValueError()
            limits.append(value)
    except ValueError:
        raise HTTPException(400,'Capture limits are outside the supported range')
    with connect() as db:
        db.execute('''UPDATE ingestion_controls SET visits_enabled=%s,history_exports_enabled=%s,downloads_enabled=%s,
            local_index_enabled=%s,ai_enabled=%s,capture_mode=%s,requests_per_minute=%s,hourly_budget=%s,domain_delay_seconds=%s,updated_at=now() WHERE id=1''',
            (*values.values(),mode,*limits))
        db.execute("UPDATE page_captures SET next_attempt_at=now() WHERE policy_state='waiting' AND NOT cancelled AND NOT excluded")
    return RedirectResponse('/settings/ingestion',303)


@router.post('/settings/ingestion/domain', dependencies=[Depends(admin)])
async def save_domain(request: Request):
    data = await form(request)
    try:
        domain = normalize_domain(data.get('domain',[''])[0])
        action = data.get('action',[''])[0]
        if action not in ('save','remove'):
            raise ValueError('Choose a domain action')
        rule = data.get('rule',['block'])[0]
        delay = data.get('delay_seconds',[''])[0]
        delay = int(delay) if delay else None
        if rule not in ('allow','block') or (delay is not None and not 1 <= delay <= 3600):
            raise ValueError('Check the domain rule and delay')
    except ValueError as error:
        raise HTTPException(400,str(error))
    with connect() as db:
        if action == 'remove':
            db.execute('DELETE FROM ingestion_domains WHERE domain=%s',(domain,))
        else:
            db.execute('INSERT INTO ingestion_domains(domain,rule,include_subdomains,delay_seconds) VALUES (%s,%s,%s,%s) ON CONFLICT(domain) DO UPDATE SET rule=excluded.rule,include_subdomains=excluded.include_subdomains,delay_seconds=excluded.delay_seconds',
                       (domain,rule,'include_subdomains' in data,delay))
        db.execute("UPDATE page_captures SET next_attempt_at=now() WHERE policy_state='waiting' AND NOT cancelled AND NOT excluded")
    return RedirectResponse('/settings/ingestion',303)


@router.post('/settings/ingestion/queue', dependencies=[Depends(admin)])
async def queue_action(request: Request):
    data = await form(request)
    identity = data.get('id',[''])[0]
    action = data.get('action',[''])[0]
    if not re.fullmatch(r'[a-f0-9]{64}',identity) or action not in ('select','deselect','cancel','retry'):
        raise HTTPException(400,'Choose a valid queue action')
    with connect() as db:
        job = db.execute('SELECT excluded FROM page_captures WHERE url_hash=%s FOR UPDATE',(identity,)).fetchone()
        if not job:
            raise HTTPException(404,'Capture not found')
        if action == 'retry':
            if job['excluded']:
                raise HTTPException(400,'Include the source before retrying it')
            db.execute("UPDATE page_captures SET selected=true,cancelled=false,state='pending',attempts=0,error=NULL,next_attempt_at=now(),policy_state='queued',policy_reason=NULL WHERE url_hash=%s",(identity,))
        elif action == 'cancel':
            db.execute("UPDATE page_captures SET cancelled=true,policy_state='cancelled',policy_reason='Cancelled explicitly' WHERE url_hash=%s",(identity,))
        else:
            db.execute("UPDATE page_captures SET selected=%s,next_attempt_at=now(),policy_state='queued',policy_reason=NULL WHERE url_hash=%s",(action=='select',identity))
    return RedirectResponse('/settings/ingestion',303)
