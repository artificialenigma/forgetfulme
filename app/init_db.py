from app.db import connect

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS ai_settings (
 id integer PRIMARY KEY CHECK(id=1), provider text NOT NULL CHECK(provider IN ('ollama','openai')),
 base_url text NOT NULL, model text NOT NULL, enabled boolean NOT NULL DEFAULT true,
 temperature double precision NOT NULL DEFAULT 0, max_tokens integer NOT NULL DEFAULT 1400,
 context_size integer NOT NULL DEFAULT 8192, api_key bytea,
 test_state text NOT NULL DEFAULT 'untested', test_message text, updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE ai_settings ADD COLUMN IF NOT EXISTS models jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE ai_settings ADD COLUMN IF NOT EXISTS models_state text NOT NULL DEFAULT 'untested';
ALTER TABLE ai_settings ADD COLUMN IF NOT EXISTS models_message text;
ALTER TABLE ai_settings ADD COLUMN IF NOT EXISTS models_fetched_at timestamptz;
CREATE TABLE IF NOT EXISTS vault_controls (
 id integer PRIMARY KEY CHECK(id=1), automation_enabled boolean NOT NULL DEFAULT true
);
INSERT INTO vault_controls(id) VALUES(1) ON CONFLICT DO NOTHING;
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
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS extractor text;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS wiki_source_path text;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS wiki_indexed_at timestamptz;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS wiki_data jsonb;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS ai_state text NOT NULL DEFAULT 'pending' CHECK(ai_state IN ('pending','retry','complete','failed','reviewed'));
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS ai_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS ai_next_attempt timestamptz NOT NULL DEFAULT now();
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS ai_error text;
CREATE TABLE IF NOT EXISTS wiki_questions (
 id uuid PRIMARY KEY, question text NOT NULL, state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','complete','failed')),
 answer text, citations jsonb, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz, error text
);
CREATE TABLE IF NOT EXISTS library_documents (
 path text PRIMARY KEY, title text NOT NULL, origin text NOT NULL, kind text NOT NULL,
 tags jsonb NOT NULL DEFAULT '[]', project text NOT NULL DEFAULT '', source_url text NOT NULL DEFAULT '',
 reviewed boolean NOT NULL DEFAULT false, words integer NOT NULL DEFAULT 0, metadata jsonb NOT NULL DEFAULT '{}',
 searchable boolean NOT NULL DEFAULT true, fingerprint text NOT NULL, content_hash text NOT NULL DEFAULT '', indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS library_chunks (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, path text NOT NULL REFERENCES library_documents(path) ON DELETE CASCADE,
 heading text NOT NULL, start_line integer NOT NULL, end_line integer NOT NULL, content text NOT NULL,
 search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple',content)) STORED
);
CREATE INDEX IF NOT EXISTS library_chunk_search ON library_chunks USING gin(search_vector);
CREATE INDEX IF NOT EXISTS library_chunk_path ON library_chunks(path);
CREATE TABLE IF NOT EXISTS library_overrides (
 path text PRIMARY KEY, excluded boolean NOT NULL DEFAULT false, reviewed boolean, project text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS library_question_status (
 id text PRIMARY KEY, state text NOT NULL CHECK(state IN ('open','resolved')), answer_path text NOT NULL DEFAULT '', updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS library_connections (
 source text NOT NULL, target text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(source,target)
);
-- Additive upgrade: paths remain a compatible API, identities survive moves.
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS document_id uuid NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS library_document_identity ON library_documents(document_id);
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS file_key text NOT NULL DEFAULT '';
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS present boolean NOT NULL DEFAULT true;
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS evidence_scope text NOT NULL DEFAULT 'none' CHECK(evidence_scope IN ('archive','imported','none'));
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS source_id text NOT NULL DEFAULT '';
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS index_version integer NOT NULL DEFAULT 0;
ALTER TABLE library_documents ADD COLUMN IF NOT EXISTS match_title text NOT NULL DEFAULT '';
ALTER TABLE library_chunks ADD COLUMN IF NOT EXISTS match_content text NOT NULL DEFAULT '';
ALTER TABLE library_chunks DROP CONSTRAINT IF EXISTS library_chunks_path_fkey;
ALTER TABLE library_chunks ADD CONSTRAINT library_chunks_path_fkey FOREIGN KEY(path) REFERENCES library_documents(path) ON DELETE CASCADE ON UPDATE CASCADE;
CREATE INDEX IF NOT EXISTS library_match_search ON library_chunks USING gin(to_tsvector('simple',match_content));
CREATE TABLE IF NOT EXISTS library_import_origins (
 path text PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS library_path_history (
 document_id uuid NOT NULL, path text NOT NULL, first_seen timestamptz NOT NULL DEFAULT now(),
 last_seen timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(document_id,path)
);
CREATE TABLE IF NOT EXISTS library_operations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL,
 old_path text NOT NULL, new_path text NOT NULL, content_hash text NOT NULL,
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','complete','conflict')),
 error text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS library_index_jobs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 mode text NOT NULL CHECK(mode IN ('incremental','full')),
 state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','succeeded','failed')),
 seen integer NOT NULL DEFAULT 0, changed integer NOT NULL DEFAULT 0, failed integer NOT NULL DEFAULT 0,
 error text, created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS library_index_errors (
 path text PRIMARY KEY, category text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS publication_state text NOT NULL DEFAULT 'pending';
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS publication_error text;
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS publication_next_attempt timestamptz NOT NULL DEFAULT now();
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS capture_content_hash text NOT NULL DEFAULT '';
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS summary_source_hash text NOT NULL DEFAULT '';
UPDATE page_captures SET publication_state='succeeded' WHERE state='complete'
 AND wiki_indexed_at IS NOT NULL AND wiki_indexed_at>=fetched_at AND publication_state='pending';
ALTER TABLE wiki_questions ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'archive' CHECK(scope IN ('archive','all'));
ALTER TABLE page_captures ADD COLUMN IF NOT EXISTS excluded boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS page_captures_pending ON page_captures(next_attempt_at) WHERE state IN ('pending','retry');
INSERT INTO page_captures(url_hash,url)
 SELECT DISTINCT encode(sha256(convert_to(split_part(url,'#',1),'UTF8')),'hex'),split_part(url,'#',1) FROM browser_visits
 ON CONFLICT(url_hash) DO NOTHING;
"""

from app.ingestion_policy import POLICY_SCHEMA
from app.publication import PUBLICATION_SCHEMA
from app.pdf_extract import PDF_SCHEMA
SCHEMA += POLICY_SCHEMA + PUBLICATION_SCHEMA + PDF_SCHEMA + """
ALTER TABLE library_chunks ADD COLUMN IF NOT EXISTS page_number integer;
ALTER TABLE wiki_questions ADD COLUMN IF NOT EXISTS project text NOT NULL DEFAULT '';
ALTER TABLE wiki_questions ADD COLUMN IF NOT EXISTS source_document_id uuid;
ALTER TABLE wiki_questions ADD COLUMN IF NOT EXISTS retrieval_metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE library_question_status DROP CONSTRAINT IF EXISTS library_question_status_state_check;
ALTER TABLE library_question_status ADD CONSTRAINT library_question_status_state_check CHECK(state IN ('open','resolved','dismissed'));
CREATE TABLE IF NOT EXISTS library_health_dismissals (
 document_id uuid NOT NULL REFERENCES library_documents(document_id) ON DELETE CASCADE,
 revision text NOT NULL, finding text NOT NULL, dismissed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(document_id,revision,finding)
);
CREATE TABLE IF NOT EXISTS library_connection_exports (
 document_id uuid PRIMARY KEY REFERENCES library_documents(document_id) ON DELETE CASCADE,
 state text NOT NULL DEFAULT 'pending', path text NOT NULL DEFAULT '',error text,
 updated_at timestamptz NOT NULL DEFAULT now()
);
"""

if __name__ == "__main__":
    with connect() as db:
        db.execute(SCHEMA)
