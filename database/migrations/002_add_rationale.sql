CREATE TABLE decision_rationales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    match_score INTEGER,
    score_reasoning TEXT,
    key_gaps TEXT,
    applied_despite_gaps BOOLEAN,
    applied_rationale TEXT,
    
    what_worked TEXT,
    what_to_change TEXT,
    
    rationale_path TEXT NOT NULL,
    
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

CREATE INDEX idx_rationale_app ON decision_rationales(application_id);

INSERT INTO schema_version (version) VALUES (2);