CREATE SCHEMA memory;
CREATE SCHEMA research;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

CREATE TABLE memory.engrams (
    id text COLLATE "C" PRIMARY KEY CHECK (id ~ '^[0-7][0-9A-HJKMNP-TV-Z]{25}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    content text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    parent_id text REFERENCES memory.engrams(id),
    public_state text NOT NULL DEFAULT 'visible' CHECK (public_state IN ('visible','tombstoned','quarantined')),
    reason text CHECK (reason IN ('privacy','spam','safety','legal','other')),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
);
CREATE INDEX engrams_visible_recent ON memory.engrams(id DESC) WHERE public_state='visible';
CREATE INDEX engrams_search ON memory.engrams USING gin(search_vector) WHERE public_state='visible';
CREATE INDEX engrams_parent ON memory.engrams(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX engrams_hash ON memory.engrams(sha256);
CREATE TABLE memory.engram_references (
    source_id text REFERENCES memory.engrams(id) NOT NULL,
    target_id text REFERENCES memory.engrams(id) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(source_id,target_id), CHECK (source_id <> target_id)
);
CREATE INDEX references_backlinks ON memory.engram_references(target_id,source_id DESC);
CREATE TABLE memory.moderation_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engram_id text NOT NULL REFERENCES memory.engrams(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    action text NOT NULL CHECK (action IN ('visible','tombstoned','quarantined')),
    reason text NOT NULL CHECK (reason IN ('privacy','spam','safety','legal','other'))
);
CREATE FUNCTION memory.immutable_content() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.id,NEW.created_at,NEW.content,NEW.sha256,NEW.parent_id)
    IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.content,OLD.sha256,OLD.parent_id) THEN
   RAISE EXCEPTION 'engram content is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_content BEFORE UPDATE ON memory.engrams
 FOR EACH ROW EXECUTE FUNCTION memory.immutable_content();
-- No foreign keys to memory: telemetry can be exported/dropped independently.
CREATE TABLE research.requests (
    request_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    cluster text NOT NULL,
    route text NOT NULL,
    method text NOT NULL,
    status integer NOT NULL,
    latency_ms integer NOT NULL,
    request_bytes integer NOT NULL,
    response_bytes integer NOT NULL,
    user_agent_claim text,
    referer_origin text,
    cf_ray text,
    country text,
    asn bigint,
    crawler_observation text,
    self_claimed_identity text,
    behavioral_classification text NOT NULL DEFAULT 'UNKNOWN',
    attribution_confidence integer NOT NULL DEFAULT 0 CHECK (attribution_confidence BETWEEN 0 AND 5),
    events jsonb NOT NULL DEFAULT '[]'
);
CREATE INDEX requests_time ON research.requests(created_at);
CREATE INDEX requests_cluster ON research.requests(cluster,created_at);
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA memory FROM PUBLIC;
