\getenv pw N8N_WRITER_PASSWORD

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_writer') THEN
        CREATE ROLE n8n_writer LOGIN;
    END IF;
END
$$;

ALTER ROLE n8n_writer WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'pw';

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM n8n_writer;
REVOKE CREATE ON SCHEMA public FROM n8n_writer;

GRANT SELECT ON allowed_senders TO n8n_writer;
GRANT INSERT ON emails TO n8n_writer;
GRANT INSERT ON system_events TO n8n_writer;
GRANT INSERT ON emails TO n8n_writer;
GRANT SELECT (gmail_message_id) ON emails TO n8n_writer;
GRANT INSERT ON system_events TO n8n_writer;
GRANT INSERT ON search_run_steps TO n8n_writer;
GRANT SELECT (id) ON search_run_steps TO n8n_writer;
GRANT UPDATE (status, found, "new", message) ON search_run_steps TO n8n_writer;

ALTER TABLE search_run_steps ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS n8n_writer_select ON search_run_steps;
DROP POLICY IF EXISTS n8n_writer_insert ON search_run_steps;
DROP POLICY IF EXISTS n8n_writer_update ON search_run_steps;

CREATE POLICY n8n_writer_select ON search_run_steps
    FOR SELECT TO n8n_writer USING (true);
CREATE POLICY n8n_writer_insert ON search_run_steps
    FOR INSERT TO n8n_writer WITH CHECK (true);
CREATE POLICY n8n_writer_update ON search_run_steps
    FOR UPDATE TO n8n_writer USING (status = 'running') WITH CHECK (true);