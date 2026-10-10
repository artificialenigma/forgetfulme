"""Explicit ingestion choices and bounded server-side capture scheduling."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from app.db import connect

POLICY_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_controls (
 id integer PRIMARY KEY CHECK(id=1), visits_enabled boolean, history_exports_enabled boolean,
 downloads_enabled boolean, local_index_enabled boolean, ai_enabled boolean,
 capture_mode text NOT NULL DEFAULT 'all' CHECK(capture_mode IN ('all','selected','allowlisted')),
 requests_per_minute integer NOT NULL DEFAULT 12 CHECK(requests_per_minute BETWEEN 1 AND 60),
 hourly_budget integer NOT NULL DEFAULT 120 CHECK(hourly_budget BETWEEN 1 AND 1000),
 domain_delay_seconds integer NOT NULL DEFAULT 10 CHECK(domain_delay_seconds BETWEEN 1 AND 3600),
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO ingestion_controls(id) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS ingestion_domains (
 domain text PRIMARY KEY, rule text NOT NULL CHECK(rule IN ('allow','block')),
 include_subdomains boolean NOT NULL DEFAULT true, delay_seconds integer CHECK(delay_seconds BETWEEN 1 AND 3600)
);
CREATE TABLE IF NOT EXISTS capture_domain_state (
 domain text PRIMARY KEY, next_allowed_at timestamptz NOT NULL DEFAULT now(), failures integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS capture_attempt_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source_id text NOT NULL, domain text NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), outcome text NOT NULL DEFAULT 'started'
);
CREATE INDEX IF NOT EXISTS capture_attempt_time ON capture_attempt_log(started_at);
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS selected boolean NOT NULL DEFAULT false;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS cancelled boolean NOT NULL DEFAULT false;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS capture_domain text NOT NULL DEFAULT '';
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS policy_state text NOT NULL DEFAULT 'queued';
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS policy_reason text;
"""

CONTROL_NAMES = ('visits', 'history_exports', 'downloads', 'local_index', 'ai')
_SECRET = re.compile(r'^(?:.*[_-])?(?:token|api[_-]?key|key|password|passwd|pwd|secret|signature|sig|auth|authorization|session(?:id)?|sid|code|state|jwt|credential)$|^(?:x-amz-.+|SAMLResponse|SAMLRequest|code_verifier|csrf)$', re.I)


def safe_display_url(url):
    """Redact displays/exports only; never use this as a capture or visit identity."""
    try:
        parsed = urlsplit(str(url))
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return '[unavailable source URL]'
        host = parsed.hostname
        host = '[' + host + ']' if ':' in host else host
        netloc = host + (':' + str(parsed.port) if parsed.port else '')
        def clean(value):
            return urlencode([(key, '[redacted]' if _SECRET.fullmatch(key) else item)
                              for key, item in parse_qsl(value, keep_blank_values=True)])
        fragment = clean(parsed.fragment) if '=' in parsed.fragment else parsed.fragment
        return urlunsplit((parsed.scheme, netloc, parsed.path, clean(parsed.query), fragment))
    except (TypeError, ValueError):
        return '[unavailable source URL]'


def normalize_domain(value):
    value = value.strip().strip('.').casefold()
    try:
        value = value.encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('Provide a valid domain name')
    if (len(value) > 253 or any(len(label)>63 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?',label)
                                for label in value.split('.'))):
        raise ValueError('Use a domain without a scheme, port, path or wildcard')
    return value


def controls(db=None):
    if db is None:
        with connect() as connection:
            return controls(connection)
    row = db.execute('SELECT * FROM ingestion_controls WHERE id=1').fetchone()
    legacy = db.execute('SELECT automation_enabled FROM vault_controls WHERE id=1').fetchone()
    ai = db.execute('SELECT enabled FROM ai_settings WHERE id=1').fetchone()
    result = dict(row)
    inherited = {'visits': True, 'history_exports': legacy['automation_enabled'],
                 'downloads': legacy['automation_enabled'], 'local_index': True,
                 'ai': ai['enabled'] if ai else True}
    for name in CONTROL_NAMES:
        override = row[name + '_enabled']
        result[name] = inherited[name] if override is None else override
        if name=='ai':result[name]=bool(inherited['ai'] and result[name])
    return result


def enabled(name, db=None):
    if name not in CONTROL_NAMES:
        raise ValueError('Unknown ingestion control')
    return controls(db)[name]


def domain_rule(db, domain):
    matches = [row for row in db.execute('SELECT * FROM ingestion_domains').fetchall()
               if domain == row['domain'] or (row['include_subdomains'] and domain.endswith('.' + row['domain']))]
    # Any explicit block wins, including a blocked parent of an allowed child.
    blocked = [row for row in matches if row['rule'] == 'block']
    return max(blocked or matches, key=lambda row: len(row['domain']), default=None)


def allowed(db, url, selected=False, config=None):
    config = config or controls(db)
    try:
        domain = normalize_domain(urlsplit(url).hostname or '')
    except ValueError:
        return False, 'Invalid source domain', '', None
    rule = domain_rule(db, domain)
    if rule and rule['rule'] == 'block':
        return False, 'Domain blocked by ingestion policy', domain, rule
    if config['capture_mode'] == 'selected' and not selected:
        return False, 'Waiting for explicit page selection', domain, rule
    if config['capture_mode'] == 'allowlisted' and not (rule and rule['rule'] == 'allow'):
        return False, 'Domain is outside the allowed-site list', domain, rule
    return True, None, domain, rule


def claim_capture(db):
    config = controls(db)
    if not config['downloads']:
        return None
    # Short advisory budget lock plus per-domain locks stay transaction-scoped.
    # Current worker is serial; duplicate workers skip rather than exceed budgets.
    if not db.execute('SELECT pg_try_advisory_xact_lock(418246) AS locked').fetchone()['locked']:
        return None
    counts = db.execute("SELECT count(*) FILTER(WHERE started_at>now()-interval '1 minute') AS minute,count(*) AS hour FROM capture_attempt_log WHERE started_at>now()-interval '1 hour'").fetchone()
    if counts['minute'] >= config['requests_per_minute'] or counts['hour'] >= config['hourly_budget']:
        return None
    jobs = db.execute("SELECT * FROM page_captures WHERE NOT excluded AND NOT cancelled AND state IN ('pending','retry') AND next_attempt_at<=now() ORDER BY next_attempt_at,url_hash FOR UPDATE SKIP LOCKED LIMIT 50").fetchall()
    for job in jobs:
        permission, reason, domain, rule = allowed(db, job['url'], job['selected'], config)
        if not permission:
            db.execute("UPDATE page_captures SET capture_domain=%s,policy_state='waiting',policy_reason=%s,next_attempt_at=now()+interval '1 minute' WHERE url_hash=%s", (domain, reason, job['url_hash']))
            continue
        db.execute('INSERT INTO capture_domain_state(domain) VALUES (%s) ON CONFLICT DO NOTHING', (domain,))
        clock = db.execute('SELECT *,next_allowed_at<=now() AS ready FROM capture_domain_state WHERE domain=%s FOR UPDATE', (domain,)).fetchone()
        if not clock['ready']:
            db.execute("UPDATE page_captures SET capture_domain=%s,policy_state='waiting',policy_reason='Domain delay or backoff',next_attempt_at=%s WHERE url_hash=%s", (domain, clock['next_allowed_at'], job['url_hash']))
            continue
        delay = (rule and rule['delay_seconds']) or config['domain_delay_seconds']
        db.execute("UPDATE capture_domain_state SET next_allowed_at=now()+(%s*interval '1 second') WHERE domain=%s", (delay, domain))
        attempt = db.execute('INSERT INTO capture_attempt_log(source_id,domain) VALUES (%s,%s) RETURNING id', (job['url_hash'], domain)).fetchone()
        db.execute("UPDATE page_captures SET capture_domain=%s,policy_state='fetching',policy_reason=NULL WHERE url_hash=%s", (domain, job['url_hash']))
        job['_policy_attempt'] = attempt['id']
        job['_policy_domain'] = domain
        return job
    return None


def finish_capture(db, job, outcome):
    if '_policy_attempt' not in job:
        return
    db.execute('UPDATE capture_attempt_log SET outcome=%s WHERE id=%s', (outcome, job['_policy_attempt']))
    db.execute('UPDATE page_captures SET policy_state=%s WHERE url_hash=%s', (outcome, job['url_hash']))
    if outcome == 'complete':
        db.execute('UPDATE capture_domain_state SET failures=0 WHERE domain=%s', (job['_policy_domain'],))
    elif outcome == 'retry':
        db.execute("UPDATE capture_domain_state SET failures=least(failures+1,8),next_allowed_at=greatest(next_allowed_at,now()+least(3600,60*power(2,least(failures,6))) * interval '1 second') WHERE domain=%s", (job['_policy_domain'],))
    db.execute("DELETE FROM capture_attempt_log WHERE started_at<now()-interval '2 days'")


def check_fetch_policy(db, job, url):
    if not controls(db)['downloads']:
        raise ValueError('Page downloading is paused')
    permission, reason, _, _ = allowed(db, url, job['selected'])
    if not permission:
        raise ValueError(reason)
