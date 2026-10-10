"""Public-page fetching, extraction and durable per-URL work."""
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
import trafilatura
from app.db import connect
from app.obsidian_export import text

USER_AGENT = 'ForgetfulMe/0.1'
MAX_BODY = 5 * 1024 * 1024
_FETCH_POLICY_GUARD = ContextVar('capture_fetch_policy', default=None)


class Blocked(ValueError):
    pass


class FetchFailed(ValueError):
    pass


def public_target(url):
    try:
        parts = urlsplit(url)
        expected_port = 443 if parts.scheme == 'https' else 80
        if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password or parts.port not in {None,expected_port}:
            raise Blocked('Only public HTTP(S) pages on standard ports can be scraped')
        host = parts.hostname.encode('idna').decode('ascii')
        addresses = socket.getaddrinfo(host, expected_port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise Blocked('Local, private and reserved network addresses are excluded')
        return parts, host, expected_port, sorted(addresses,key=lambda item:item[0]!=socket.AF_INET)[0][4][0]
    except (UnicodeError, ValueError) as error:
        if isinstance(error, Blocked): raise
        raise Blocked('Invalid page address')
    except OSError:
        raise FetchFailed('DNS resolution failed')


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, secure, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address, self.secure = address, secure
    def connect(self):
        self.sock = socket.create_connection((self.address,self.port),self.timeout)
        if self.secure:
            self.sock = ssl.create_default_context().wrap_socket(self.sock,server_hostname=self.host)


def fetch(url, respect_robots=False):
    deadline = time.monotonic() + 20
    for _ in range(6):
        guard = _FETCH_POLICY_GUARD.get()
        if guard:
            guard(url)
        parts, host, port, address = public_target(url)
        if respect_robots: check_robots(url)
        remaining = deadline-time.monotonic()
        if remaining <= 0: raise FetchFailed('Page fetch timed out')
        connection = PinnedConnection(host,port,address,parts.scheme=='https',min(remaining,8))
        try:
            path = quote(parts.path or '/',safe='/%:@!$&\'()*+,;=-._~')
            if parts.query: path += '?' + quote(parts.query,safe='/%?:@!$&\'()*+,;=-._~')
            connection.request('GET',path,headers={'User-Agent':USER_AGENT,'Accept':'text/html,text/plain;q=0.9','Accept-Encoding':'identity','Connection':'close'})
            response = connection.getresponse()
            if response.status in {301,302,303,307,308}:
                location = response.getheader('Location')
                if not location: raise FetchFailed('Redirect has no destination')
                url = urljoin(url,location)
                continue
            content_type = response.getheader('Content-Type','').split(';')[0].strip().lower()
            if response.status >= 400:
                return response.status, content_type, b'', url
            if response.status != 200: raise FetchFailed('Unexpected HTTP response')
            if response.getheader('Content-Encoding','identity').lower() != 'identity':
                raise Blocked('Compressed responses are unsupported')
            length = response.getheader('Content-Length')
            if length and int(length) > MAX_BODY: raise Blocked('Page exceeds 5 MiB')
            chunks, size = [], 0
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise FetchFailed('Page fetch timed out')
                if connection.sock is not None:
                    connection.sock.settimeout(min(remaining,8))
                chunk = response.read(65536)
                if not chunk: break
                size += len(chunk)
                if size > MAX_BODY: raise Blocked('Page exceeds 5 MiB')
                chunks.append(chunk)
            return response.status,content_type,b''.join(chunks),url
        except (OSError,http.client.HTTPException):
            raise FetchFailed('Connection or TLS failure')
        except ValueError as error:
            if isinstance(error,(Blocked,FetchFailed)): raise
            raise FetchFailed('Invalid HTTP response')
        finally:
            connection.close()
    raise FetchFailed('Too many redirects')


_ROBOTS = {}

def check_robots(url):
    parts = urlsplit(url)
    origin = urlunsplit((parts.scheme,parts.netloc,'','',''))
    cached = _ROBOTS.get(origin)
    if cached and time.monotonic()-cached[0] < 3600:
        parser = cached[1]
    else:
        status, _, body, final = fetch(origin + '/robots.txt')
        parser = RobotFileParser(origin+'/robots.txt')
        if status in {401,403}:
            parser.disallow_all = True
        elif status >= 500 or status == 429:
            raise FetchFailed('Robots policy temporarily unavailable')
        elif status >= 400:
            parser.allow_all = True
        else:
            parser.parse(body.decode('utf-8',errors='replace').splitlines())
        if len(_ROBOTS) >= 1000: _ROBOTS.clear()
        _ROBOTS[origin] = time.monotonic(), parser
    if not parser.can_fetch(USER_AGENT,url):
        raise Blocked('Site robots policy disallows fetching this page')


def capture_content(note):
    """Stable extracted content, excluding generated fetch time and note links."""
    from app.library import frontmatter
    _,body,_=frontmatter(note)
    body=re.split(r'\r?\n---\r?\n',body,maxsplit=1)[-1]
    body=re.sub(r'\r?\n\r?\n## Wiki record\r?\n\r?\n\[\[Forgetful Me/wiki/sources/[^\n]+\]\]\s*\Z','',body)
    return body.replace('\r\n','\n').strip()


def capture_hash(note):
    return hashlib.sha256(capture_content(note).encode('utf-8')).hexdigest()


def scrape_page(url, digest, vault=Path('/vault')):
    from app.library import capture_problem, capture_url_problem
    problem=capture_url_problem(url)
    if problem:raise Blocked(problem)
    public_target(url)
    status, content_type, body, final = fetch(url, respect_robots=True)
    if status in {401,403,404,410}:
        raise Blocked(f'HTTP {status}: page unavailable or requires access')
    if status != 200: raise FetchFailed(f'HTTP {status}')
    if content_type not in {'text/html','application/xhtml+xml','text/plain'}:
        raise Blocked('Page type is unsupported; only HTML and text are scraped')
    engine = 'Trafilatura'
    if content_type == 'text/plain':
        engine = 'Plain text'
        content = body.decode('utf-8',errors='replace').strip()
        title = urlsplit(final).hostname
        # Plain text is fenced so it cannot introduce active HTML/Markdown.
        fence = '`' * max(3, max((len(part) for part in re.findall(r'`+',content)),default=0)+1)
        content = fence + '\n' + content + '\n' + fence if content else ''
    else:
        from app.crawl4ai_client import extract_html
        try:
            content = extract_html(body,final)
            if content: engine = 'Crawl4AI'
        except Exception:
            # Service outage/unsupported API must not stall the history backlog.
            content = None
        if not content:
            content = trafilatura.extract(body,url=final,output_format='markdown',include_comments=False,include_links=True,include_images=False,favor_precision=True)
        metadata = trafilatura.extract_metadata(body)
        title = (metadata.title if metadata else None) or urlsplit(final).hostname
    if not content or len(content.strip()) < 40:
        raise Blocked('No readable page content found (may require JavaScript or login)')
    problem=capture_problem(final,title,content)
    if problem:raise Blocked(problem)
    from app.library import safe_path
    from app.wiki import atomic_note,note_header
    relative='Forgetful Me/Pages/'+digest+'.md'
    destination=safe_path(relative,vault)
    from app.ingestion_policy import safe_display_url
    display_url=safe_display_url(final)
    source_link = quote(display_url,safe=':/?#@!$&\'*=+;,%~-._')
    content_digest=hashlib.sha256(content.replace('\r\n','\n').strip().encode()).hexdigest()
    note = note_header('raw_source',title,source_id=digest,source_url=display_url,source_revision=content_digest)
    note += f'# {text(title)}\n\nSource: [{text(display_url)}](<{source_link}>)\n\nFetched: {datetime.now(timezone.utc).isoformat()}\nExtractor: {engine}\n\n> Captured from the public page at fetch time. Keep personal annotations in a separate note.\n\n---\n\n{content}\n'
    if destination.exists():
        # Capture snapshots are immutable. Legacy or annotated originals survive
        # recapture; changed extraction gets a separate, no-overwrite revision.
        if capture_hash(destination.read_text())==content_digest:
            return str(destination.relative_to(vault)),final,engine
        destination=safe_path('Forgetful Me/Pages/'+digest+' — '+content_digest[:16]+'.md',vault)
        if destination.exists() and capture_hash(destination.read_text())==content_digest:
            return str(destination.relative_to(vault)),final,engine
    if not atomic_note(destination,note,expected_hash=''):
        raise FetchFailed('Captured revision destination is protected or changed')
    return str(destination.relative_to(vault)), final, engine


def process_page():
    with connect() as db:
        from app.ingestion_policy import claim_capture, finish_capture, check_fetch_policy
        # Row lock lasts through bounded fetching; another worker skips it safely.
        job = claim_capture(db)
        if not job: return False
        attempts = job['attempts'] + 1
        try:
            old_hash=job.get('capture_content_hash','')
            if not old_hash and job.get('note_path'):
                from app.library import safe_path
                try:old_hash=capture_hash(safe_path(job['note_path']).read_text())
                except (OSError,ValueError,UnicodeError):pass
            def guard(url):
                try:check_fetch_policy(db,job,url)
                except ValueError as error:raise Blocked(str(error))
            token = _FETCH_POLICY_GUARD.set(guard)
            try:path, final, engine = scrape_page(job['url'],job['url_hash'])
            finally:_FETCH_POLICY_GUARD.reset(token)
            from app.library import safe_path
            captured=safe_path(path).read_text()
            new_hash=capture_hash(captured)
            changed=old_hash!=new_hash
            already_published=not changed and job.get('wiki_indexed_at') is not None and job.get('publication_state')=='succeeded'
            if already_published:path=job['note_path']
            data=job.get('wiki_data') or {}
            if changed:
                from app.library import frontmatter
                new_title=frontmatter(captured)[0].get('title')
                data={'title':new_title or data.get('title') or urlsplit(final).hostname}
            summary_hash=(job.get('summary_source_hash') or old_hash) if not changed else ''
            db.execute("""UPDATE page_captures SET state='complete',attempts=%s,note_path=%s,final_url=%s,extractor=%s,fetched_at=now(),error=NULL,
                capture_content_hash=%s,summary_source_hash=%s,wiki_data=%s::jsonb,
                ai_state=CASE WHEN %s THEN 'pending' ELSE ai_state END,
                ai_attempts=CASE WHEN %s THEN 0 ELSE ai_attempts END,
                ai_error=CASE WHEN %s THEN NULL ELSE ai_error END,ai_next_attempt=now(),
                publication_state=CASE WHEN %s THEN publication_state ELSE 'pending' END,
                publication_error=CASE WHEN %s THEN publication_error ELSE NULL END,publication_next_attempt=now(),
                wiki_indexed_at=CASE WHEN %s THEN now() ELSE NULL END
                WHERE url_hash=%s""",(attempts,path,final,engine,new_hash,summary_hash,json.dumps(data),changed,changed,changed,already_published,already_published,already_published,job['url_hash']))
            finish_capture(db,job,'complete')
        except Blocked as error:
            db.execute("UPDATE page_captures SET state='blocked',attempts=%s,error=%s WHERE url_hash=%s",(attempts,str(error)[:200],job['url_hash']))
            finish_capture(db,job,'blocked')
        except Exception as error:
            reason = str(error)[:200] if isinstance(error,FetchFailed) else 'Page extraction or vault write failed'
            db.execute("UPDATE page_captures SET state=%s,attempts=%s,error=%s,next_attempt_at=now()+(%s * interval '1 second') WHERE url_hash=%s",('retry' if attempts < 3 else 'failed',attempts,reason,60*2**(attempts-1),job['url_hash']))
            finish_capture(db,job,'retry' if attempts<3 else 'failed')
    return True
