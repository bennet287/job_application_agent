import json
import hashlib
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from docx import Document


@dataclass
class BulletFingerprint:
    index: int
    section: str
    text_hash: str
    style_hash: str


class SurgicalCVEditor:
    def __init__(self, master_cv_path: str, llm_client):
        self.master_path = Path(master_cv_path)
        self.llm = llm_client
        self.doc = Document(master_cv_path)
        self.bullet_map = self._index_bullets()
        self.master_fingerprints = self._compute_fingerprints()
        self.approved_changes = {}
    
    def _index_bullets(self) -> Dict[int, Dict]:
        bullets = {}
        current_section = "Unknown"
        
        for i, para in enumerate(self.doc.paragraphs):
            if para.style.name.startswith('Heading'):
                current_section = para.text.strip()
                continue
            
            text = para.text.strip()
            if text and (para.style.name.startswith('List') or 
                        text.startswith('•') or text.startswith('-')):
                bullets[i] = {
                    'text': text,
                    'style': para.style.name,
                    'section': current_section,
                    'original_text': para.text
                }
        
        return bullets
    
    def _compute_fingerprints(self) -> Dict[int, BulletFingerprint]:
        fingerprints = {}
        
        for idx, info in self.bullet_map.items():
            para = self.doc.paragraphs[idx]
            
            normalized = ' '.join(info['text'].lower().split())
            text_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            
            if para.runs:
                r = para.runs[0]
                style_sig = f"{r.font.name}|{r.font.size}|{r.bold}|{r.italic}"
                style_hash = hashlib.sha256(style_sig.encode()).hexdigest()[:8]
            else:
                style_hash = "no_runs"
            
            fingerprints[idx] = BulletFingerprint(
                index=idx,
                section=info['section'],
                text_hash=text_hash,
                style_hash=style_hash
            )
        
        self._save_master_state(fingerprints)
        return fingerprints
    
    def _save_master_state(self, fingerprints: Dict[int, BulletFingerprint]):
        state_path = self.master_path.parent / '.cv_master_state.json'
        state = {
            'master_path': str(self.master_path),
            'timestamp': datetime.now().isoformat(),
            'bullet_count': len(fingerprints),
            'fingerprints': {
                str(idx): {
                    'section': fp.section,
                    'text_hash': fp.text_hash,
                    'style_hash': fp.style_hash
                }
                for idx, fp in fingerprints.items()
            }
        }
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def generate_diff(self, jd: Dict, analysis: Dict, max_changes: int = 3) -> List[Dict]:
        from config.prompts import CV_BULLET_REWRITE_PROMPT
        
        bullet_list = []
        for idx, info in list(self.bullet_map.items())[:15]:
            bullet_list.append(f"{idx}: {info['text'][:100]}")
        
        prompt = CV_BULLET_REWRITE_PROMPT.format(
            max_changes=max_changes,
            keywords=json.dumps(jd.get('tools_mentioned', [])),
            must_haves=json.dumps(jd.get('must_haves', [])),
            bullets='\n'.join(bullet_list)
        )
        
        response = self.llm.generate(prompt)
        
        try:
            suggestions = json.loads(response)
        except json.JSONDecodeError:
            return []
        
        validated = []
        for sugg in suggestions[:max_changes]:
            match_idx = self._find_bullet_match(sugg.get('original', ''))
            if match_idx is not None and self._validate_change(sugg):
                validated.append({
                    'index': match_idx,
                    'original': sugg['original'],
                    'new': sugg['new'],
                    'reason': sugg.get('reason', 'keyword alignment'),
                    'section': self.bullet_map[match_idx]['section']
                })
        
        return validated
    
    def _find_bullet_match(self, text_fragment: str) -> Optional[int]:
        if not text_fragment:
            return None
        
        for idx, info in self.bullet_map.items():
            if text_fragment.lower() in info['text'].lower():
                return idx
        
        return None
    
    def _validate_change(self, change: Dict) -> bool:
        original = change.get('original', '')
        new = change.get('new', '')
        
        if not original or not new:
            return False
        
        orig_nums = set(re.findall(r'\d+%|\d+x|\$\d+|\d+\s*(?:hours|days|weeks|months)', original, re.I))
        new_nums = set(re.findall(r'\d+%|\d+x|\$\d+|\d+\s*(?:hours|days|weeks|months)', new, re.I))
        
        if new_nums - orig_nums:
            return False
        
        inflation_checks = [
            (r'\bexperience with\b', r'\bexpert in\b'),
            (r'\bfamiliar with\b', r'\bproficient in\b'),
            (r'\bexposure to\b', r'\bspecialized in\b'),
            (r'\bassisted\b', r'\bled\b'),
            (r'\bparticipated\b', r'\bdirected\b'),
        ]
        
        orig_lower = original.lower()
        new_lower = new.lower()
        
        for weak, strong in inflation_checks:
            if re.search(weak, orig_lower) and re.search(strong, new_lower):
                return False
        
        return True
    
    def apply_changes(self, changes: List[Dict], output_path: str) -> str:
        new_doc = Document(self.master_path)
        self.approved_changes = {}
        
        for change in changes:
            idx = change['index']
            if idx >= len(new_doc.paragraphs):
                continue
            
            self.approved_changes[idx] = change
            
            para = new_doc.paragraphs[idx]
            original_runs = para.runs
            
            if original_runs:
                first_run = original_runs[0]
                font_name = first_run.font.name
                font_size = first_run.font.size
                bold = first_run.bold
                italic = first_run.italic
                color = None
                if first_run.font.color and first_run.font.color.rgb:
                    color = first_run.font.color.rgb
                
                para.clear()
                new_run = para.add_run(change['new'])
                
                if font_name:
                    new_run.font.name = font_name
                if font_size:
                    new_run.font.size = font_size
                new_run.bold = bold
                new_run.italic = italic
                if color:
                    new_run.font.color.rgb = color
            else:
                para.text = change['new']
        
        new_doc.save(output_path)
        
        with open(output_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        
        return file_hash
    
    def validate_export(self, output_path: str) -> Tuple[bool, List[str]]:
        new_doc = Document(output_path)
        violations = []
        
        for idx, master_fp in self.master_fingerprints.items():
            if idx >= len(new_doc.paragraphs):
                violations.append(f"Index {idx} out of range")
                continue
            
            new_para = new_doc.paragraphs[idx]
            normalized = ' '.join(new_para.text.lower().split())
            new_text_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            
            is_modified = idx in self.approved_changes
            
            if not is_modified and new_text_hash != master_fp.text_hash:
                violations.append(
                    f"UNINTENDED CHANGE at {idx} ({master_fp.section}): "
                    f"expected {master_fp.text_hash}, got {new_text_hash}"
                )
        
        return len(violations) == 0, violations
    
    def generate_pdf(self, docx_path: str, output_path: str):
        cmd = [
            'soffice',
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(Path(output_path).parent),
            docx_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")
        
        generated = docx_path.replace('.docx', '.pdf')
        if generated != output_path:
            import shutil
            shutil.move(generated, output_path)
        
        return output_path
    
    def create_tailored_cv(self, company: str, role: str, jd_data: Dict, analysis: Dict, cv_facts: Dict, max_changes: int = 3):
        """Actually tailor CV based on JD requirements."""
        # Read current CV bullets
        current_bullets = self._extract_bullets()
        
        if not current_bullets:
            return {'pdf': str(self.master_cv_path), 'changes': [], 'hash': 'master'}
        
        # Build tailoring prompt
        prompt = f"""Tailor these CV bullets for {role} at {company}.

JOB REQUIREMENTS:
Must-haves: {jd_data.get('must_haves', [])}
Nice-to-haves: {jd_data.get('nice_to_haves', [])}

CURRENT CV BULLETS:
{json.dumps(current_bullets[:5], indent=2)}

TAILORING INSTRUCTIONS:
1. Identify which bullets can be improved to match job keywords
2. Suggest MAX {max_changes} rewrites
3. ONLY rephrase existing content - never invent new experience
4. Incorporate job keywords naturally
5. Preserve all numbers and metrics exactly

Return JSON array of changes:
[
  {{
    "bullet_index": 0,
    "original": "original text",
    "new": "improved text with job keywords",
    "reason": "why this improves match"
  }}
]

If no changes needed, return empty array []."""

        try:
            response = self.llm.generate(prompt)
            
            # Parse changes
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                changes = json.loads(json_match.group(1))
            else:
                try:
                    changes = json.loads(response)
                except:
                    changes = []
            
            # Validate changes
            valid_changes = []
            for change in changes:
                if self._validate_change(change, current_bullets):
                    valid_changes.append(change)
            
            if not valid_changes:
                print("No CV changes suggested - current CV is suitable")
                return {
                    'pdf': str(self.master_cv_path),
                    'changes': [],
                    'hash': self._compute_hash(str(self.master_cv_path))
                }
            
            # Apply changes
            new_doc = self._apply_changes(current_bullets, valid_changes)
            
            # Save tailored version
            output_path = self._save_tailored(new_doc, company, role)
            
            return {
                'pdf': str(output_path),
                'changes': valid_changes,
                'hash': self._compute_hash(str(output_path))
            }
            
        except Exception as e:
            print(f"CV tailoring error: {e}")
        return {
            'pdf': str(self.master_cv_path),
            'changes': [],
            'hash': 'master'
        }

def _extract_bullets(self):
    """Extract bullet points from CV."""
    from docx import Document
    try:
        doc = Document(self.master_cv_path)
        bullets = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text and (text.startswith('•') or text.startswith('-') or text.startswith('*') or text[0].isdigit()):
                bullets.append(text)
        return bullets
    except Exception as e:
        print(f"Could not extract bullets: {e}")
        return []

def _validate_change(self, change: dict, current_bullets: list) -> bool:
    """Validate that change is legitimate."""
    idx = change.get('bullet_index', -1)
    if idx < 0 or idx >= len(current_bullets):
        return False
    
    original = change.get('original', '')
    new = change.get('new', '')
    
    # Check original matches
    if current_bullets[idx] != original:
        return False
    
    # Don't invent new numbers
    orig_nums = set(re.findall(r'\d+%|\d+\s*(?:million|k)', original, re.I))
    new_nums = set(re.findall(r'\d+%|\d+\s*(?:million|k)', new, re.I))
    
    if new_nums - orig_nums:
        return False
    
    return True

def _apply_changes(self, bullets: list, changes: list):
    """Apply validated changes."""
    new_bullets = bullets.copy()
    for change in changes:
        idx = change.get('bullet_index', -1)
        if 0 <= idx < len(new_bullets):
            new_bullets[idx] = change.get('new', new_bullets[idx])
    return new_bullets

def _save_tailored(self, bullets: list, company: str, role: str):
    """Save tailored CV."""
    from docx import Document
    from datetime import datetime
    
    doc = Document()
    doc.add_heading(f'{role} - {company}', 0)
    
    for bullet in bullets:
        p = doc.add_paragraph(bullet, style='List Bullet')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_company = re.sub(r'[^\w]', '_', company)[:20]
    safe_role = re.sub(r'[^\w]', '_', role)[:20]
    filename = f'{safe_company}_{safe_role}_{timestamp}.docx'
    output_path = self.output_dir / filename
    doc.save(output_path)
    
    return output_path

def _compute_hash(self, filepath: str) -> str:
    """Compute file hash."""
    import hashlib
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return 'unknown'
    def _extract_bullets(self):
        from docx import Document
        try:
            doc = Document(self.master_cv_path)
            bullets = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text and len(text) > 15:
                    bullets.append(text)
            return bullets
        except:
            return []
    
    def _validate_change(self, change, bullets):
        idx = change.get('bullet_index', -1)
        return 0 <= idx < len(bullets)
    
    def _apply_changes(self, bullets, changes):
        new_bullets = bullets.copy()
        for change in changes:
            idx = change.get('bullet_index', -1)
            if 0 <= idx < len(new_bullets):
                new_bullets[idx] = change.get('new', new_bullets[idx])
        return new_bullets
    
    def _save_tailored(self, bullets, company, role):
        from docx import Document
        from datetime import datetime
        import re
        
        doc = Document()
        doc.add_heading(f'{role} - {company}', 0)
        
        for bullet in bullets:
            doc.add_paragraph(bullet, style='List Bullet')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_company = re.sub(r'[^\w]', '_', company)[:20]
        safe_role = re.sub(r'[^\w]', '_', role)[:20]
        filename = f'{safe_company}_{safe_role}_{timestamp}.docx'
        output_path = self.output_dir / filename
        doc.save(output_path)
        return output_path
    
def _slugify(self, text: str) -> str:
    return re.sub(r'[^\w]+', '_', text.lower()).strip('_')[:50]
    def _extract_bullets(self):
        from docx import Document
        try:
            doc = Document(self.master_cv_path)
            bullets = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text and (text.startswith('') or text.startswith('-') or text.startswith('*')):
                    bullets.append(text)
            return bullets
        except:
            return []
    
    def _validate_change(self, change, current_bullets):
        idx = change.get('bullet_index', -1)
        if idx < 0 or idx >= len(current_bullets):
            return False
        return current_bullets[idx] == change.get('original', '')
    
    def _apply_changes(self, bullets, changes):
        new_bullets = bullets.copy()
        for change in changes:
            idx = change.get('bullet_index', -1)
            if 0 <= idx < len(new_bullets):
                new_bullets[idx] = change.get('new', new_bullets[idx])
        return new_bullets
    
    def _save_tailored(self, bullets, company, role):
        from docx import Document
        from datetime import datetime
        import re
        
        doc = Document()
        doc.add_heading(f'{role} - {company}', 0)
        for bullet in bullets:
            doc.add_paragraph(bullet, style='List Bullet')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_company = re.sub(r'[^\w]', '_', company)[:20]
        safe_role = re.sub(r'[^\w]', '_', role)[:20]
        filename = f'{safe_company}_{safe_role}_{timestamp}.docx'
        output_path = self.output_dir / filename
        doc.save(output_path)
        return output_path
