"""Public-page fetching, extraction and durable per-URL work."""
import hashlib
import http.client
import ipaddress
import os
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
import trafilatura
from app.db import connect
from app.obsidian_export import text

USER_AGENT = 'ForgetfulMe/0.1'
MAX_BODY = 5 * 1024 * 1024


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


def scrape_page(url, digest, vault=Path('/vault')):
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
    folder = vault / 'Forgetful Me' / 'Pages'
    folder.mkdir(parents=True,exist_ok=True)
    destination = folder / (digest + '.md')
    source_link = quote(final,safe=':/?#@!$&\'*=+;,%~-._')
    note = f'# {text(title)}\n\nSource: [{text(final)}](<{source_link}>)\n\nFetched: {datetime.now(timezone.utc).isoformat()}\nExtractor: {engine}\n\n> Captured from the public page at fetch time. Keep personal annotations in a separate note.\n\n---\n\n{content}\n'
    temporary = destination.with_suffix('.md.tmp')
    with temporary.open('w',encoding='utf-8') as output:
        output.write(note); output.flush(); os.fsync(output.fileno())
    os.replace(temporary,destination)
    return str(destination.relative_to(vault)), final, engine


def process_page():
    with connect() as db:
        # Row lock lasts through bounded fetching; another worker skips it safely.
        job = db.execute("SELECT url_hash,url,attempts FROM page_captures WHERE state IN ('pending','retry') AND next_attempt_at<=now() ORDER BY next_attempt_at,url_hash FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if not job: return False
        attempts = job['attempts'] + 1
        try:
            path, final, engine = scrape_page(job['url'],job['url_hash'])
            db.execute("UPDATE page_captures SET state='complete',attempts=%s,note_path=%s,final_url=%s,extractor=%s,fetched_at=now(),error=NULL WHERE url_hash=%s",(attempts,path,final,engine,job['url_hash']))
        except Blocked as error:
            db.execute("UPDATE page_captures SET state='blocked',attempts=%s,error=%s WHERE url_hash=%s",(attempts,str(error)[:200],job['url_hash']))
        except Exception as error:
            reason = str(error)[:200] if isinstance(error,FetchFailed) else 'Page extraction or vault write failed'
            db.execute("UPDATE page_captures SET state=%s,attempts=%s,error=%s,next_attempt_at=now()+(%s * interval '1 second') WHERE url_hash=%s",('retry' if attempts < 3 else 'failed',attempts,reason,60*2**(attempts-1),job['url_hash']))
    return True
