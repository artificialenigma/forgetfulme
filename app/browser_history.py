import hashlib
import html
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from app.db import connect
from app.auth import COOKIE, session_valid, signature

router = APIRouter()


def admin(request: Request):
    if not session_valid(request.cookies.get(COOKIE)):
        raise HTTPException(401, "Sign in to manage browser devices")


def page(body):
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Browser history · Forgetful Me</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;background:#f7f5ef;color:#253831}a{color:#24644e}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}input,button{padding:10px;font:inherit}code{overflow-wrap:anywhere}small{color:#52645c}</style><a href="/">← Dashboard</a> · <a href="/devices">Devices</a> · <a href="/history">History</a>' + body + '</html>')


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
    body += f'<form method="post"><input name="csrf" type="hidden" value="{token}"><input name="name" placeholder="Laptop Chrome" required maxlength="100"><button>Add device</button></form><table><tr><th>Device</th><th>Last received</th><th>Access</th></tr>'
    for row in rows:
        action = 'Revoked' if row['revoked'] else f'<form method="post" action="/devices/{row["id"]}/revoke"><input type="hidden" name="csrf" value="{token}"><button>Revoke</button></form>'
        body += f'<tr><td>{html.escape(row["name"])}</td><td>{html.escape(str(row["last_seen"] or "Waiting for visits"))}</td><td>{action}</td></tr>'
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
        db.execute('UPDATE browser_devices SET last_seen=now() WHERE id=%s', (device['id'],))
    return {'accepted': len(batch.visits), 'inserted': inserted}


@router.get('/history', dependencies=[Depends(admin)])
def history():
    with connect() as db:
        rows = db.execute('SELECT v.url,v.title,v.visited_at,d.name FROM browser_visits v JOIN browser_devices d ON d.id=v.device_id ORDER BY visited_at DESC LIMIT 200').fetchall()
        count = db.execute('SELECT count(*) AS n FROM browser_visits').fetchone()['n']
    body = f'<h1>Browsing history</h1><p>{count:,} visits stored · showing the latest 200</p><table><tr><th>Page</th><th>Device</th><th>Visited (UTC)</th></tr>'
    for row in rows:
        body += f'<tr><td><a target="_blank" rel="noopener noreferrer" href="{html.escape(row["url"], quote=True)}">{html.escape(row["title"] or row["url"])}</a><br><small>{html.escape(row["url"])}</small></td><td>{html.escape(row["name"])}</td><td>{row["visited_at"].astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S")}</td></tr>'
    return page(body + '</table>' + ('<p>No visits yet. <a href="/devices">Connect a browser</a>.</p>' if not rows else ''))
