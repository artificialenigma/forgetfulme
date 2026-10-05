"""Parse bounded CSV/JSON exports without reading local browser profiles."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from app.browser_history import Visit

MAX_BYTES = 100 * 1024 * 1024
MAX_ROWS = 10000


def parse_export(content: bytes, filename: str) -> list[Visit]:
    if len(content) > MAX_BYTES:
        raise ValueError('File exceeds 100 MiB. Split the export into smaller files.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('Upload a UTF-8 CSV or JSON file.')
    if filename.lower().endswith('.csv'):
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {'url', 'visited_at'}.issubset(reader.fieldnames):
            raise ValueError('CSV needs url and visited_at columns; title is optional.')
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise ValueError('A file can contain at most 10,000 visits.')
    elif filename.lower().endswith('.json'):
        try:
            rows = json.loads(text)
        except (ValueError, RecursionError):
            raise ValueError('Invalid JSON file.')
        if isinstance(rows, dict):
            rows = rows.get('visits')
        if not isinstance(rows, list):
            raise ValueError('JSON must be a list of visits or an object with a visits list.')
    else:
        raise ValueError('Choose a .csv or .json browsing history export.')
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError('A file must contain between 1 and 10,000 visits.')
    visits = []
    for number, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict):
                raise ValueError()
            url = row['url']
            raw_time = row['visited_at']
            if not isinstance(url, str) or not isinstance(raw_time, str):
                raise ValueError()
            timestamp = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError()
            timestamp = timestamp.astimezone(timezone.utc)
            event_id = 'import:' + hashlib.sha256((url + '\0' + timestamp.isoformat()).encode()).hexdigest()
            visits.append(Visit(event_id=event_id, url=url, title=row.get('title') or '', visited_at=timestamp))
        except (ValueError, KeyError, TypeError, OverflowError):
            raise ValueError(f'Row {number} is invalid. Use an HTTP(S) URL, a title up to 1,000 characters, and an ISO timestamp with a timezone, such as 2026-10-04T12:30:00Z. Future dates and embedded URL credentials are rejected.')
    return visits
