from app.db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind text NOT NULL CHECK (kind = 'maintenance'),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS service_status (
    service text PRIMARY KEY,
    last_seen timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS browser_devices (
 id uuid PRIMARY KEY, name text NOT NULL, token_hash text UNIQUE NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), last_seen timestamptz, revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS browser_visits (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 device_id uuid NOT NULL REFERENCES browser_devices(id), event_id text NOT NULL,
 url text NOT NULL, title text NOT NULL, visited_at timestamptz NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(), UNIQUE(device_id,event_id)
);
ALTER TABLE browser_visits ADD COLUMN IF NOT EXISTS obsidian_exported_at timestamptz;
CREATE INDEX IF NOT EXISTS browser_visits_export_pending ON browser_visits(id) WHERE obsidian_exported_at IS NULL;
CREATE INDEX IF NOT EXISTS browser_visits_time ON browser_visits(visited_at DESC);
CREATE TABLE IF NOT EXISTS page_captures (
 url_hash text PRIMARY KEY, url text NOT NULL,
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','retry','complete','blocked','failed')),
 attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
 note_path text, final_url text, fetched_at timestamptz, error text
);
CREATE INDEX IF NOT EXISTS page_captures_pending ON page_captures(next_attempt_at) WHERE state IN ('pending','retry');
INSERT INTO page_captures(url_hash,url)
 SELECT DISTINCT encode(sha256(convert_to(split_part(url,'#',1),'UTF8')),'hex'),split_part(url,'#',1) FROM browser_visits
 ON CONFLICT(url_hash) DO NOTHING;
"""

if __name__ == "__main__":
    with connect() as db:
        db.execute(SCHEMA)
