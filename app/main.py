import html
import os
import secrets
from urllib.parse import parse_qs
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.dashboard import render
from app.layout import render_page, render_login
from app.db import connect
from app.auth import COOKIE, TTL, credentials_valid, issue_session, session_valid

app = FastAPI(title="Forgetful Me", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
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


def login_destination(value):
    # Only known pages are accepted: never redirect to user-provided external URLs.
    return value if value in {"/", "/devices", "/history", "/history/import", "/history/capture", "/vault", "/vault/wiki"} else "/"


def login_page(error="", destination="/"):
    destination = login_destination(destination)
    csrf = secrets.token_hex(32)
    page = render_login(f"""<h1>Forgetful Me</h1><p>Sign in to your browsing archive.</p><form method="post" action="/login"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="next" value="{destination}"><p role="alert">{html.escape(error)}</p><label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="256"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024"><button type="submit">Sign in</button></form><p>Use the credentials from your local .env file.</p>""")
    response = HTMLResponse(page, status_code=401 if error else 200)
    response.set_cookie("forgetfulme_csrf", csrf, httponly=True, samesite="strict", max_age=600)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/login")
def login(request: Request):
    return login_page(destination=request.query_params.get("next", "/"))


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
        return login_page("Incorrect username or password.", data.get("next", ["/"])[0])
    response = RedirectResponse(login_destination(data.get("next", ["/"])[0]), status_code=303)
    # Caddy overwrites X-Forwarded-Proto; the app has no publicly exposed port.
    response.set_cookie(COOKIE, issue_session(), httponly=True, samesite="strict",
                        secure=request.headers.get("x-forwarded-proto") == "https", max_age=TTL)
    response.delete_cookie("forgetfulme_csrf")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/internal/desktop-auth")
def desktop_auth(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]):
    if not authorized(request, credentials):
        return RedirectResponse("/login", status_code=303)
    origin = request.headers.get("origin")
    scheme = request.headers.get("x-forwarded-proto", "http")
    if origin and origin != f'{scheme}://{request.headers.get("host")}':
        raise HTTPException(403, "Desktop requests must come from this app")
    return {"authenticated": True}


@app.get("/vault", response_class=HTMLResponse)
def vault_desktop(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]):
    if not authorized(request, credentials):
        return RedirectResponse("/login", status_code=303)
    return render_page('<div class="vault-actions"><p>Open <strong>Forgetful Me/Home</strong> in Obsidian for the linked source library, concepts and entities. <a href="/vault/wiki">Knowledge processing and local Q&amp;A →</a></p><a class="button" href="/obsidian/" target="_blank" rel="noopener">Open desktop in a tab ↗</a></div><section class="panel vault-panel"><iframe src="/obsidian/" title="Obsidian vault desktop" allow="clipboard-read; clipboard-write; fullscreen" allowfullscreen></iframe></section>', 'Obsidian vault', '/vault')


@app.get("/api/vault", dependencies=[Depends(authenticate)])
def vault_status():
    vault = Path("/vault")
    with connect() as db:
        progress = db.execute('SELECT count(*) FILTER (WHERE obsidian_exported_at IS NULL) AS pending, count(*) FILTER (WHERE obsidian_exported_at IS NOT NULL) AS exported FROM browser_visits').fetchone()
    with connect() as db:
        captures = db.execute('SELECT state,count(*) AS count FROM page_captures GROUP BY state').fetchall()
    return {"page_captures": {row['state']: row['count'] for row in captures}, "pages_folder": "Forgetful Me/raw", "wiki_home": "Forgetful Me/Home.md", "history_export": progress, "history_folder": "Forgetful Me/Browsing History", "mounted": vault.is_dir(), "name": "Forgetful Me", "markdown_files": sum(1 for p in vault.rglob("*.md") if ".obsidian" not in p.parts), "desktop_url": "/vault"}


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
        recent_jobs = db.execute("SELECT id, kind, created_at, completed_at FROM jobs ORDER BY id DESC LIMIT 8").fetchall()
    return {"services": services, "jobs": jobs, "recent_jobs": recent_jobs}


@app.get("/api/status", dependencies=[Depends(authenticate)])
def status():
    return snapshot()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, credentials: Annotated[HTTPBasicCredentials | None, Depends(security)]):
    if not authorized(request, credentials):
        return RedirectResponse("/login", status_code=303)
    return render(snapshot())


# Device tokens authorize ingestion only, independently of administrator sessions.
from app.browser_history import router as history_router
app.include_router(history_router)

from app.wiki_routes import router as wiki_router
app.include_router(wiki_router)
