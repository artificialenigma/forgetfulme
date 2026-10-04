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
"""

if __name__ == "__main__":
    with connect() as db:
        db.execute(SCHEMA)
