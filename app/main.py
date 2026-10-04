import html
import os
import secrets
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.db import connect

app = FastAPI(title="Forgetful Me", docs_url=None, redoc_url=None, openapi_url=None)
security = HTTPBasic()


def authenticate(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    user_ok = secrets.compare_digest(credentials.username.encode(), os.environ["ADMIN_USER"].encode())
    password_ok = secrets.compare_digest(credentials.password.encode(), os.environ["ADMIN_PASSWORD"].encode())
    if not (user_ok and password_ok):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Basic"})


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


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(authenticate)])
def dashboard():
    state = snapshot()
    rows = "".join(f"<tr><td>{html.escape(s['service'])}</td><td>{'Healthy' if s['healthy'] else 'Stale'}</td><td>{html.escape(str(s['last_seen']))}</td></tr>" for s in state["services"])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forgetful Me</title>
<style>body{{font:16px system-ui;margin:60px auto;padding:0 24px;max-width:900px;background:#f7f5ef;color:#253831}}h1{{font-size:40px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:14px;border-bottom:1px solid #ccd4ce}}section{{background:white;padding:24px;border-radius:12px;margin:24px 0}}p{{line-height:1.6}}</style>
<h1>Forgetful Me</h1><p>Your browsing archive starts here.</p><section><h2>Stack status</h2><p>Webapp and database connected.</p><table><tr><th>Service</th><th>Status</th><th>Last heartbeat (UTC)</th></tr>{rows}</table><p>Pending jobs: {state['jobs']['pending']} · Completed jobs: {state['jobs']['completed']}</p></section>
<section><h2>Next steps</h2><p>The Docker foundation is running. Browser ingestion, history search, and Obsidian delivery are planned and are not available yet.</p></section></html>"""
