"""Local vault catalog, section retrieval and diagnostics. Never modifies source notes."""
import hashlib
import json
import os
import re
import math
import unicodedata
import regex as unicode_re
import yaml
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from app.db import connect

VAULT = Path('/vault')
MAX_NOTE = 5 * 1024 * 1024
INDEX_VERSION = 4
STOP = {'a','an','the','what','which','how','do','does','is','are','my','sources','say','about','of','to','in','and','can','you','me','tell'}


MAX_FRONTMATTER = 64 * 1024
MAX_METADATA_NODES = 2048
MAX_METADATA_DEPTH = 16
MAX_METADATA_SCALAR = 8192
# Remove recognized HTML markup; preserve generic types, C includes and autolinks.
HTML_TAGS = 'a|abbr|address|article|aside|audio|b|blockquote|body|br|button|caption|center|cite|code|col|colgroup|dd|del|details|div|dl|dt|em|embed|figcaption|figure|font|footer|form|h[1-6]|head|header|hr|html|i|iframe|img|input|label|li|link|main|meta|nav|ol|option|p|picture|pre|section|select|small|source|span|strong|sub|summary|sup|table|tbody|td|textarea|th|thead|title|tr|u|ul|video'


def normalize_match_text(value):
    """NFC/casefold matching with Latin accent folding, keeping other marks.

    cafe/café and composed/decomposed Latin spelling intentionally match. Dhivehi,
    Arabic and other scripts retain their combining marks. Display stays original.
    """
    result = []
    latin = False
    for char in unicodedata.normalize('NFD', str(value)).casefold():
        if unicodedata.category(char).startswith('M'):
            if not latin:
                result.append(char)
        else:
            latin = 'LATIN' in unicodedata.name(char, '')
            result.append(char)
    return unicodedata.normalize('NFC', ''.join(result))


def word_tokens(value):
    """Shared Unicode word rule for diagnostics and retrieval; no query limit."""
    return unicode_re.findall(r'[\p{L}\p{N}][\p{L}\p{M}\p{N}]*', normalize_match_text(value))


def tokens(value):
    return list(dict.fromkeys(x for x in word_tokens(value) if x not in STOP))[:40]


class MetadataLoader(yaml.SafeLoader):
    """A JSON-compatible YAML mapping with no aliases and bounded parse work."""
    def __init__(self, stream):
        super().__init__(stream)
        self.metadata_nodes = 0
        self.metadata_depth = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError('YAML aliases are unsupported')
        self.metadata_nodes += 1
        if self.metadata_nodes > MAX_METADATA_NODES:
            raise ValueError('Too many metadata values')
        self.metadata_depth += 1
        try:
            if self.metadata_depth > MAX_METADATA_DEPTH:
                raise ValueError('Metadata nesting exceeds limit')
            node = super().compose_node(parent, index)
            if isinstance(node, yaml.ScalarNode) and len(node.value) > MAX_METADATA_SCALAR:
                raise ValueError('Metadata scalar exceeds limit')
            return node
        finally:
            self.metadata_depth -= 1

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ValueError('Metadata mapping required')
        values = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key == '<<':
                raise ValueError('Metadata keys must be strings; YAML merges are unsupported')
            if key in values:
                raise ValueError('Duplicate metadata key')
            values[key] = self.construct_object(value_node, deep=deep)
        return values


# Timestamps stay strings and true/false are the only implicit booleans.
# A title/alias such as "On" and source dates retain their original spelling.
MetadataLoader.yaml_implicit_resolvers = {
    key: [(tag, rule) for tag, rule in rules if tag != 'tag:yaml.org,2002:bool']
    for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
MetadataLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$', re.I), list('tTfF'))
MetadataLoader.add_constructor('tag:yaml.org,2002:timestamp', lambda loader, node: loader.construct_scalar(node))


def _metadata_json(value):
    if isinstance(value, dict):
        return {key: _metadata_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_metadata_json(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError('Unsupported metadata value')


def frontmatter(text):
    """Return metadata, unchanged body, and its 1-based source line.

    Invalid closed envelopes are stripped and reported in _frontmatter_issues;
    unclosed/overlong envelopes remain in the body to avoid losing note content.
    """
    opening = re.match(r'^\ufeff?---\r?\n', text)
    if not opening:
        return {}, text, 1
    window = text[opening.end():MAX_FRONTMATTER + 10]
    closing = re.search(r'^---[ \t]*(?:\r?\n|$)', window, re.M)
    # A truncated search window must not make a partial delimiter look like EOF.
    if closing and not closing[0].endswith('\n') and opening.end() + closing.end() < len(text):
        closing = None
    if not closing:
        issue = 'Frontmatter has no closing delimiter within 64 KiB limit'
        return {'_frontmatter_issues': [dict(kind='metadata', detail=issue)]}, text, 1
    end = opening.end() + closing.end()
    source = text[opening.end():opening.end() + closing.start()]
    if len(source.encode('utf-8')) > MAX_FRONTMATTER:
        return {'_frontmatter_issues': [dict(kind='metadata', detail='Frontmatter exceeds 64 KiB limit')]}, text, 1
    body, first_line = text[end:], text[:end].count('\n') + 1
    try:
        values = yaml.load(source, Loader=MetadataLoader)
        if values is None:
            values = {}
        if not isinstance(values, dict):
            raise ValueError('Frontmatter must be a mapping')
        values = _metadata_json(values)
        if '_frontmatter_issues' in values:
            raise ValueError('Reserved metadata key')
        return values, body, first_line
    except (yaml.YAMLError, ValueError, RecursionError):
        # Parser error strings may include private field data; keep diagnostics generic.
        return {'_frontmatter_issues': [dict(kind='metadata', detail='Invalid or unsupported YAML frontmatter; metadata ignored')]}, body, first_line


def clean_text(body):
    """Remove page markup/data while preserving code and source line numbers."""
    protected = []
    marker = '\ufdd0FM_CODE_' + hashlib.sha256(body.encode('utf-8', errors='replace')).hexdigest()[:16] + '_'
    while marker in body:
        marker += '_'

    def protect(value):
        token = f'{marker}{len(protected)}\ufdd1'
        protected.append((token, value))
        return token + '\n' * value.count('\n')

    output, ordinary = [], []
    fence = None
    block = []
    for line in body.splitlines(keepends=True):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)', line)
        if fence:
            block.append(line)
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                output.append(protect(''.join(block)))
                block, fence = [], None
        elif match:
            output.extend(ordinary)
            ordinary = []
            fence = (match[1][0], len(match[1]))
            block = [line]
        elif line.startswith(('    ', '\t')):
            ordinary.append(protect(line))
        else:
            ordinary.append(line)
    output.extend(ordinary)
    if block:
        output.append(protect(''.join(block)))
    text = ''.join(output)
    # Match equal-width inline backtick runs in linear work. A backreference
    # regex can become quadratic for pathological unmatched backtick sequences.
    runs = list(re.finditer(r'`+', text))
    following, next_run = {}, {}
    for index in range(len(runs) - 1, -1, -1):
        width = len(runs[index][0])
        following[index] = next_run.get(width)
        next_run[width] = index
    pieces, cursor, index = [], 0, 0
    while index < len(runs):
        closing = following[index]
        if closing is None:
            index += 1
            continue
        pieces.append(text[cursor:runs[index].start()])
        cursor = runs[closing].end()
        pieces.append(protect(text[runs[index].start():cursor]))
        index = closing + 1
    pieces.append(text[cursor:])
    text = ''.join(pieces)

    def blank(match):
        return '\n' * match[0].count('\n')

    text = re.sub(r'<(script|style)\b[^>]*>.*?(?:</\1\s*>|\Z)', blank, text, flags=re.S | re.I)
    text = re.sub(r'<!--.*?(?:-->|\Z)', blank, text, flags=re.S)
    text = re.sub(r'!\[[^\]\n]*\]\(data:[^\n]*?\)', '[Embedded image omitted]', text)
    text = re.sub(r'<\/?(?:' + HTML_TAGS + r')(?:\s[^<>]*)?/?>', lambda match: ' ' + blank(match), text, flags=re.I)
    def restore(match):
        value = protected[int(match[1])][1]
        # Consume only placeholder line padding, preserving subsequent blank lines.
        return value + match[2][value.count('\n'):]

    return re.sub(re.escape(marker) + r'(\d+)\ufdd1(\n*)', restore, text)


def chunks(body, first_line=1, size=1800):
    """Bound every excerpt to size (128–18000 chars) with source coordinates.

    Large code/text lines split into multiple chunks citing the same source line.
    Fences govern heading recognition even across splits and mixed fence lengths.
    """
    size = max(128, min(18000, int(size)))
    result, lines = [], []
    heading, start, length, fence = 'Introduction', first_line, 0, None

    def flush(end):
        content = '\n'.join(lines)
        if content.strip():
            result.append(dict(heading=heading, start_line=start, end_line=end, content=content))

    cleaned = clean_text(body).splitlines()
    for number, line in enumerate(cleaned, first_line):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)', line)
        title = re.match(r'^#{1,6}\s+(.+)', line) if fence is None and not match else None
        in_code = fence is not None or match is not None
        if match:
            if fence is None:
                fence = (match[1][0], len(match[1]))
            elif match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
        if not in_code and len(line) > size * 3 and re.search(r'data:[^;]+;base64|__next|streamController|\\"\$\\"', line, re.I):
            line = '[Embedded page data omitted]'
        added = len(line) + (1 if lines else 0)
        if lines and (title or length + added > size):
            flush(number - 1)
            lines, length = [], 0
        if title:
            heading = title[1][:500]
        if len(line) > size:
            for offset in range(0, len(line), size):
                content = line[offset:offset + size]
                if content.strip():
                    result.append(dict(heading=heading, start_line=number, end_line=number, content=content))
            continue
        if not lines:
            start = number
        lines.append(line)
        length += len(line) + (1 if len(lines) > 1 else 0)
    flush(first_line + len(cleaned) - 1)
    return result


def summary_excerpt(body, limit=18000):
    limit = max(0, int(limit))
    sections = chunks(body)
    if not sections or not limit:
        return ''
    # Sample across the whole document so later evidence remains eligible.
    count = min(10, len(sections))
    indices = sorted({round(i * (len(sections) - 1) / max(1, count - 1)) for i in range(count)})
    excerpts, remaining = [], limit
    for index in indices:
        section = sections[index]
        label = f"SECTION: {section['heading']} (lines {section['start_line']}–{section['end_line']})\n"
        separator = 2 if excerpts else 0
        selected = section['content'][:max(0, min(1600, remaining - len(label) - separator))]
        if selected:
            excerpts.append(label + selected)
            remaining -= len(label) + len(selected) + separator
    return '\n\n'.join(excerpts)


def safe_path(relative, vault=VAULT):
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts or any(x.startswith('.') for x in path.parts): raise ValueError('Invalid vault path')
    target=vault/path
    if any(p.is_symlink() for p in [target,*target.parents] if p==vault or vault in p.parents): raise ValueError('Vault links are excluded')
    if not target.is_relative_to(vault): raise ValueError('Invalid vault path')
    return target


def repaired_name(name):
    """Recover UTF-8 bytes decoded using ZIP's CP437 fallback, when round-trip safe."""
    try:
        recovered=name.encode('cp437').decode('utf-8')
        return unicodedata.normalize('NFC',recovered) if recovered!=name else None
    except (UnicodeError,ValueError): return None


def capture_url_problem(url):
    parts=urlsplit(url or '')
    if parts.hostname=='accounts.google.com' or re.search(r'/(?:login|signin|sign-in|oauth|accountchooser)(?:/|$)',parts.path,re.I):
        return 'Authentication page; exclude from research'
    return None


def capture_problem(url, title, content):
    problem=capture_url_problem(url)
    if problem:return problem
    if re.fullmatch(r'\s*(?:sign in|log in|redirect notice|your preferences|access denied)\s*',title or '',re.I):
        return 'Login, redirect or preferences page'
    plain=clean_text(content)
    if len(re.findall(r'[^\W_]+',plain))<20: return 'Too little readable content'
    if re.search(r'just a moment|checking your browser|enable javascript.*continue',plain[:500],re.I):
        return 'Challenge or JavaScript placeholder'
    return None



def open_questions(body):
    result=[]
    for match in re.finditer(r'^##\s+Open [Qq]uestions\s*\n(.*?)(?=^## |\Z)',body,re.M|re.S):
        current=[]
        for line in match[1].splitlines():
            bullet=re.match(r'^\s*(?:[-*]|\d+[.)])\s+(.*)',line)
            if bullet or not line.strip():
                if current:result.append(' '.join(current)[:1000]);current=[]
            if bullet:current.append(bullet[1].strip())
            elif line.strip() and not line.startswith('#'):current.append(line.strip())
        if current:result.append(' '.join(current)[:1000])
    return result[:100]

def inspect_note(path, text):
    meta,body,first=frontmatter(text); heading=re.search(r'^#\s+(.+)',body,re.M)
    title=str(meta.get('title') or (heading[1] if heading else Path(path).stem))[:500]
    origin='imported'  # Final scope/origin is assigned by authoritative provenance in scan.
    kind=str(meta.get('type') or ('raw' if path.startswith(('raw/','Clippings/')) else 'note'))[:80]
    tags=meta.get('tags',[]);tags=[str(x)[:100] for x in tags] if isinstance(tags,list) else []
    source_value=meta.get('source_url') or meta.get('source') or ''
    if isinstance(source_value,dict):source_value=source_value.get('url','')
    source_url=str(source_value)
    if not source_url.startswith(('http://','https://')):
        found=re.search(r'https?://[^\s<>\]\)"`]+',body);source_url=found[0] if found else ''
    source_url=source_url[:8192]
    parsed=chunks(body,first); wordcount=len(word_tokens(clean_text(body)))
    issues=list(meta.get('_frontmatter_issues', []))
    if not wordcount: issues.append(dict(kind='empty',detail='No note body'))
    elif wordcount<40: issues.append(dict(kind='thin',detail=f'Only {wordcount} body words; review source completeness'))
    if repaired_name(path): issues.append(dict(kind='encoding',detail='Filename can be recovered as UTF-8',target=repaired_name(path)))
    if '/entities/' in path and kind=='concept': issues.append(dict(kind='metadata',detail='Concept stored in entities folder'))
    if kind=='source' and not source_url: issues.append(dict(kind='provenance',detail='No original URL; check local source reference'))
    if len(text)>100000 and re.search(r'data:|__NEXT|streamController',text): issues.append(dict(kind='boilerplate',detail='Large embedded page data; omitted from retrieval'))
    problem=capture_problem(source_url,title,body) if origin=='archive' and kind in ('source','raw_source') else None
    if problem: issues.append(dict(kind='capture',detail=problem))
    questions=open_questions(body)
    links=re.findall(r'(?<!!)\[\[([^\]\n]+)\]\]',re.sub(r'```.*?```|`[^`\n]+`','',body,flags=re.S))
    metadata={k:meta.get(k) for k in ('author','publisher','published','created','updated','captured_at','confidence','sources','reviewed','ai_state','source_id','managed_by','aliases','evidence_scope','outbound_evidence','parent_document_ids','parent_source_ids','evidence_revisions','source_revision','summary_revision') if k in meta}
    if 'captured_at' not in metadata:
        captured=re.search(r'(?:Fetched:|Captured \(UTC\):)\s*([^\n]+)',body)
        if captured:metadata['captured_at']=captured[1][:100]
    metadata['questions']=questions[:100];metadata['links']=links;metadata['issues']=issues
    metadata['source_refs']=list(dict.fromkeys(re.findall(r'(?:raw|Clippings)/[^`\n]+',body)))[:20]
    project=str(meta.get('project') or '')[:100]
    searchable=wordcount>0 and not problem and not path.startswith('Forgetful Me/Pages/')
    return dict(path=path,title=title,origin=origin,kind=kind,tags=tags,project=project,source_url=source_url,reviewed=meta.get('reviewed') is True,words=wordcount,metadata=metadata,searchable=searchable,chunks=parsed)


def scan(vault=VAULT, force=False):
    from app.library_index import scan as index_scan
    return index_scan(vault, force, db_connect=connect)


# Display categorization never supplies evidence scope or source identity.
DISPLAY_ORIGIN_SQL="""CASE WHEN NOT EXISTS(SELECT 1 FROM library_import_origins display_import WHERE display_import.path=d.path)
 AND ((d.metadata->>'managed_by'='forgetfulme' AND d.kind IN ('query','connections','index','home','website','concept','entity'))
      OR d.path LIKE 'Forgetful Me/Browsing History/%%')
 THEN 'generated' ELSE d.origin END"""


def documents():
    with connect() as db:
        return db.execute('SELECT d.*,'+DISPLAY_ORIGIN_SQL+''' AS display_origin,coalesce(o.excluded,false) AS excluded,coalesce(o.reviewed,d.reviewed) AS effective_reviewed,
            coalesce(nullif(o.project,''),d.project) AS effective_project FROM library_documents d LEFT JOIN library_overrides o USING(path) WHERE d.present ORDER BY path''').fetchall()


def search(query='',origin='',kind='',tag='',project='',review='',limit=50,offset=0,scope='all',for_ai=False,document_id=''):
    from app.evidence import ALLOWED
    if scope not in ('archive','all'):raise ValueError('Explicit evidence scope required')
    terms=tokens(query);filters=[ALLOWED];params=[]
    if for_ai:
        filters.append('d.evidence_scope=ANY(%s)');params.append(['archive'] if scope=='archive' else ['archive','imported'])
    elif scope=='archive':filters.append("d.evidence_scope='archive'")
    if scope=='archive':filters.append('NOT EXISTS(SELECT 1 FROM library_import_origins i WHERE i.path=d.path)')
    for field,value in [('origin',origin),('kind',kind)]:
        if value:filters.append((DISPLAY_ORIGIN_SQL if field=='origin' and not for_ai else 'd.'+field)+'=%s');params.append(value)
    if tag:filters.append('d.tags ? %s');params.append(tag)
    if project:filters.append("coalesce(nullif(o.project,''),d.project)=%s");params.append(project)
    if document_id:filters.append('d.document_id::text=%s');params.append(str(document_id))
    if review in ('reviewed','draft'):filters.append('coalesce(o.reviewed,d.reviewed)=%s');params.append(review=='reviewed')
    condition=' AND '.join(filters)
    fields="""d.path,d.document_id,d.content_hash,d.evidence_scope,d.source_id,d.title,d.origin,d.kind,d.tags,d.source_url,d.metadata,
        coalesce(o.reviewed,d.reviewed) AS reviewed,coalesce(nullif(o.project,''),d.project) AS project,
        c.id,c.heading,c.start_line,c.end_line,c.page_number,c.content,"""+DISPLAY_ORIGIN_SQL+" AS display_origin"
    with connect() as db:
        if not terms:
            return db.execute('SELECT '+fields+""",0 AS score FROM library_documents d
                LEFT JOIN library_overrides o USING(path)
                JOIN LATERAL (SELECT * FROM library_chunks WHERE path=d.path ORDER BY start_line LIMIT 1) c ON true
                WHERE """+condition+' ORDER BY d.indexed_at DESC,d.path LIMIT %s OFFSET %s',params+[limit,offset]).fetchall()
        expression=' | '.join(terms)
        # Limit within each underlying source before truncating candidates. A long
        # title-matched note cannot crowd every other source out of AI context.
        sql='WITH ranked AS (SELECT '+fields+""",
            ts_rank_cd(to_tsvector('simple',c.match_content),to_tsquery('simple',%s),32) +
            ts_rank_cd(to_tsvector('simple',d.match_title),to_tsquery('simple',%s),32)*0.5 +
            (SELECT count(*) FROM unnest(%s::text[]) AS token(word) WHERE to_tsvector('simple',c.match_content) @@ plainto_tsquery('simple',word) OR to_tsvector('simple',d.match_title) @@ plainto_tsquery('simple',word))*2 AS score
            FROM library_chunks c JOIN library_documents d USING(path) LEFT JOIN library_overrides o USING(path)
            WHERE """+condition+""" AND (to_tsvector('simple',c.match_content) @@ to_tsquery('simple',%s) OR to_tsvector('simple',d.match_title) @@ to_tsquery('simple',%s)))"""
        if for_ai:
            sql+=""", diverse AS (SELECT *,row_number() OVER(PARTITION BY coalesce(nullif(source_id,''),document_id::text) ORDER BY score DESC,reviewed DESC,path,start_line) AS source_rank FROM ranked)
                SELECT * FROM diverse WHERE source_rank<=2"""
        else:sql+=' SELECT * FROM ranked'
        sql+=' ORDER BY score DESC,reviewed DESC,path,start_line LIMIT %s OFFSET %s'
        return db.execute(sql,[expression,expression,terms]+params+[expression,expression,limit,offset]).fetchall()


def path_aliases():
    from app.publication import vault_key
    with connect() as db:
        history=db.execute('SELECT h.path,d.path AS current FROM library_path_history h JOIN library_documents d USING(document_id) WHERE d.present AND h.path<>d.path').fetchall()
        publications=db.execute("SELECT DISTINCT ON(logical_path) logical_path,destination_path FROM library_publications WHERE vault_key=%s AND state='published' ORDER BY logical_path,id DESC",(vault_key('/vault'),)).fetchall()
    aliases=defaultdict(set)
    for row in history:aliases[row['path']].add(row['current'])
    for row in publications:aliases[row['logical_path']].add(row['destination_path'])
    return aliases


def resolve_link(source,target,paths,aliases=None,suffixes=None):
    target=target.split('|')[0].split('#')[0].strip()
    if not target: return []
    variants=[target] if Path(target).suffix else [target+'.md',target]
    local=[str(Path(source).parent/x) for x in variants]
    historical=[]
    for name in variants+local:
        historical.extend(p for p in (aliases or {}).get(name,[]) if p in paths)
    if historical:return list(dict.fromkeys(historical))
    exact=[p for p in variants+local if p in paths]
    if exact: return list(dict.fromkeys(exact))
    if suffixes is not None:return list(dict.fromkeys(p for variant in variants for p in suffixes.get(variant,[])))
    return [p for p in paths if any(p.endswith('/'+x) for x in variants)]


def health(rows=None):
    rows=rows if rows is not None else documents(); paths={r['path'] for r in rows};issues=[];hashes=defaultdict(list)
    aliases=path_aliases()
    suffixes=defaultdict(list)
    for path in sorted(paths):
        parts=path.split('/')
        for index in range(1,len(parts)):suffixes['/'.join(parts[index:])].append(path)
    for row in rows:
        for issue in row['metadata'].get('issues',[]): issues.append(dict(path=row['path'],**issue))
        if row['content_hash']: hashes[row['content_hash']].append(row['path'])
        for target in row['metadata'].get('links',[]):
            found=resolve_link(row['path'],target,paths,aliases,suffixes)
            if not found: issues.append(dict(path=row['path'],kind='link',detail='Unresolved link: '+target[:200]))
            elif len(found)>1: issues.append(dict(path=row['path'],kind='ambiguous',detail='Ambiguous link: '+target[:200]))
    for paths in hashes.values():
        if len(paths)>1:
            for p in paths: issues.append(dict(path=p,kind='duplicate',detail='Identical content: '+', '.join(x for x in paths[:9] if x!=p)[:400]))
    return issues


def suggestions(path,rows=None):
    rows=rows if rows is not None else documents();source=next((r for r in rows if r['path']==path),None)
    if not source: return []
    with connect() as db:accepted=db.execute('SELECT target FROM library_connections WHERE source=%s',(path,)).fetchall()
    existing={r['target'] for r in accepted}
    for target in source['metadata'].get('links',[]):existing.update(resolve_link(path,target,{r['path'] for r in rows}))
    results=[]
    for row in rows:
        if row['path']==path or row['path'] in existing or not row['searchable'] or row['excluded']: continue
        shared=set(source['tags'])&set(row['tags']); score=len(shared)
        if source['effective_project'] and source['effective_project']==row['effective_project']:score+=3
        if score>=2:results.append(dict(path=row['path'],title=row['title'],tags=sorted(shared),score=score))
    return sorted(results,key=lambda x:(-x['score'],x['path']))[:8]
