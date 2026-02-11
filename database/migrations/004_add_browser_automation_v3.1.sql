-- Migration 004: Add browser automation metrics for v3.1 hybrid architecture

-- Add v3.1 columns to applications table
ALTER TABLE applications ADD COLUMN automation_mode TEXT DEFAULT 'manual';
ALTER TABLE applications ADD COLUMN stop_reason TEXT;
ALTER TABLE applications ADD COLUMN actions_taken INTEGER DEFAULT 0;
ALTER TABLE applications ADD COLUMN actions_failed INTEGER DEFAULT 0;
ALTER TABLE applications ADD COLUMN success_rate REAL;
ALTER TABLE applications ADD COLUMN avg_latency REAL;
ALTER TABLE applications ADD COLUMN screenshot_path TEXT;
ALTER TABLE applications ADD COLUMN metrics_json TEXT;

-- Create action_metrics table for detailed observability
CREATE TABLE action_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    
    -- Action details
    action_type TEXT,
    action_raw TEXT,
    
    -- Execution result
    success BOOLEAN DEFAULT 0,
    
    -- Performance metrics
    latency_ms INTEGER,
    
    -- Error categorization
    error_category TEXT,
    
    -- DOM state tracking
    dom_hash_before TEXT,
    dom_hash_after TEXT,
    dom_changed BOOLEAN DEFAULT 0,
    
    -- Retry tracking
    retry_count INTEGER DEFAULT 0,
    
    -- Confidence score for fuzzy matching
    confidence REAL,
    
    -- Error details
    error_message TEXT,
    
    -- Timestamp
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE INDEX idx_action_metrics_app ON action_metrics(application_id);
CREATE INDEX idx_action_metrics_success ON action_metrics(success);
CREATE INDEX idx_action_metrics_category ON action_metrics(error_category);

-- Mark migration complete
INSERT INTO schema_version (version) VALUES (4);