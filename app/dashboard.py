"""Render a compact operations dashboard using live database data."""
import html
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo
from app.layout import render_page

LOCAL = ZoneInfo('Indian/Maldives')


def timestamp(value):
    return value.astimezone(LOCAL).strftime('%d %b, %H:%M:%S')


def badge(text, tone='good'):
    return f'<span class="badge {tone}"><span class="dot" aria-hidden="true"></span>{html.escape(text)}</span>'


def render(state):
    now = datetime.now(timezone.utc)
    services = {item['service']: item for item in state['services']}
    healthy = sum(bool(services.get(name, {}).get('healthy')) for name in ('worker', 'scheduler'))
    service_rows = []
    for name, description in [('Webapp', 'Dashboard and API'), ('Database', 'Persistent archive storage')]:
        service_rows.append(f'<tr><th scope="row"><strong>{name}</strong><small>{description}</small></th><td>{badge("Connected")}</td><td><span class="muted">Checked on this page load</span></td></tr>')
    for key, name, description in [('worker', 'Worker', 'Captures pages and exports vault notes'), ('scheduler', 'Scheduler', 'Schedules maintenance every minute')]:
        item = services.get(key)
        current = bool(item and item['healthy'])
        seen = timestamp(item['last_seen']) if item else 'No heartbeat received'
        age = max(0, int((now - item['last_seen']).total_seconds())) if item else None
        service_rows.append(f'<tr><th scope="row"><strong>{name}</strong><small>{description}</small></th><td>{badge("Healthy" if current else "Needs attention", "good" if current else "warn")}</td><td><span>{seen}</span><small>{str(age) + " seconds ago" if age is not None else "Waiting for service"}</small></td></tr>')
    recent_rows = []
    for job in state['recent_jobs']:
        complete = job['completed_at'] is not None
        recent_rows.append(f'<tr><td class="job-id">#{job["id"]}</td><th scope="row">Maintenance</th><td>{timestamp(job["created_at"])}</td><td>{badge("Completed" if complete else "Queued", "neutral" if complete else "warn")}</td></tr>')
    if not recent_rows:
        recent_rows.append('<tr><td colspan="4" class="empty">No jobs yet. The scheduler will add the first maintenance job shortly.</td></tr>')
    body = Template((Path(__file__).parent / 'dashboard.html').read_text()).substitute(
        updated=timestamp(now), overview=badge('All services connected' if healthy == 2 else 'Check background services', 'good' if healthy == 2 else 'warn'),
        healthy=str(healthy + 2), pending=f'{state["jobs"]["pending"]:,}', completed=f'{state["jobs"]["completed"]:,}',
        service_rows=''.join(service_rows), job_rows=''.join(recent_rows),
    )

    knowledge=state.get('library',{})
    body='<section class="panel content-panel"><h2>Your knowledge</h2><p>'+str(knowledge.get('searchable',0))+' searchable files · '+str(knowledge.get('imported',0))+' imported notes · '+str(knowledge.get('generated',0))+' generated navigation/history files · '+str(knowledge.get('reviewed',0))+' reviewed · '+str(knowledge.get('questions',0))+' research questions · '+str(knowledge.get('issues',0))+' health findings</p><p><a href="/library">Search library</a> · <a href="/library/questions">Research questions</a> · <a href="/library/health">Review vault health</a></p></section>'+body
    return render_page(body, "Overview", "/", show_heading=False)
