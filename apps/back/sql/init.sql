-- =========================================================
-- Extensions
-- =========================================================
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector(for vector search)
CREATE EXTENSION IF NOT EXISTS ltree;

-- =========================================================
-- 1. users
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    username        TEXT NOT NULL UNIQUE,
    -- password_hash   TEXT NOT NULL,
    country_code    TEXT,
    user_language   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 2. keywords
-- =========================================================
CREATE TABLE IF NOT EXISTS keywords (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    source_id       TEXT UNIQUE,    -- unique identifier for the keyword from the source
    label           TEXT NOT NULL,
    definition      TEXT,
    parent_id       UUID REFERENCES keywords(id) ON DELETE SET NULL,
    synonyms        TEXT[],  -- array of synonyms
    keyword_type    TEXT,
    embedding       vector(	1024),  -- for BAAI/bge-m3
    path            ltree NOT NULL,      -- for hierarchical relationships
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- create GIST index for ltree path to support hierarchical queries
CREATE INDEX IF NOT EXISTS idx_keywords_path_gist ON keywords USING GIST (path);
CREATE INDEX IF NOT EXISTS idx_keywords_parent_id ON keywords (parent_id);


-- create a trigger to automatically set the path of a keyword based on its parent_id
CREATE OR REPLACE FUNCTION keywords_set_path()
RETURNS TRIGGER AS $$
DECLARE
    parent_path ltree;
BEGIN
    -- use the keyword's id as the path segment, replacing '-' with '_' to conform to ltree format
    NEW.path := replace(NEW.id::text, '-', '_')::ltree;

    IF NEW.parent_id IS NOT NULL THEN
        SELECT path INTO parent_path FROM keywords WHERE id = NEW.parent_id;
        IF parent_path IS NULL THEN
            RAISE EXCEPTION 'parent_id % not found', NEW.parent_id;
        END IF;
        NEW.path := parent_path || NEW.path;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_keywords_set_path
BEFORE INSERT OR UPDATE OF parent_id ON keywords
FOR EACH ROW
EXECUTE FUNCTION keywords_set_path();

-- if a keyword's path changes, update the paths of all its descendants to reflect the new hierarchy
CREATE OR REPLACE FUNCTION keywords_cascade_path()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.path IS DISTINCT FROM OLD.path THEN
        UPDATE keywords
        SET path = NEW.path || subpath(path, nlevel(OLD.path))
        WHERE path <@ OLD.path
          AND id <> NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_keywords_cascade_path
AFTER UPDATE OF path ON keywords
FOR EACH ROW
EXECUTE FUNCTION keywords_cascade_path();

-- =========================================================
-- 3. user_keywords
--    relationship table between users and keywords, with interest level.
-- =========================================================
CREATE TABLE IF NOT EXISTS user_keywords (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    keyword_id      UUID   NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    interest_level  REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_user_keywords_user ON user_keywords(user_id);

-- =========================================================
-- 4. articles
-- =========================================================
CREATE TABLE IF NOT EXISTS articles (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    title           TEXT NOT NULL,
    link            TEXT NOT NULL UNIQUE,
    snippet         TEXT,
    published_at    TIMESTAMPTZ,
    source          TEXT,
    article_language    TEXT,
    article_type    TEXT,  -- e.g., "news", "discussion", "research"
    content         TEXT,
    content_status  TEXT DEFAULT 'pending',  -- e.g., "pending", "completed", "failed"
    content_error   TEXT,  -- error message if content fetching failed
    embedding       vector(1024),            -- for BAAI/bge-m3
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    discarded       BOOLEAN DEFAULT FALSE,
    discarded_reason TEXT
);

-- vector search index for articles embedding
CREATE INDEX IF NOT EXISTS idx_articles_embedding
    ON articles USING hnsw (embedding vector_cosine_ops);

-- TODO: Consider use url hash as unique identifier if using mutiple db

-- =========================================================
-- 5. events
-- =========================================================
CREATE TABLE IF NOT EXISTS events (
    id                          UUID PRIMARY KEY DEFAULT uuidv7(),
    title                       TEXT NOT NULL,
    summary                     TEXT,
    published_at_range_start    TIMESTAMPTZ,
    published_at_range_end      TIMESTAMPTZ,
    confidence_score            REAL,
    importance_score            REAL,
    embedding                   vector(1024),  -- for BAAI/bge-m3
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 6. user_article_interactions
-- =========================================================
CREATE TABLE IF NOT EXISTS user_article_interactions (
    user_id              UUID NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    article_id           UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    interaction_type     TEXT NOT NULL,
    interaction_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, article_id, interaction_type, interaction_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_uai_user    ON user_article_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_uai_article ON user_article_interactions(article_id);

-- =========================================================
-- 7. user_event_interactions
-- =========================================================
CREATE TABLE IF NOT EXISTS user_event_interactions (
    user_id              UUID NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    event_id             UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    interaction_type     TEXT NOT NULL,
    interaction_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);

-- =========================================================
-- 8. event_article_relationships
-- =========================================================
CREATE TABLE IF NOT EXISTS event_article_relationships (
    event_id   UUID NOT NULL REFERENCES events(id)   ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_ear_article ON event_article_relationships(article_id);

-- =========================================================
-- 9. event_keyword_relationships
-- =========================================================
CREATE TABLE IF NOT EXISTS event_keyword_relationships (
    event_id        UUID NOT NULL REFERENCES events(id)   ON DELETE CASCADE,
    keyword_id      UUID   NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    relevance_score REAL,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_ekr_keyword ON event_keyword_relationships(keyword_id);


-- =========================================================
-- 10. sessions
-- =========================================================

CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  BYTEA NOT NULL UNIQUE
                CHECK (octet_length(token_hash) = 32),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id
    ON sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
    ON sessions (expires_at);