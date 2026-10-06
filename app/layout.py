"""Shared app navigation, branding and page frame."""
import html

NAVIGATION = [('/', 'Overview', '◫'), ('/history', 'Browsing history', '≡'),
              ('/devices', 'Browser devices', '◉'), ('/history/import', 'Import history', '⇧'),
              ('/history/capture', 'Page scraping', '↗'), ('/vault', 'Obsidian vault', '◇'), ('/vault/wiki', 'Knowledge wiki', '◎'), ('/vault/import', 'Import vault', '⇧'), ('/settings/ai', 'AI settings', '⚙')]


def brand():
    return '<a class="brand" href="/" aria-label="Forgetful Me home"><span class="mark" aria-hidden="true">fm<span>.</span></span><span>forgetful me<small>Your personal archive</small></span></a>'


def render_page(body, title, active='/', show_heading=True):
    navigation = ''.join(f'<a href="{path}"' + (' class="active" aria-current="page"' if path == active else '') + f'><span aria-hidden="true">{icon}</span>{label}</a>' for path, label, icon in NAVIGATION)
    heading = f'<div class="heading"><div><p class="eyebrow">YOUR PERSONAL ARCHIVE</p><h1>{html.escape(title)}</h1></div></div>' if show_heading else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Forgetful Me</title><link rel="stylesheet" href="/static/dashboard.css"></head><body><a class="skip" href="#main">Skip to content</a><aside class="sidebar">{brand()}<div class="nav-label">WORKSPACE</div><nav aria-label="Workspace">{navigation}</nav><div class="sidebar-bottom"><span class="mini-label">PERSONAL ARCHIVE</span><strong>Collect → Capture → Read</strong><p>Browser history and readable page content, together in your vault.</p></div></aside><main id="main"><header class="topbar"><span>Workspace <span class="slash">/</span> {html.escape(title)}</span><span class="private-label">Personal workspace</span></header>{heading}{body}<footer><span>Forgetful Me · Your personal archive</span><span>Times in Maldives (UTC+05:00)</span></footer></main></body></html>'''


def render_login(body):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Forgetful Me</title><link rel="stylesheet" href="/static/dashboard.css"></head><body class="auth"><main class="auth-main">{brand()}{body}</main></body></html>'
