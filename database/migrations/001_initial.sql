-- Schema version tracking (append-only)
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main applications table
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identifiers
    company_slug TEXT NOT NULL,
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    role_taxonomy TEXT CHECK(role_taxonomy IN (
        'tech_consultant', 'cyber_consultant', 'implementation_consultant',
        'ai_consultant', 'project_consultant', 'strategy_consultant'
    )),
    
    -- Input
    input_type TEXT CHECK(input_type IN ('url', 'pasted')),
    source_url TEXT,
    raw_jd_text TEXT,
    human_verified BOOLEAN DEFAULT 0,
    human_corrections TEXT,
    
    -- Parsed JD
    location TEXT,
    salary_range TEXT,
    must_haves TEXT,
    nice_to_haves TEXT,
    red_flags TEXT,
    
    -- Decision
    match_score INTEGER,
    auto_reject_reason TEXT,
    applied BOOLEAN DEFAULT 0,
    is_exploration BOOLEAN DEFAULT 0,
    
    -- CV
    cv_file_path TEXT,
    cv_docx_path TEXT,
    cv_changes_made TEXT,
    cv_file_hash TEXT,
    cv_variant TEXT DEFAULT 'v1',
    
    -- Cover letter (ADAPTIVE CONSTRAINT ADDED)
    cover_letter_path TEXT,
    cover_letter_constraint_type TEXT CHECK(cover_letter_constraint_type IN (
        'none', 'chars', 'words', 'file'
    )),
    cover_letter_constraint_limit INTEGER,
    cover_letter_strategy_used TEXT CHECK(cover_letter_strategy_used IN (
        'full', 'compress', 'truncate', 'custom'
    )),
    cover_letter_length INTEGER,
    cover_letter_opening_type TEXT,
    cover_letter_company_ref TEXT,
    cover_letter_human_edit_seconds INTEGER,
    
    -- LLM context
    llm_model TEXT,
    llm_temperature REAL,
    prompt_version TEXT,
    
    -- Timeline
    date_processed TIMESTAMP,
    date_applied TIMESTAMP,
    process_latency_seconds INTEGER,
    
    -- Outcome
    status TEXT DEFAULT 'processed',
    outcome TEXT DEFAULT 'pending',
    outcome_date DATE,
    rejection_reason TEXT,
    decision_latency_days INTEGER,
    
    notes TEXT
);

CREATE INDEX idx_company_outcome ON applications(company_slug, outcome);
CREATE INDEX idx_taxonomy_score ON applications(role_taxonomy, match_score);
CREATE INDEX idx_exploration ON applications(is_exploration, outcome);
CREATE INDEX idx_prompt_version ON applications(prompt_version);
CREATE INDEX idx_cl_constraint ON applications(cover_letter_constraint_type, cover_letter_strategy_used);

INSERT INTO schema_version (version) VALUES (1);