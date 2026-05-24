-- Incident grouping and alert suppression tracking.

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    max_severity TEXT NOT NULL,
    max_risk_score INTEGER NOT NULL,
    article_count INTEGER NOT NULL,
    sources TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_last_seen_at ON incidents(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_incidents_max_severity ON incidents(max_severity);

CREATE TABLE IF NOT EXISTS incident_alerts (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    severity TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    alerted_at TEXT NOT NULL,
    escalation INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_alerts_incident_id ON incident_alerts(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_alerted_at ON incident_alerts(alerted_at);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_channel ON incident_alerts(channel);
