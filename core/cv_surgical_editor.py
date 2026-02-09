from pathlib import Path
from typing import Dict, List
from docx import Document


class SurgicalCVEditor:
    def __init__(self, master_cv_path: Path, llm_client):
        self.master_cv_path = master_cv_path
        self.llm = llm_client
        self.output_dir = master_cv_path.parent / "cv_versions"
        self.output_dir.mkdir(exist_ok=True)
    
    def create_tailored_cv(self, company: str, role: str, jd_data: Dict, analysis: Dict, cv_facts: Dict, max_changes: int = 3):
        """Return master CV for now."""
        return {
            "pdf": str(self.master_cv_path),
            "changes": [],
            "hash": "master"
        }
    
    def _extract_bullets(self):
        try:
            doc = Document(self.master_cv_path)
            return [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        except:
            return []
    
    def _validate_change(self, change, bullets):
        idx = change.get("bullet_index", -1)
        return 0 <= idx < len(bullets)
    
    def _apply_changes(self, bullets, changes):
        new_bullets = bullets.copy()
        for change in changes:
            idx = change.get("bullet_index", -1)
            if 0 <= idx < len(new_bullets):
                new_bullets[idx] = change.get("new", new_bullets[idx])
        return new_bullets
