-- =========================================================
-- TRACE Platform — Migration 001: Core Schema (PostgreSQL 15+)
-- =========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- 1. users ----------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(150),
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('admin','investigator','operator','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 2. cameras ----------
CREATE TABLE IF NOT EXISTS cameras (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    location        VARCHAR(255),
    rtsp_url        TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','offline','maintenance')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 3. zones ----------
CREATE TABLE IF NOT EXISTS zones (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id       UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    polygon         JSONB NOT NULL,
    zone_type       VARCHAR(30) NOT NULL DEFAULT 'restricted'
                    CHECK (zone_type IN ('restricted','monitored','entry_exit')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 4. videos ----------
CREATE TABLE IF NOT EXISTS videos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id       UUID REFERENCES cameras(id) ON DELETE CASCADE,
    filename        VARCHAR(255),
    file_path       TEXT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    progress        INTEGER NOT NULL DEFAULT 0,
    progress_message VARCHAR(255),
    frames_total    INTEGER,
    frames_processed INTEGER,
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 5. tracks ----------
CREATE TABLE IF NOT EXISTS tracks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id        UUID REFERENCES videos(id) ON DELETE SET NULL,
    camera_id       UUID REFERENCES cameras(id) ON DELETE CASCADE,
    reid_global_id  VARCHAR(64),
    class_label     VARCHAR(30) NOT NULL DEFAULT 'person',
    current_position JSONB DEFAULT '{}',
    previous_position JSONB DEFAULT '{}',
    speed           REAL NOT NULL DEFAULT 0.0,
    direction       VARCHAR(30),
    duration_frames INTEGER NOT NULL DEFAULT 0,
    current_state   VARCHAR(50),
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ
);

-- ---------- 6. track_history ----------
CREATE TABLE IF NOT EXISTS track_history (
    id              BIGSERIAL PRIMARY KEY,
    track_id        UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    frame_number    INTEGER NOT NULL,
    bbox_x          REAL NOT NULL,
    bbox_y          REAL NOT NULL,
    bbox_w          REAL NOT NULL,
    bbox_h          REAL NOT NULL,
    confidence      REAL CHECK (confidence BETWEEN 0 AND 1),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 7. embeddings ----------
CREATE TABLE IF NOT EXISTS embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id        UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    vector          BYTEA NOT NULL,
    model_version   VARCHAR(30),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 8. events ----------
CREATE TABLE IF NOT EXISTS events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id        UUID REFERENCES tracks(id) ON DELETE SET NULL,
    camera_id       UUID REFERENCES cameras(id) ON DELETE CASCADE,
    video_id        UUID REFERENCES videos(id) ON DELETE CASCADE,
    event_type      VARCHAR(50) NOT NULL,
    score           REAL CHECK (score BETWEEN 0 AND 1),
    frame_number    INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 9. keyframes ----------
CREATE TABLE IF NOT EXISTS keyframes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id        UUID REFERENCES videos(id) ON DELETE CASCADE,
    camera_id       UUID REFERENCES cameras(id) ON DELETE CASCADE,
    track_id        UUID REFERENCES tracks(id) ON DELETE SET NULL,
    frame_number    INTEGER NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason          VARCHAR(80) NOT NULL,
    image_path      TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 10. descriptions ----------
CREATE TABLE IF NOT EXISTS descriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id        UUID REFERENCES tracks(id) ON DELETE SET NULL,
    keyframe_id     UUID REFERENCES keyframes(id) ON DELETE CASCADE,
    video_id        UUID REFERENCES videos(id) ON DELETE CASCADE,
    frame_number    INTEGER NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    description     TEXT NOT NULL,
    objects         JSONB DEFAULT '[]',
    confidence      REAL CHECK (confidence BETWEEN 0 AND 1),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 11. conversation_memory ----------
CREATE TABLE IF NOT EXISTS conversation_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    conversation_id TEXT NOT NULL,
    memory_key      TEXT NOT NULL,
    memory_value    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 12. zone_events ----------
CREATE TABLE IF NOT EXISTS zone_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id         UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    track_id        UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    camera_id       UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    event_type      VARCHAR(20) NOT NULL
                    CHECK (event_type IN ('enter','exit','dwell')),
    dwell_seconds   INTEGER,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 10. anomalies ----------
CREATE TABLE IF NOT EXISTS anomalies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id) ON DELETE SET NULL,
    track_id        UUID REFERENCES tracks(id) ON DELETE SET NULL,
    camera_id       UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    severity        VARCHAR(20) NOT NULL DEFAULT 'low'
                    CHECK (severity IN ('low','medium','high','critical')),
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','reviewing','resolved','dismissed')),
    resolved_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 11. investigations ----------
CREATE TABLE IF NOT EXISTS investigations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','closed','archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 12. investigation_links ----------
CREATE TABLE IF NOT EXISTS investigation_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    entity_type     VARCHAR(20) NOT NULL
                    CHECK (entity_type IN ('track','event','anomaly','video')),
    entity_id       UUID NOT NULL,
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Indexes for performance ----------
CREATE INDEX IF NOT EXISTS idx_tracks_video_id ON tracks(video_id);
CREATE INDEX IF NOT EXISTS idx_tracks_camera_id ON tracks(camera_id);
CREATE INDEX IF NOT EXISTS idx_track_history_track_id ON track_history(track_id);
CREATE INDEX IF NOT EXISTS idx_events_camera_id ON events(camera_id);
CREATE INDEX IF NOT EXISTS idx_events_track_id ON events(track_id);
CREATE INDEX IF NOT EXISTS idx_events_video_id ON events(video_id);
CREATE INDEX IF NOT EXISTS idx_keyframes_video_id ON keyframes(video_id);
CREATE INDEX IF NOT EXISTS idx_keyframes_track_id ON keyframes(track_id);
CREATE INDEX IF NOT EXISTS idx_descriptions_video_id ON descriptions(video_id);
CREATE INDEX IF NOT EXISTS idx_descriptions_track_id ON descriptions(track_id);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_conversation_id ON conversation_memory(conversation_id);
CREATE INDEX IF NOT EXISTS idx_zone_events_zone_id ON zone_events(zone_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_camera_id ON anomalies(camera_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status);
CREATE INDEX IF NOT EXISTS idx_investigations_user_id ON investigations(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_camera_id ON videos(camera_id);
