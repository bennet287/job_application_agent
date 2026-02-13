"""
Database models for Job Application Agent v3.1
Includes browser automation metrics and observability
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Boolean, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Company & Role
    company_slug = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    role_title = Column(String, nullable=False)
    role_taxonomy = Column(String)
    
    # Source
    input_type = Column(String)
    source_url = Column(String)
    raw_jd_text = Column(Text)
    human_verified = Column(Boolean, default=False)
    
    # Requirements
    must_haves = Column(Text)
    nice_to_haves = Column(Text)
    red_flags = Column(Text)
    
    # Scoring
    match_score = Column(Integer)
    auto_reject_reason = Column(String)
    applied = Column(Boolean, default=False)
    is_exploration = Column(Boolean, default=False)
    
    # CV
    cv_file_path = Column(String)
    cv_file_hash = Column(String)
    cv_variant = Column(String, default='v1')
    
    # Cover Letter
    cover_letter_path = Column(String)
    cover_letter_constraint_type = Column(String)
    cover_letter_constraint_limit = Column(Integer)
    cover_letter_strategy_used = Column(String)
    cover_letter_length = Column(Integer)
    
    # ========================================================================
    # BROWSER AUTOMATION v3.1 - New fields for hybrid architecture
    # ========================================================================
    
    automation_mode = Column(String, default='manual')
    stop_reason = Column(String)
    actions_taken = Column(Integer, default=0)
    actions_failed = Column(Integer, default=0)
    success_rate = Column(Float)
    avg_latency = Column(Float)
    screenshot_path = Column(String)
    metrics_json = Column(Text)
    
    # ========================================================================
    
    # LLM Metadata
    llm_model = Column(String)
    llm_temperature = Column(Float)
    prompt_version = Column(String)
    
    # Timing
    date_processed = Column(DateTime)
    process_latency_seconds = Column(Integer)
    
    # Outcome
    status = Column(String, default='processed')
    outcome = Column(String, default='pending')
    
    notes = Column(Text)
    
    # Relationships
    decision_rationale = relationship("DecisionRationale", back_populates="application", uselist=False)
    action_metrics = relationship("ActionMetric", back_populates="application", cascade="all, delete-orphan")


class DecisionRationale(Base):
    __tablename__ = 'decision_rationales'
    
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'), nullable=False)
    
    match_score = Column(Integer)
    score_reasoning = Column(Text)
    applied_rationale = Column(Text)
    
    what_worked = Column(Text)
    what_to_change = Column(Text)
    
    rationale_path = Column(String, nullable=False)
    
    application = relationship("Application", back_populates="decision_rationale")


class ActionMetric(Base):
    """
    v3.1: Detailed action metrics for observability
    """
    __tablename__ = 'action_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey('applications.id'), nullable=False)
    
    # Action details
    action_type = Column(String)
    action_raw = Column(Text)
    
    # Execution result
    success = Column(Boolean, default=False)
    
    # Performance metrics
    latency_ms = Column(Integer)
    
    # Error categorization
    error_category = Column(String)
    
    # DOM state tracking
    dom_hash_before = Column(String)
    dom_hash_after = Column(String)
    dom_changed = Column(Boolean, default=False)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    
    # Confidence score for fuzzy matching
    confidence = Column(Float)
    
    # Error details
    error_message = Column(Text)
    
    # Timestamp
    timestamp = Column(DateTime)
    
    # Relationship
    application = relationship("Application", back_populates="action_metrics")


def init_db(db_path: str):
    """Initialize database with all tables."""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    db_file = Path(db_path)
    if db_file.exists():
        os.chmod(db_file, 0o600)
    return sessionmaker(bind=engine)


# ========================================================================
# Helper functions for metrics storage
# ========================================================================

def save_application_metrics(session, application_id: int, result: dict):
    """
    Save v3.1 automation metrics to database.
    
    Args:
        session: SQLAlchemy session
        application_id: Application ID
        result: HybridAutomationResult dict
    """
    from datetime import datetime
    
    app = session.query(Application).get(application_id)
    if not app:
        return
    
    # Update high-level metrics
    app.automation_mode = result.get('automation_mode', 'manual')
    app.stop_reason = result.get('stop_reason', '')
    app.actions_taken = len(result.get('actions_taken', []))
    app.actions_failed = len(result.get('errors', []))
    app.success_rate = result.get('metrics_report', {}).get('success_rate', 0.0)
    app.avg_latency = result.get('metrics_report', {}).get('avg_latency', 0.0)
    app.screenshot_path = result.get('screenshot_path', '')
    
    # Store detailed metrics as JSON
    import json
    app.metrics_json = json.dumps(result.get('metrics_report', {}))
    
    # Save individual action metrics
    for metric in result.get('metrics_report', {}).get('actions', []):
        action_metric = ActionMetric(
            application_id=application_id,
            action_type=metric.get('action', '').split('|')[0] if '|' in metric.get('action', '') else 'UNKNOWN',
            action_raw=metric.get('action', ''),
            success=metric.get('success', False),
            latency_ms=int(metric.get('latency', 0) * 1000),
            error_category=categorize_error(metric.get('error')),
            dom_changed=metric.get('dom_changed', False),
            retry_count=metric.get('retry_count', 0),
            timestamp=datetime.now()
        )
        session.add(action_metric)
    
    session.commit()


def categorize_error(error_msg: str) -> str:
    """Categorize error message into standard categories."""
    if not error_msg:
        return None
    
    error_lower = error_msg.lower()
    
    if 'validation' in error_lower:
        return 'VALIDATION'
    elif 'timeout' in error_lower or 'wait' in error_lower:
        return 'TIMEOUT'
    elif 'stale' in error_lower:
        return 'STALE_ELEMENT'
    elif 'not found' in error_lower or 'unresolved' in error_lower:
        return 'ELEMENT_NOT_FOUND'
    elif 'confidence' in error_lower:
        return 'LOW_CONFIDENCE'
    else:
        return 'EXECUTION'