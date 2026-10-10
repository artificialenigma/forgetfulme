"""Use a trusted local Crawl4AI service for offline HTML-to-Markdown extraction."""
import json
import os
import urllib.error
import urllib.request
from lxml import html


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def extract_html(content, source_url):
    endpoint = os.environ.get('CRAWL4AI_URL','').rstrip('/')
    if not endpoint:
        return None
    # Downloading remains in our DNS-pinned fetcher. Remove active resources before
    # sending raw HTML, so this API call never delegates browsing untrusted URLs.
    document = html.fromstring(content)
    for node in document.xpath('//script|//style|//iframe|//frame|//object|//embed|//img|//source|//video|//audio|//link|//meta|//base'):
        parent = node.getparent()
        if parent is not None: parent.remove(node)
    for node in document.iter():
        for attribute in list(node.attrib):
            if attribute.lower() not in {'href'}:
                del node.attrib[attribute]
        if node.tag != 'a':
            node.attrib.pop('href',None)
        elif node.get('href'):
            from urllib.parse import urljoin, urlsplit
            resolved = urljoin(source_url,node.get('href'))
            if urlsplit(resolved).scheme in {'http','https'}:
                node.set('href',resolved)
            else:
                node.attrib.pop('href',None)
    safe_html = html.tostring(document,encoding='unicode')
    payload = {'urls':['raw:'+safe_html],
               'browser_config':{'type':'BrowserConfig','params':{'headless':True,'java_script_enabled':False,'ignore_https_errors':False,'verbose':False}},
               'crawler_config':{'type':'CrawlerRunConfig','params':{'word_count_threshold':1,'verbose':False,'excluded_tags':['nav','footer','header','aside','form'],'remove_forms':True}}}
    headers = {'Content-Type':'application/json'}
    token = os.environ.get('CRAWL4AI_API_TOKEN')
    if token: headers['Authorization']='Bearer '+token
    request = urllib.request.Request(endpoint+'/crawl',data=json.dumps(payload).encode(),headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=15) as response:
        data = response.read(16*1024*1024+1)
    if len(data)>16*1024*1024: raise ValueError('Crawl4AI response exceeds limit')
    result = json.loads(data)
    results = result.get('results')
    if not result.get('success') or not isinstance(results,list) or not results or not results[0].get('success'):
        raise ValueError('Crawl4AI extraction failed')
    markdown = results[0].get('markdown')
    if isinstance(markdown,dict):
        markdown = markdown.get('fit_markdown') or markdown.get('raw_markdown')
    if not isinstance(markdown,str) or len(markdown.strip())<40:
        raise ValueError('Crawl4AI returned no readable content')
    return markdown
