"""Verify raw-HTML integration, service failures and safe resource removal."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from app import crawl4ai_client as client, page_scraper

article = ('<html><body><nav>Navigation</nav><article><h1>Integration test</h1><p>'+'This is readable article content for our Markdown integration. '*20+'</p></article><script src="http://127.0.0.1/private">secret()</script><iframe src="http://private/"></iframe><img src="http://private/image"><a href="javascript:secret()">Bad link</a></body></html>').encode()
class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,limit):return json.dumps({'success':True,'results':[{'success':True,'markdown':{'fit_markdown':'','raw_markdown':'Readable Markdown content for integration verification. '*3}}]}).encode()
class Opener:
    def open(self,request,timeout):
        payload=json.loads(request.data)
        raw=payload['urls'][0]
        assert raw.startswith('raw:') and '<script' not in raw and '<iframe' not in raw and '<img' not in raw
        assert 'javascript:' not in raw and 'http://private' not in raw
        assert not payload['browser_config']['params']['java_script_enabled']
        return Response()
with patch.dict(client.os.environ,{'CRAWL4AI_URL':'http://crawl4ai:11235'}),patch.object(client.urllib.request,'build_opener',return_value=Opener()):
    assert 'Readable Markdown' in client.extract_html(article,'https://example.com')
with TemporaryDirectory() as temp,patch.object(page_scraper,'public_target',return_value=None),patch.object(page_scraper,'fetch',return_value=(200,'text/html',article,'https://example.com')),patch.object(client,'extract_html',side_effect=OSError('service down')):
    path,_,engine=page_scraper.scrape_page('https://example.com','fallback',Path(temp))
    assert engine=='Trafilatura' and 'readable article' in (Path(temp)/path).read_text()
# Actual worker -> existing service request with synthetic content.
markdown=client.extract_html(article,'https://example.com')
assert markdown and 'readable article' in markdown
print('Crawl4AI raw HTML sanitization, service-outage fallback and live service extraction passed')
