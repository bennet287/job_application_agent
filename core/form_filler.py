from datetime import datetime
from pathlib import Path
from typing import Dict


class ConservativeFormFiller:
    def __init__(self):
        pass
    
    def prepare(self, url: str, cv_path: Path, cover_letter: str) -> Dict:
        """Simplified version - just returns data for logging."""
        return {
            'fields_found': {'manual': True},
            'cover_letter_constraint': None,
            'cover_letter_length': len(cover_letter),
            'url': url or 'manual',
            'timestamp': datetime.now().isoformat()
        }
    
    def close(self):
        pass
