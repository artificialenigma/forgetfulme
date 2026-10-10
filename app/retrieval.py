"""Bound and diversify already-permitted evidence without modifying excerpts."""
import hashlib
import math
import unicodedata

RETRIEVAL_VERSION='lexical-source-diversity-v1'


def source_key(row):
    """Raw and summary records share a source; independent notes keep IDs."""
    return str(row.get('source_id') or row.get('document_id') or row['path'])


def excerpt_key(row):
    normalized=' '.join(unicodedata.normalize('NFC',row['content']).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def estimate_tokens(row):
    """Conservative UTF-8 estimate, including source/coordinate prompt headers.

    Provider tokenizers vary; this is an explicit estimate, not an exact context
    limit. Whole excerpts remain intact so retained citations match source text.
    """
    fields=(row.get('path',''),row.get('heading',''),row['content'])
    return math.ceil(sum(len(str(value).encode('utf-8')) for value in fields)/3)+80


def select_evidence(candidates,max_sections=6,max_per_source=2,token_budget=3500):
    """Select whole ranked chunks after scope/exclusion revalidation.

    The first pass takes one section per source. A second section may come from
    the same chosen document; mixing its raw and summary records is avoided.
    Exact excerpt duplicates never spend context twice, without merging note
    identities. This function makes no permission decisions.
    """
    if max_sections<1 or max_per_source<1 or token_budget<1:return []
    selected=[];seen=set();documents={};counts={};spent=0
    def take(row):
        nonlocal spent
        key=excerpt_key(row);cost=estimate_tokens(row);source=source_key(row)
        if key in seen or spent+cost>token_budget or len(selected)>=max_sections:return False
        selected.append(row);seen.add(key);spent+=cost
        counts[source]=counts.get(source,0)+1
        documents[source]=str(row.get('document_id') or row['path'])
        return True
    for row in candidates:
        if source_key(row) not in counts:take(row)
    if len(selected)<max_sections and max_per_source>1:
        for row in candidates:
            source=source_key(row)
            if source in counts and counts[source]<max_per_source and documents[source]==str(row.get('document_id') or row['path']):
                take(row)
    return selected


def selection_report(rows,token_budget=3500):
    return dict(version=RETRIEVAL_VERSION,sections=len(rows),sources=len({source_key(row) for row in rows}),
                estimated_tokens=sum(estimate_tokens(row) for row in rows),token_budget=token_budget,
                token_estimate='ceil(UTF8_bytes/3)+80 per section; provider tokenizer varies')
