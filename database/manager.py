from sqlalchemy.orm import Session
from typing import Dict, Optional


class DatabaseManager:
    def __init__(self, session_factory):
        self.Session = session_factory
    
    def create_application(self, data: Dict) -> int:
        from database.models import Application
        
        session = self.Session()
        app = Application(**data)
        session.add(app)
        session.commit()
        app_id = app.id
        session.close()
        return app_id
    
    def update_application(self, app_id: int, updates: Dict):
        from database.models import Application
        
        session = self.Session()
        app = session.query(Application).filter_by(id=app_id).first()
        if app:
            for key, value in updates.items():
                setattr(app, key, value)
            session.commit()
        session.close()