-- Operator-only foundation. No grants to the public API role.
CREATE SCHEMA lab;
REVOKE ALL ON SCHEMA lab FROM PUBLIC;
CREATE TABLE lab.runs (
    run_id uuid PRIMARY KEY,
    experiment_id text NOT NULL CHECK (experiment_id ~ '^EXP-[0-9]{3}$'),
    population_id uuid NOT NULL,
    manifest jsonb NOT NULL CHECK (
        jsonb_typeof(manifest) = 'object'
        AND manifest @> '{"schema_version":"0","track":"lab","synthetic":true}'
        AND manifest ?& ARRAY['run_id','experiment_id','population_id']
        AND manifest->>'run_id' = run_id::text
        AND manifest->>'experiment_id' = experiment_id
        AND manifest->>'population_id' = population_id::text
    ),
    UNIQUE(run_id,experiment_id,population_id)
);
CREATE TABLE lab.events (
    sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    event_id uuid PRIMARY KEY,
    run_id uuid NOT NULL,
    experiment_id text NOT NULL,
    population_id uuid NOT NULL,
    timestamp timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (
        jsonb_typeof(payload) = 'object'
        AND payload @> '{"schema_version":"0"}'
        AND payload ?& ARRAY['event_id','run_id','experiment_id','population_id','timestamp']
        AND payload->>'event_id' = event_id::text
        AND payload->>'run_id' = run_id::text
        AND payload->>'experiment_id' = experiment_id
        AND payload->>'population_id' = population_id::text
        AND (payload->>'timestamp')::timestamptz = timestamp
    ),
    FOREIGN KEY(run_id,experiment_id,population_id) REFERENCES lab.runs(run_id,experiment_id,population_id)
);
CREATE INDEX lab_events_run ON lab.events(run_id,sequence);
CREATE FUNCTION lab.immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Lab records are append-only';
END $$;
CREATE TRIGGER immutable_run BEFORE UPDATE OR DELETE ON lab.runs
    FOR EACH ROW EXECUTE FUNCTION lab.immutable_record();
CREATE TRIGGER immutable_event BEFORE UPDATE OR DELETE ON lab.events
    FOR EACH ROW EXECUTE FUNCTION lab.immutable_record();
CREATE TRIGGER no_truncate_runs BEFORE TRUNCATE ON lab.runs
    FOR EACH STATEMENT EXECUTE FUNCTION lab.immutable_record();
CREATE TRIGGER no_truncate_events BEFORE TRUNCATE ON lab.events
    FOR EACH STATEMENT EXECUTE FUNCTION lab.immutable_record();
REVOKE ALL ON ALL TABLES IN SCHEMA lab FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA lab FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA lab FROM PUBLIC;
