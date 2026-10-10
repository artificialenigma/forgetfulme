"""Retryable, atomic exports to a dedicated managed vault folder."""
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
from app.db import connect
from app.publication import publish_note

LOCAL = ZoneInfo('Indian/Maldives')


def text(value):
    value = ' '.join(str(value).split())
    for character in '\\`*_{}[]<>#|':
        value = value.replace(character, '\\' + character)
    return value


def export_pending(vault=Path('/vault')):
    with connect() as db:
        from app.ingestion_policy import enabled, safe_display_url
        if not enabled('history_exports',db):
            return 0
        # Serialize workers; if a file write succeeds but the transaction fails, retry
        # republishes the same immutable revision rather than duplicating visits.
        if not db.execute('SELECT pg_try_advisory_xact_lock(418241) AS locked').fetchone()['locked']:
            return 0
        pending = db.execute('SELECT id,visited_at FROM browser_visits WHERE obsidian_exported_at IS NULL ORDER BY id LIMIT 1000').fetchall()
        groups = list(dict.fromkeys((row['visited_at'].astimezone(LOCAL).date(), row['id']//1000) for row in pending))[:8]
        exported = 0
        for day, bucket in groups:
            start = datetime.combine(day, time.min, LOCAL)
            rows = db.execute('SELECT v.id,v.url,v.title,v.visited_at,d.name FROM browser_visits v JOIN browser_devices d ON d.id=v.device_id WHERE v.id >= %s AND v.id < %s AND visited_at >= %s AND visited_at < %s ORDER BY visited_at,id', (bucket*1000,(bucket+1)*1000,start,start+timedelta(days=1))).fetchall()
            directory = vault / 'Forgetful Me' / 'Browsing History' / day.strftime('%Y/%m')
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / f'{day.isoformat()}-{bucket:08d} — visits.md'
            lines = [f'# Browsing history · {day.isoformat()}', '', '> Managed by Forgetful Me. This note is rebuilt automatically; keep personal annotations in a separate note.', '', 'Times: Maldives (UTC+05:00).', '']
            for row in rows:
                display = safe_display_url(row['url'])
                url = quote(display, safe=':/?#@!$&\'*=+;,%~-._')
                title_value = row['title'] or display
                if title_value.startswith(('http://','https://')):
                    title_value = safe_display_url(title_value)
                title = text(title_value)
                visited = row['visited_at'].astimezone(LOCAL).strftime('%H:%M:%S')
                lines += [f'- **{visited}** [{title}](<{url}>)', f"  - Source: {text(row['name'])} · Visit ID: {row['id']}"]
            from app.wiki import note_header
            content=note_header('index','Browsing history · '+day.isoformat(),outbound_evidence='none')+'\n'.join(lines)+'\n'
            result=publish_note(destination,content,vault=vault)
            if result['state']!='published':continue
            ids = [row['id'] for row in rows]
            exported += db.execute('UPDATE browser_visits SET obsidian_exported_at=now() WHERE id=ANY(%s) AND obsidian_exported_at IS NULL', (ids,)).rowcount
        return exported
