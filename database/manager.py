# Remove this - it's unused and shadows the session parameter
# from requests import session

from sqlalchemy.orm import Session
from typing import Dict, Optional, Callable  # Add Callable


class DatabaseManager:
    def __init__(self, session_factory: Callable):  # Type hint for clarity
        self.session_factory = session_factory  # Rename for clarity
    
    def create_application(self, data: Dict) -> int:
        from database.models import Application
        
        session = self.session_factory()  # Create instance
        try:
            app = Application(**data)
            session.add(app)
            session.commit()
            app_id = app.id
            return app_id
        finally:
            session.close()
    
    def update_application(self, app_id: int, updates: Dict):
        from database.models import Application
        
        session = self.session_factory()
        try:
            app = session.query(Application).filter_by(id=app_id).first()
            if app:
                for key, value in updates.items():
                    setattr(app, key, value)
                session.commit()
        finally:
            session.close()