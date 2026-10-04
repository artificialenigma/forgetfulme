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
CREATE INDEX IF NOT EXISTS browser_visits_time ON browser_visits(visited_at DESC);
"""

if __name__ == "__main__":
    with connect() as db:
        db.execute(SCHEMA)
