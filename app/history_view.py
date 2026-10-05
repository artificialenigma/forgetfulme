"""Responsive browsing-history presentation with bounded link text."""
import html
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def render_history(rows, total, current, pages, pending=0):
    entries = []
    for row in rows:
        url = row['url']
        host = urlsplit(url).hostname or 'Website'
        title = row['title'] or host
        escaped_url = html.escape(url, quote=True)
        local_time = row['visited_at'].astimezone(ZoneInfo('Indian/Maldives'))
        entries.append(f'''<tr><td class="page-cell"><a class="page-title" href="{escaped_url}" title="{html.escape(title, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a><span class="page-url" title="{escaped_url}">{html.escape(url)}</span></td><td class="source-cell">{html.escape(row['name'])}</td><td class="time-cell"><time datetime="{row['visited_at'].isoformat()}">{local_time.strftime('%d %b %Y')}<span>{local_time.strftime('%H:%M:%S')}</span></time></td></tr>''')
    first = (current-1)*50+1 if total else 0
    last = min(current*50, total)
    previous = f'<a class="button" href="/history?page={current-1}" rel="prev">← Previous</a>' if current > 1 else '<span class="button disabled">← Previous</span>'
    following = f'<a class="button" href="/history?page={current+1}" rel="next">Next →</a>' if current < pages else '<span class="button disabled">Next →</span>'
    content = '<div class="table-wrap"><table><caption class="sr-only">Browsing visits, most recent first</caption><thead><tr><th scope="col">Page</th><th scope="col">Source</th><th scope="col">Visited · UTC+05:00</th></tr></thead><tbody>' + ''.join(entries) + '</tbody></table></div>' if rows else '<div class="empty"><h2>Your browsing history starts here</h2><p>Import a backup or connect a browser to save your visits.</p><a class="button primary" href="/history/import">Import history</a></div>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Browsing history · Forgetful Me</title><link rel="stylesheet" href="/static/history.css"></head><body><a class="skip" href="#main">Skip to history</a><header class="app-header"><a class="brand" href="/">forgetful me<span>.</span></a><nav aria-label="Workspace"><a href="/">Overview</a><a class="active" aria-current="page" href="/history">History</a><a href="/devices">Devices</a><a href="/history/import">Import</a><a href="/vault">Vault</a></nav></header><main id="main"><div class="heading"><div><p class="eyebrow">YOUR PERSONAL ARCHIVE</p><h1>Browsing history</h1><p class="subtitle">{total:,} stored visits · most recent first</p></div><a class="button primary" href="/history/import">Import history</a></div><p class="footnote">Obsidian visit indexes: {total-pending:,} exported · {pending:,} pending. <a href="/history/capture">Page scraping status →</a> <a href="/vault">Open vault →</a> Refresh to update.</p><section class="history-panel" aria-label="History entries"><div class="panel-top"><span>Showing {first:,}–{last:,} of {total:,}</span><span>Times in Maldives · UTC+05:00</span></div>{content}<div class="pagination">{previous}<span>Page {current:,} of {pages:,}</span>{following}</div></section><p class="footnote">Open a page using its title. Hover over shortened text to see the full title or URL.</p></main></body></html>'''
