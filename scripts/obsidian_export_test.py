"""Verify safe Markdown, deterministic retries and failed-write behavior in isolation."""
from app.db import require_isolated_test
require_isolated_test()
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from app import obsidian_export as module

row = {'id':12,'url':'https://example.com/page?q=(test)','title':'[test] <script>','name':'Test source','visited_at':datetime(2026,1,1,21,tzinfo=timezone.utc)}
class Result:
    rowcount = 1
    def __init__(self, rows): self.rows=rows
    def fetchone(self): return self.rows[0]
    def fetchall(self): return self.rows
class Database:
    def __init__(self): self.updated=False
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self, sql, params=None):
        if 'pg_try' in sql: return Result([{'locked':True}])
        if sql.startswith('UPDATE'): self.updated=True; return Result([])
        return Result([row])
def export_fixture(vault):
    with patch('app.ingestion_policy.enabled',return_value=True):
        return module.export_pending(vault)
with TemporaryDirectory() as temp:
    db=Database()
    with patch.object(module,'connect',return_value=db):
        assert export_fixture(Path(temp)) == 1
        note=next(Path(temp).rglob('*.md'))
        original=note.read_text()
        assert note.name.startswith('2026-01-02') and '**02:00:00**' in original
        assert '\\[test\\]' in original and '<script>' not in original
        assert '%28test%29' in original
        export_fixture(Path(temp))
        assert note.read_text() == original and len(list(Path(temp).rglob('*.md'))) == 1
    db=Database()
    with patch.object(module,'connect',return_value=db), patch.object(module,'publish_note',side_effect=OSError('write failed')):
        try: export_fixture(Path(temp))
        except OSError: pass
        else: raise AssertionError('Failed write was accepted')
        assert not db.updated and note.read_text()==original
print('Obsidian Markdown escaping, timezone grouping, retry stability and failed-write tests passed')
