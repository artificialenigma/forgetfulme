import hashlib
import html
import re
from zoneinfo import ZoneInfo
from app.layout import render_page
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from app.db import connect
from app.auth import COOKIE, session_valid, signature

router = APIRouter()


def admin(request: Request):
    if not session_valid(request.cookies.get(COOKIE)):
        if request.method == "GET":
            raise HTTPException(303, "Sign in required", headers={"Location": "/login?next=" + request.url.path})
        raise HTTPException(401, "Sign in to continue")


def page(body):
    heading = re.search(r'<h1>(.*?)</h1>', body)
    title = html.unescape(heading.group(1)) if heading else 'Your archive'
    if heading:
        body = body[:heading.start()] + body[heading.end():]
    active = '/history/capture' if title == 'Page scraping' else '/devices' if title in {'Browser devices','Device created'} else '/history/import'
    body = re.sub(r'<table(?: [^>]*)?>', lambda match: '<div class="table-scroll">' + match.group(0), body).replace('</table>', '</table></div>')
    return HTMLResponse(render_page('<section class="panel content-panel">' + body + '</section>', title, active))


def csrf(request):
    return signature("devices:" + request.cookies.get(COOKIE, ""))


async def form(request):
    body = await request.body()
    if len(body) > 4096:
        raise HTTPException(413, "Form too large")
    data = parse_qs(body.decode())
    if not secrets.compare_digest(data.get("csrf", [""])[0].encode(), csrf(request).encode()):
        raise HTTPException(403, "Reload this page and try again")
    return data


@router.get("/devices", dependencies=[Depends(admin)])
def devices(request: Request):
    with connect() as db:
        rows = db.execute("SELECT id,name,last_seen,revoked FROM browser_devices ORDER BY created_at DESC").fetchall()
    token = csrf(request)
    body = '<h1>Browser devices</h1><p>Create a separate token for each browser. Install the add-on from the extensions/chrome folder, then enter this app’s address and the token in its settings.</p>'
    body += f'<form method="post"><input name="csrf" type="hidden" value="{token}"><input name="name" placeholder="Laptop Chrome" required maxlength="100"><button>Add device</button></form><table><tr><th>Device</th><th>Last received · UTC+05:00</th><th>Access</th></tr>'
    for row in rows:
        action = 'Revoked' if row['revoked'] else f'<form method="post" action="/devices/{row["id"]}/revoke"><input type="hidden" name="csrf" value="{token}"><button>Revoke</button></form>'
        body += f'<tr><td>{html.escape(row["name"])}</td><td>{html.escape(row["last_seen"].astimezone(ZoneInfo("Indian/Maldives")).strftime("%d %b %Y, %H:%M:%S") if row["last_seen"] else "Waiting for visits")}</td><td>{action}</td></tr>'
    return page(body + '</table>')


@router.post("/devices", dependencies=[Depends(admin)])
async def create_device(request: Request):
    data = await form(request)
    name = data.get("name", [""])[0].strip()
    if not name or len(name) > 100:
        raise HTTPException(400, "Provide a device name up to 100 characters")
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("INSERT INTO browser_devices(id,name,token_hash) VALUES (%s,%s,%s)", (uuid.uuid4(), name, hashlib.sha256(token.encode()).hexdigest()))
    return page(f'<h1>Device created</h1><p>Copy this token into the add-on settings. It is shown only once.</p><code>{token}</code><p><a href="/devices">Back to devices</a></p>')


@router.post("/devices/{device_id}/revoke", dependencies=[Depends(admin)])
async def revoke(device_id: uuid.UUID, request: Request):
    await form(request)
    with connect() as db:
        db.execute("UPDATE browser_devices SET revoked=true WHERE id=%s", (device_id,))
    return RedirectResponse('/devices', status_code=303)


class Visit(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=8192)
    title: str = Field(default="", max_length=1000)
    visited_at: datetime

    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Only HTTP(S) pages without embedded credentials are supported')
        except ValueError:
            raise ValueError('Invalid page URL')
        return value

    @field_validator('visited_at')
    @classmethod
    def valid_time(cls, value):
        if value.tzinfo is None or value.timestamp() < 0 or value.timestamp() > datetime.now(timezone.utc).timestamp() + 300:
            raise ValueError('Invalid visit timestamp')
        return value


class Batch(BaseModel):
    visits: list[Visit] = Field(min_length=1, max_length=100)


@router.post('/api/history/visits')
def ingest(batch: Batch, request: Request):
    auth = request.headers.get('authorization', '')
    if not auth.startswith('Bearer ') or len(auth) > 256:
        raise HTTPException(401, 'Device token required')
    digest = hashlib.sha256(auth[7:].encode()).hexdigest()
    with connect() as db:
        device = db.execute('SELECT id FROM browser_devices WHERE token_hash=%s AND NOT revoked FOR UPDATE', (digest,)).fetchone()
        if not device:
            raise HTTPException(401, 'Invalid or revoked device token')
        inserted = 0
        for visit in batch.visits:
            inserted += db.execute('INSERT INTO browser_visits(device_id,event_id,url,title,visited_at) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(device_id,event_id) DO NOTHING', (device['id'], visit.event_id, visit.url, visit.title, visit.visited_at)).rowcount
            page_url = visit.url.split('#',1)[0]
            db.execute('INSERT INTO page_captures(url_hash,url) VALUES (%s,%s) ON CONFLICT DO NOTHING', (hashlib.sha256(page_url.encode()).hexdigest(),page_url))
        db.execute('UPDATE browser_devices SET last_seen=now() WHERE id=%s', (device['id'],))
    return {'accepted': len(batch.visits), 'inserted': inserted}


@router.get('/history', dependencies=[Depends(admin)])
def history(page_number: int = Query(1, alias="page", ge=1, le=1_000_000)):
    from app.history_view import render_history
    with connect() as db:
        stats = db.execute('SELECT count(*) AS n,count(*) FILTER (WHERE obsidian_exported_at IS NULL) AS pending FROM browser_visits').fetchone()
        count = stats['n']
        pages = max(1, (count + 49) // 50)
        current = min(page_number, pages)
        rows = db.execute('SELECT v.url,v.title,v.visited_at,d.name FROM browser_visits v JOIN browser_devices d ON d.id=v.device_id ORDER BY visited_at DESC,v.id DESC LIMIT 50 OFFSET %s', ((current-1)*50,)).fetchall()
    return HTMLResponse(render_history(rows, count, current, pages, stats['pending']))


@router.get('/history/import', dependencies=[Depends(admin)])
def import_page(request: Request):
    return page(f'''<h1>Import browsing history</h1><p>Upload a UTF-8 CSV or JSON export. Files can contain up to 1,000,000 visits and 100 MiB. The whole file is checked before saving. Safari entries that fail validation can be skipped with a report; uncheck the option to reject the entire file.</p>
<p>CSV columns: <code>url,title,visited_at</code>. JSON: an array of objects with those same fields, <code>{{"visits": [...]}}</code>, or a Safari history export with <code>metadata</code> and <code>history</code> (schema version 1). Generic dates must include a timezone; Safari <code>time_usec</code> is converted automatically.</p>
<pre>url,title,visited_at
https://example.com,Example,2026-10-04T12:30:00Z</pre>
<form method="post" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{csrf(request)}"><p><label>Source name <input name="source" value="Imported history" required maxlength="100"></label></p><p><label>History file <input type="file" name="file" accept=".csv,.json" required></label></p><p><label><input type="checkbox" name="skip_invalid_safari" value="yes" checked> Skip unsupported or invalid Safari entries and report them</label></p><button>Import visits</button></form>
<p>Safari users: select the history JSON file from your browser export, not the ZIP archive. Each history entry becomes one stored visit at its recorded time; aggregate visit counts and load-failure flags are not stored.</p><p>Use the same source name when importing more files from the same browser. Repeated URL/timestamp pairs within that source are skipped. Imports and extension visits use separate identities, so overlapping data from the two methods can appear twice.</p><p>Only the file you select is uploaded; the app cannot read your browser history directly. Chrome users can also use the add-on’s last-30-day importer. URLs may contain personal information; remove unwanted entries before uploading.</p>''')


@router.post('/history/import', dependencies=[Depends(admin)])
async def import_history(request: Request):
    from email import policy
    from email.parser import BytesParser
    from app.history_import import MAX_BYTES, parse_export

    content_type = request.headers.get('content-type', '')
    if not content_type.startswith('multipart/form-data') or '\r' in content_type or '\n' in content_type or len(content_type) > 512:
        raise HTTPException(400, 'Upload a CSV or JSON file using the import form')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BYTES + 65536:
            raise HTTPException(413, 'Upload exceeds 100 MiB')
    message = BytesParser(policy=policy.default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
    if not message.is_multipart():
        raise HTTPException(400, 'Invalid upload')
    fields = {}
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if name in fields or part.is_multipart():
            raise HTTPException(400, 'Invalid or duplicate upload fields')
        fields[name] = (part.get_payload(decode=True) or b'', part.get_filename())
    try:
        supplied_csrf = fields.get('csrf', (b'', None))[0]
        if not secrets.compare_digest(supplied_csrf, csrf(request).encode()):
            raise HTTPException(403, 'Reload the import page and try again')
        source = fields.get('source', (b'', None))[0].decode('utf-8').strip()
        if not source or len(source) > 100:
            raise ValueError('Provide a source name up to 100 characters.')
        content, filename = fields.get('file', (b'', None))
        result = await run_in_threadpool(parse_export, content, filename or '', fields.get('skip_invalid_safari', (b'', None))[0] == b'yes')
        visits = result.visits
    except (ValueError, UnicodeDecodeError) as error:
        return page('<h1>Import could not be completed</h1><p>' + html.escape(str(error)) + '</p><p>No visits were saved. <a href="/history/import">Try again</a>.</p>')
    inserted = await run_in_threadpool(save_import, source, visits)
    report = ''
    if result.skipped:
        report = f'<h2>{result.skipped:,} unsupported or invalid entries skipped</h2><p>Showing the first {len(result.issues)} reasons. No skipped entry was saved.</p><ul>' + ''.join('<li>' + html.escape(issue) + '</li>' for issue in result.issues) + '</ul>'
    return page(f'<h1>Import complete</h1><p>{inserted:,} visits imported. {len(visits)-inserted:,} duplicates skipped.</p>{report}<p><a href="/history">View browsing history</a> · <a href="/history/import">Import another file</a></p>')


def save_import(source, visits):
    device_id = uuid.uuid5(uuid.NAMESPACE_URL, 'forgetfulme:import:' + source.casefold())
    with connect() as db:
        db.execute('INSERT INTO browser_devices(id,name,token_hash,revoked) VALUES (%s,%s,%s,true) ON CONFLICT(id) DO NOTHING', (device_id, 'Import: ' + source, hashlib.sha256(secrets.token_bytes(32)).hexdigest()))
        # Stage validated entries with COPY, then deduplicate in one atomic transaction.
        db.execute('CREATE TEMP TABLE import_visits (event_id text, url text, title text, visited_at timestamptz) ON COMMIT DROP')
        with db.cursor().copy('COPY import_visits (event_id,url,title,visited_at) FROM STDIN') as copy:
            for visit in visits:
                copy.write_row((visit.event_id, visit.url, visit.title, visit.visited_at))
        inserted = db.execute('INSERT INTO browser_visits(device_id,event_id,url,title,visited_at) SELECT %s,event_id,url,title,visited_at FROM import_visits ON CONFLICT(device_id,event_id) DO NOTHING', (device_id,)).rowcount
        db.execute("INSERT INTO page_captures(url_hash,url) SELECT DISTINCT encode(sha256(convert_to(split_part(url,'#',1),'UTF8')),'hex'),split_part(url,'#',1) FROM import_visits ON CONFLICT DO NOTHING")
        db.execute('UPDATE browser_devices SET last_seen=now() WHERE id=%s', (device_id,))
    return inserted


@router.get('/history/capture', dependencies=[Depends(admin)])
def capture_status(request: Request):
    with connect() as db:
        counts = db.execute('SELECT state,count(*) AS count FROM page_captures GROUP BY state ORDER BY state').fetchall()
        recent = db.execute("SELECT url,state,error,note_path,extractor FROM page_captures WHERE state IN ('failed','blocked','retry','complete') ORDER BY (state='complete'),coalesce(fetched_at,next_attempt_at) DESC LIMIT 30").fetchall()
    body = '<h1>Page scraping</h1><p>The worker fetches each unique imported or collected URL, extracts readable public HTML/text into Markdown, and saves successful captures in <strong>Forgetful Me/Pages</strong> in the vault. Visit indexes remain in Browsing History. Crawl4AI is used for HTML extraction when configured, with local extraction as a fallback.</p><p>'
    body += ' · '.join(html.escape(row['state']) + ': ' + f"{row['count']:,}" for row in counts) + '</p>'
    body += '<p>Refresh this page for progress. Local/private pages, robots restrictions, unavailable pages and unreadable content are reported as blocked. Temporary failures retry up to three times. Login-only or JavaScript-only content and PDFs need a separate capture path; browser cookies are never sent. Captures reflect the page now, not necessarily what you saw when visiting.</p>'
    body += f'<div class="capture-actions"><form method="post" action="/history/capture/retry"><input type="hidden" name="csrf" value="{csrf(request)}"><button>Retry failed pages</button></form><a class="button" href="/history/capture">Refresh status</a><a class="button" href="/vault">Open Obsidian vault</a></div><h2>Recent captures and issues</h2><p class="muted">Up to 30 results · issues first, then completed captures.</p><table class="capture-table"><caption class="sr-only">Page capture results and failure reasons</caption><thead><tr><th scope="col">Page</th><th scope="col">Status</th><th scope="col">Capture result</th></tr></thead><tbody>'
    from app.dashboard import badge
    for row in recent:
        url = html.escape(row['url'], quote=True)
        host = html.escape(urlsplit(row['url']).hostname or 'Website')
        tone = {'complete':'good','blocked':'neutral','retry':'warn','failed':'bad'}[row['state']]
        label = {'complete':'Captured','blocked':'Blocked','retry':'Retry queued','failed':'Failed'}[row['state']]
        if row['state'] == 'complete':
            detail = '<strong>Saved to Obsidian</strong><small>' + html.escape(row['extractor'] or 'Markdown extraction') + ' · Forgetful Me/Pages</small>'
            full = html.escape(row['note_path'] or '',quote=True)
        else:
            detail = '<span>' + html.escape(row['error'] or 'Waiting for another attempt') + '</span>'
            full = html.escape(row['error'] or '',quote=True)
        body += f'<tr><td><a class="capture-title" href="{url}" title="{url}" target="_blank" rel="noopener noreferrer">{host}</a><span class="capture-url" title="{url}">{url}</span></td><td class="capture-state">{badge(label,tone)}</td><td class="capture-result" title="{full}">{detail}</td></tr>'
    if not recent:
        body += '<tr><td colspan="3" class="empty">No capture results yet. Queued pages will appear here after the worker processes them.</td></tr>'
    return page(body + '</tbody></table>')



@router.post('/history/capture/retry', dependencies=[Depends(admin)])
async def retry_captures(request: Request):
    await form(request)
    with connect() as db:
        db.execute("UPDATE page_captures SET state='pending',attempts=0,error=NULL,next_attempt_at=now() WHERE state='failed'")
    return RedirectResponse('/history/capture',status_code=303)
