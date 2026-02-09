import sqlite3
import datetime
from typing import Tuple, Dict


class FatigueMonitor:
    def __init__(self, db_path: str, daily_cap: int = 5, min_hours: float = 0.5):
        self.db_path = db_path
        self.daily_cap = daily_cap
        self.min_hours = min_hours
    
    def check_and_enforce(self) -> Tuple[bool, Dict]:
        conn = sqlite3.connect(self.db_path)
        
        today_count = conn.execute("""
            SELECT COUNT(*) FROM applications
            WHERE date(date_processed) = date('now', 'localtime')
        """).fetchone()[0]
        
        last_app = conn.execute("""
            SELECT datetime(date_processed, 'localtime')
            FROM applications
            WHERE date_processed IS NOT NULL
            ORDER BY date_processed DESC LIMIT 1
        """).fetchone()
        
        status = {
            'reviewed_today': today_count,
            'daily_cap': self.daily_cap,
            'remaining': max(0, self.daily_cap - today_count)
        }
        
        if today_count >= self.daily_cap:
            conn.close()
            return False, {
                'state': 'DAILY_CAP_REACHED',
                'message': f"Hard stop: {self.daily_cap} applications today.",
                'resume_time': 'Tomorrow',
                **status
            }
        
        if last_app:
            last_time = datetime.datetime.fromisoformat(last_app[0])
            hours_since = (datetime.datetime.now() - last_time).total_seconds() / 3600
            
            if hours_since < self.min_hours:
                wait_mins = int((self.min_hours - hours_since) * 60)
                conn.close()
                return False, {
                    'state': 'RAPID_SUCCESSION',
                    'message': f"Wait {wait_mins}m between applications.",
                    'resume_time': f"In {wait_mins} minutes",
                    **status
                }
        
        conn.close()
        return True, {
            'state': 'PROCEED',
            'message': f"Proceed. {status['remaining']} remaining today.",
            **status
        }