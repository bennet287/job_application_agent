# database/migrate_v3.1.py
"""
Migration script to add v3.1 columns to existing database
"""

from sqlalchemy import create_engine, text
import sys

def migrate(db_path: str):
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        # Add new columns to applications table
        columns = [
            "automation_mode VARCHAR DEFAULT 'manual'",
            "stop_reason VARCHAR",
            "actions_taken INTEGER DEFAULT 0",
            "actions_failed INTEGER DEFAULT 0",
            "success_rate FLOAT",
            "avg_latency FLOAT",
            "screenshot_path VARCHAR",
            "metrics_json TEXT"
        ]
        
        for col in columns:
            try:
                conn.execute(text(f"ALTER TABLE applications ADD COLUMN {col}"))
                print(f"Added column: {col.split()[0]}")
            except Exception as e:
                print(f"Skipped {col.split()[0]}: {e}")
        
        # Create action_metrics table
        try:
            conn.execute(text("""
                CREATE TABLE action_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    action_type VARCHAR,
                    action_raw TEXT,
                    success BOOLEAN DEFAULT 0,
                    latency_ms INTEGER,
                    error_category VARCHAR,
                    dom_hash_before VARCHAR(8),
                    dom_hash_after VARCHAR(8),
                    dom_changed BOOLEAN DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    confidence FLOAT,
                    error_message TEXT,
                    timestamp DATETIME,
                    FOREIGN KEY (application_id) REFERENCES applications (id)
                )
            """))
            print("Created action_metrics table")
        except Exception as e:
            print(f"Skipped action_metrics: {e}")
        
        conn.commit()
        print("Migration complete")

if __name__ == '__main__':
    migrate('applications.db')