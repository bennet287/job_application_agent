from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Boolean, Text, Float, CheckConstraint, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    company_slug = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    role_title = Column(String, nullable=False)
    role_taxonomy = Column(String)
    
    input_type = Column(String)
    source_url = Column(String)
    raw_jd_text = Column(Text)
    human_verified = Column(Boolean, default=False)
    
    must_haves = Column(Text)
    nice_to_haves = Column(Text)
    red_flags = Column(Text)
    
    match_score = Column(Integer)
    auto_reject_reason = Column(String)
    applied = Column(Boolean, default=False)
    is_exploration = Column(Boolean, default=False)
    
    cv_file_path = Column(String)
    cv_file_hash = Column(String)
    cv_variant = Column(String, default='v1')
    
    cover_letter_path = Column(String)
    cover_letter_constraint_type = Column(String)
    cover_letter_constraint_limit = Column(Integer)
    cover_letter_strategy_used = Column(String)
    cover_letter_length = Column(Integer)
    
    llm_model = Column(String)
    llm_temperature = Column(Float)
    prompt_version = Column(String)
    
    date_processed = Column(DateTime)
    process_latency_seconds = Column(Integer)
    
    status = Column(String, default='processed')
    outcome = Column(String, default='pending')
    
    notes = Column(Text)


class DecisionRationale(Base):
    __tablename__ = 'decision_rationales'
    
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'))
    
    match_score = Column(Integer)
    score_reasoning = Column(Text)
    applied_rationale = Column(Text)
    
    what_worked = Column(Text)
    what_to_change = Column(Text)
    
    rationale_path = Column(String, nullable=False)


def init_db(db_path: str):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)