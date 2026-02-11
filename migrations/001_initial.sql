-- Phoenix Agent - Initial Database Schema

CREATE TABLE IF NOT EXISTS refactoring_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    files_modified JSONB DEFAULT '[]'::jsonb,
    risk_score FLOAT DEFAULT 0.0,
    metrics_before JSONB DEFAULT '{}'::jsonb,
    metrics_after JSONB DEFAULT '{}'::jsonb,
    pr_url TEXT,
    outcome VARCHAR(32) DEFAULT 'success',
    duration_seconds FLOAT DEFAULT 0.0,
    goal_description TEXT,
    target_path TEXT
);

CREATE TABLE IF NOT EXISTS team_preferences (
    id SERIAL PRIMARY KEY,
    key VARCHAR(256) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    rationale TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_history_session ON refactoring_history(session_id);
CREATE INDEX IF NOT EXISTS idx_history_outcome ON refactoring_history(outcome);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON refactoring_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_preferences_key ON team_preferences(key);
