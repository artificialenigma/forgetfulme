"""Parse bounded CSV/JSON exports without reading local browser profiles."""
import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pydantic import ValidationError
from app.browser_history import Visit

MAX_BYTES = 100 * 1024 * 1024
MAX_ROWS = 1_000_000


@dataclass
class ImportResult:
    visits: list[Visit]
    skipped: int
    issues: list[str]


def parse_export(content: bytes, filename: str, skip_invalid_safari: bool = False) -> ImportResult:
    if len(content) > MAX_BYTES:
        raise ValueError('File exceeds 100 MiB. Split the export into smaller files.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('Upload a UTF-8 CSV or JSON file.')
    safari = False
    if filename.lower().endswith('.csv'):
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {'url', 'visited_at'}.issubset(reader.fieldnames):
            raise ValueError('CSV needs url and visited_at columns; title is optional.')
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise ValueError('A file can contain at most 1,000,000 visits.')
    elif filename.lower().endswith('.json'):
        try:
            rows = json.loads(text)
        except (ValueError, RecursionError):
            raise ValueError('Invalid JSON file.')
        if isinstance(rows, dict):
            if 'history' in rows:
                metadata = rows.get('metadata')
                if (not isinstance(metadata, dict) or metadata.get('browser_name') != 'Safari'
                        or metadata.get('data_type') != 'history'
                        or type(metadata.get('schema_version')) is not int
                        or metadata['schema_version'] != 1):
                    raise ValueError('Unsupported Safari export. Use a Safari history JSON export with schema_version 1.')
                safari = True
                rows = rows['history']
            else:
                rows = rows.get('visits')
        if not isinstance(rows, list):
            raise ValueError('JSON must be a visits list, an object with a visits list, or a Safari history export.')
    else:
        raise ValueError('Choose a .csv or .json browsing history export.')
    if not rows:
        raise ValueError('The file contains no history entries.')
    if len(rows) > MAX_ROWS:
        raise ValueError(f'The file contains {len(rows):,} entries; the limit is {MAX_ROWS:,}. Split it into smaller files.')
    visits = []
    skipped = 0
    issues = []
    for number, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict):
                raise ValueError("Invalid entry structure or field type")
            url = row['url']
            if not isinstance(url, str):
                raise ValueError("Invalid entry structure or field type")
            if safari:
                microseconds = row['time_usec']
                if type(microseconds) is not int or microseconds < 0:
                    raise ValueError('time_usec must be a nonnegative integer')
                # Safari JSON exports use Unix microseconds, not History.db's Apple epoch.
                # Integer timedelta preserves exact microseconds for repeat-import identities.
                timestamp = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=microseconds)
            else:
                raw_time = row['visited_at']
                if not isinstance(raw_time, str):
                    raise ValueError("Invalid entry structure or field type")
                timestamp = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError("Invalid entry structure or field type")
            timestamp = timestamp.astimezone(timezone.utc)
            event_id = 'import:' + hashlib.sha256((url + '\0' + timestamp.isoformat()).encode()).hexdigest()
            visits.append(Visit(event_id=event_id, url=url, title=row.get('title') or '', visited_at=timestamp))
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            if isinstance(error, ValidationError):
                detail = error.errors(include_url=False, include_input=False)[0]
                reason = str(detail['loc'][0]) + ': ' + detail['msg']
            elif isinstance(error, KeyError):
                reason = 'Missing field: ' + str(error.args[0])
            elif isinstance(error, OverflowError):
                reason = 'Timestamp is outside the supported range'
            else:
                reason = str(error) or 'Invalid field type'
            issue = f'{"Safari history entry" if safari else "Row"} {number}: {reason}'
            if safari and skip_invalid_safari:
                skipped += 1
                if len(issues) < 20:
                    issues.append(issue)
                continue
            raise ValueError(issue)
    if not visits:
        raise ValueError('No valid visits found. ' + ('; '.join(issues) if issues else 'Check the export format.'))
    return ImportResult(visits, skipped, issues)
