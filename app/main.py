import html
import os
import secrets
from urllib.parse import parse_qs
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.db import connect
from app.auth import COOKIE, TTL, credentials_valid, issue_session, session_valid

app = FastAPI(title="Forgetful Me", docs_url=None, redoc_url=None, openapi_url=None)
security = HTTPBasic(auto_error=False)


@app.middleware("http")
async def prevent_caching(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def authorized(request, credentials):
    return session_valid(request.cookies.get(COOKIE)) or (
        credentials is not None and credentials_valid(credentials.username, credentials.password)
    )


def authenticate(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]):
    if not authorized(request, credentials):
        raise HTTPException(401, "Authentication required")


def login_page(error=""):
    csrf = secrets.token_hex(32)
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Forgetful Me</title>
<style>body{{font:16px system-ui;background:#f7f5ef;color:#253831;margin:60px auto;padding:24px;max-width:440px}}form{{background:white;padding:28px;border-radius:12px}}label{{display:block;margin:16px 0 6px}}input{{box-sizing:border-box;width:100%;padding:12px;font:inherit;border:1px solid #a7b6ad;border-radius:6px}}button{{margin-top:24px;padding:12px 20px;background:#253831;color:white;border:0;border-radius:6px;font:inherit}}p{{line-height:1.6}}</style>
<h1>Forgetful Me</h1><p>Sign in to your browsing archive.</p><form method="post" action="/login"><input type="hidden" name="csrf" value="{csrf}"><p role="alert">{html.escape(error)}</p><label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="256"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024"><button type="submit">Sign in</button></form><p>Use the credentials from your local .env file.</p></html>"""
    response = HTMLResponse(page, status_code=401 if error else 200)
    response.set_cookie("forgetfulme_csrf", csrf, httponly=True, samesite="strict", max_age=600)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/login")
def login():
    return login_page()


@app.post("/login")
async def submit_login(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            raise HTTPException(413, "Login request too large")
    data = parse_qs(body.decode("utf-8", errors="replace"))
    csrf = data.get("csrf", [""])[0]
    cookie = request.cookies.get("forgetfulme_csrf", "")
    if not csrf or not cookie or not secrets.compare_digest(csrf.encode(), cookie.encode()):
        raise HTTPException(403, "Please reload the login page and try again")
    if not credentials_valid(data.get("username", [""])[0], data.get("password", [""])[0]):
        return login_page("Incorrect username or password.")
    response = RedirectResponse("/", status_code=303)
    # Caddy overwrites X-Forwarded-Proto; the app has no publicly exposed port.
    response.set_cookie(COOKIE, issue_session(), httponly=True, samesite="strict",
                        secure=request.headers.get("x-forwarded-proto") == "https", max_age=TTL)
    response.delete_cookie("forgetfulme_csrf")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with connect() as db:
            db.execute("SELECT 1 FROM jobs LIMIT 1")
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


def snapshot():
    with connect() as db:
        services = db.execute("SELECT service, last_seen, last_seen > now() - interval '90 seconds' AS healthy FROM service_status ORDER BY service").fetchall()
        jobs = db.execute("SELECT count(*) FILTER (WHERE completed_at IS NULL) AS pending, count(*) FILTER (WHERE completed_at IS NOT NULL) AS completed FROM jobs").fetchone()
    return {"services": services, "jobs": jobs}


@app.get("/api/status", dependencies=[Depends(authenticate)])
def status():
    return snapshot()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]):
    if not authorized(request, credentials):
        return RedirectResponse("/login", status_code=303)
    state = snapshot()
    rows = "".join(f"<tr><td>{html.escape(s['service'])}</td><td>{'Healthy' if s['healthy'] else 'Stale'}</td><td>{html.escape(str(s['last_seen']))}</td></tr>" for s in state["services"])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forgetful Me</title>
<style>body{{font:16px system-ui;margin:60px auto;padding:0 24px;max-width:900px;background:#f7f5ef;color:#253831}}h1{{font-size:40px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:14px;border-bottom:1px solid #ccd4ce}}section{{background:white;padding:24px;border-radius:12px;margin:24px 0}}p{{line-height:1.6}}</style>
<h1>Forgetful Me</h1><p>Your browsing archive starts here.</p><section><h2>Stack status</h2><p>Webapp and database connected.</p><table><tr><th>Service</th><th>Status</th><th>Last heartbeat (UTC)</th></tr>{rows}</table><p>Pending jobs: {state['jobs']['pending']} · Completed jobs: {state['jobs']['completed']}</p></section>
<section><h2>Next steps</h2><p>The Docker foundation is running. Browser ingestion, history search, and Obsidian delivery are planned and are not available yet.</p></section></html>"""
