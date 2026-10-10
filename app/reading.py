"""Bounded Markdown reading with escaped HTML and no remote media loads."""
import html
from urllib.parse import urlsplit,urlencode
from markdown_it import MarkdownIt
from app.ingestion_policy import safe_display_url

MAX_READING_CHARS=250_000


def render(body):
    parser=MarkdownIt('commonmark',{'html':False,'linkify':False,'maxNesting':20}).enable('table')
    def image(self,tokens,index,options,env):
        return '<span class="omitted-media">[Image omitted: '+html.escape(tokens[index].content)+']</span>'
    parser.add_render_rule('image',image)
    def link_open(self,tokens,index,options,env):
        token=tokens[index];href=token.attrGet('href') or ''
        parsed=urlsplit(href)
        if parsed.scheme in ('http','https'):
            token.attrSet('href',safe_display_url(href));token.attrSet('rel','noopener noreferrer')
        elif parsed.scheme or href.startswith('//'):
            token.attrSet('href','#')
        elif href and not href.startswith('#'):
            token.attrSet('href','/library/note?'+urlencode({'path':href}))
        return parser.renderer.renderToken(tokens,index,options,env)
    parser.add_render_rule('link_open',link_open)
    if len(body)>MAX_READING_CHARS:
        return '<p>Reading preview is limited to 250,000 characters. Use the raw source view or Obsidian for the full note.</p>'
    try:return parser.render(body)
    except Exception:return '<p>Reading preview unavailable. Use raw source below.</p>'
