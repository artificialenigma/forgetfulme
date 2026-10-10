"""Pure FM-04 regressions: no database, provider, vault or network access."""
import json
from app import library


def metadata_tests():
    text = '\ufeff---\r\ntitle: "Café: notes"\r\nsummary: |\r\n  First line: quoted colon.\r\n  Second line.\r\ntags: [esp32, "IoT: board"]\r\naliases:\r\n  - ދިވެހި\r\n  - On\r\nauthor:\r\n  name: "Someone: Else"\r\n  identifiers: [123, 456]\r\nsource:\r\n  url: https://example.test/path\r\nreviewed: true\r\npublished: 2026-10-06\r\n---\r\n# Original\r\n'
    meta, body, first = library.frontmatter(text)
    assert meta['title'] == 'Café: notes'
    assert meta['summary'] == 'First line: quoted colon.\nSecond line.\n'
    assert meta['tags'] == ['esp32', 'IoT: board']
    assert meta['aliases'] == ['ދިވެހި', 'On']
    assert meta['author']['name'] == 'Someone: Else'
    assert meta['source']['url'] == 'https://example.test/path'
    assert meta['reviewed'] is True and meta['published'] == '2026-10-06'
    assert first == 18 and body == '# Original\r\n'
    json.dumps(meta, ensure_ascii=False, allow_nan=False)
    assert library.frontmatter('No envelope')[0] == {}
    assert library.frontmatter('---\n---\nBody') == ({}, 'Body', 3)
    assert library.frontmatter('---\ntitle: test\n---')[2] == 3
    rejected = [
        'title: [broken',
        'title: first\ntitle: second',
        'title: !custom unsafe',
        'title: !!python/object/apply:os.system ["true"]',
        'author: &author {name: A}\nsource: *author',
        'authors: &authors [*authors]',
        'authors: !!set {A: null}',
        'title: !!binary YWJj',
        'confidence: .nan',
        'confidence: .inf',
        '42: numeric key',
        '- a\n- b',
        'title: ' + 'a' * (library.MAX_METADATA_SCALAR + 1),
        'value: ' + '[' * 30 + '0' + ']' * 30,
        'tags: [' + ','.join('a' for _ in range(library.MAX_METADATA_NODES + 1)) + ']',
        '_frontmatter_issues: []',
    ]
    for source in rejected:
        meta, body, first = library.frontmatter('---\n' + source + '\n---\nBody')
        assert list(meta) == ['_frontmatter_issues'], source[:100]
        assert meta['_frontmatter_issues'][0]['kind'] == 'metadata'
        assert body == 'Body'
        assert first == source.count('\n') + 4
    for text in ('---\ntitle: no closer', '---\n' + 'x' * (library.MAX_FRONTMATTER + 50) + '\n---\nBody', '---\ntitle: ' + 'ދ' * 35000 + '\n---\nBody'):
        meta, body, first = library.frontmatter(text)
        assert meta['_frontmatter_issues'] and body == text and first == 1
    truncated_delimiter = '---\n' + 'x' * (library.MAX_FRONTMATTER + 2) + '\n---tail\nBody'
    meta, body, first = library.frontmatter(truncated_delimiter)
    assert meta['_frontmatter_issues'] and body == truncated_delimiter and first == 1


def cleaning_tests():
    text = '# Code\n```cpp\n#include <stdio.h>\nvector<int> value;\n# not a heading\n~~~\n<script>literal()</script>\n```\nInline `List<T>` and ``<span>x</span>``.\n    #include <stdio.h>\n\n<table><tr><td>Visible HTML</td></tr></table>\n| A | B |\n| - | - |\n| 1 | 2 |\n<script>\nsecretJavascript();\n</script>\n<style>.secret {x: y}</style>\n<!-- hidden comment\nsecond line -->\n![](data:image/png;base64,BASE64SECRET)\n## Late\nLate evidence <https://example.test/>.\n'
    cleaned = library.clean_text(text)
    assert cleaned.count('\n') == text.count('\n')
    for content in ('#include <stdio.h>', 'vector<int> value;', '# not a heading', '<script>literal()</script>', '`List<T>`', '``<span>x</span>``', '| 1 | 2 |', '<https://example.test/>', 'Visible HTML', 'Late evidence'):
        assert content in cleaned, content
    for content in ('secretJavascript', '.secret', 'hidden comment', 'BASE64SECRET', '<table>'):
        assert content not in cleaned, content
    parts = library.chunks(text, first_line=10, size=128)
    assert all(len(part['content']) <= 128 for part in parts)
    assert not any(part['heading'] == 'not a heading' for part in parts)
    assert next(part for part in parts if 'Late evidence' in part['content'])['start_line'] == 32
    assert next(part for part in parts if '#include' in part['content'])['start_line'] == 10
    # A shorter fence and the other fence marker inside code never close it.
    mixed = '````cpp\n```\n# inside fence\n~~~\n````\n## Real\nEnd\n'
    assert '<stdio.h>' in library.clean_text('```c\n#include <stdio.h>\n')
    assert not any(part['heading'] == 'inside fence' for part in library.chunks(mixed))
    assert library.chunks(mixed)[-1]['heading'] == 'Real'
    assert library.chunks('    indented(code)\n')[0]['content'].startswith('    ')


def chunk_tests():
    for length in (1800, 1801, 3600, 5400, 5401, 50000):
        source = '# Heading\n' + 'x' * length + '\n## Later\nLate evidence\n'
        parts = library.chunks(source)
        assert all(len(part['content']) <= 1800 for part in parts)
        assert ''.join(part['content'] for part in parts if part['start_line'] == 2) == 'x' * length
        assert parts[-1]['heading'] == 'Later' and 'Late evidence' in parts[-1]['content']
        assert all(part['start_line'] <= part['end_line'] for part in parts)
    large_code = '```c\n' + '#include <stdio.h>;' * 2000 + '\n# still code\n```\n## Later\nLate\n'
    parts = library.chunks(large_code)
    assert all(len(part['content']) <= 1800 for part in parts)
    assert '#include <stdio.h>' in ''.join(part['content'] for part in parts)
    assert not any(part['heading'] == 'still code' for part in parts)
    indented = '```python\n' + ('    print("keep indentation")\n' * 1000) + '```\n'
    assert all(not part['content'].startswith('print') for part in library.chunks(indented))
    # Unmatched inline runs and markup must stay bounded without regex backtracking.
    for pathological in ('x' + '`' * 100000 + 'y', '<span ' + ' ' * 100000, '`<span>` text\n' * 20000):
        assert all(len(part['content']) <= 1800 for part in library.chunks(pathological))
    embedded = '# Heading\n' + '__NEXT_DATA__ BASE64SECRET ' * 2000 + '\n## Later\nLate evidence\n'
    assert 'BASE64SECRET' not in library.summary_excerpt(embedded)
    assert 'Embedded page data omitted' in library.summary_excerpt(embedded)
    long = '# Intro\n' + 'Early paragraph\n' * 1400 + '## Late section\nUnique later evidence for café ދިވެހި.\n'
    assert 'Unique later evidence' in library.summary_excerpt(long)
    for limit in (0, 1, 50, 128, 1600, 18000):
        assert len(library.summary_excerpt(long, limit)) <= limit


def multilingual_tests():
    assert library.normalize_match_text('CAFÉ Cafe\u0301 cafe') == 'cafe cafe cafe'
    assert library.normalize_match_text('ދިވެހި') == 'ދިވެހި'
    assert library.word_tokens('ދިވެހި CAFÉ') == ['ދިވެހި', 'cafe']
    assert library.tokens('café cafe Cafe\u0301 the ދިވެހި') == ['cafe', 'ދިވެހި']
    assert library.normalize_match_text('مُحَمَّد') == 'مُحَمَّد'
    assert library.normalize_match_text('Αθήνα') == 'αθήνα'
    assert library.normalize_match_text('Crème brûlée Straße') == 'creme brulee strasse'
    assert len(library.tokens(' '.join('term' + str(i) for i in range(100)))) == 40
    assert len(library.word_tokens(' '.join('term' + str(i) for i in range(100)))) == 100


metadata_tests()
cleaning_tests()
chunk_tests()
multilingual_tests()
print('FM-04: bounded YAML, code/line fidelity, chunk budgets, Latin accent matching and Dhivehi regressions passed')
