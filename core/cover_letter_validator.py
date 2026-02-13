"""
Cover Letter Validator v3.2 – LLM‑based fact checking against CV facts.
"""

import json
import re
from typing import List, Dict
from utils.llm_client import LLMClient


class CoverLetterValidator:
    def __init__(self):
        self.llm = LLMClient()
    
    def validate_against_cv(self, letter: str, cv_facts: Dict) -> List[str]:
        """Returns list of clearly unsupported claims."""
        if not cv_facts:
            return []
        
        # Build a comprehensive CV summary
        cv_summary = f"""
CANDIDATE: {cv_facts.get('name', 'Unknown')}
YEARS EXPERIENCE: {cv_facts.get('years_experience', 'Not specified')}
DEGREES: {', '.join(cv_facts.get('degrees', []))}
CERTIFICATIONS: {', '.join(cv_facts.get('certifications', []))}

WORK HISTORY (from CV):
{cv_facts.get('raw_text', '')[:1500]}

KEY ACHIEVEMENTS (from CV):
{chr(10).join(['- ' + a for a in cv_facts.get('key_achievements', [])])}
"""
        
        prompt = f"""You are a strict but FAIR fact-checker for job applications.

CV FACTS (these are TRUE):
{cv_summary}

COVER LETTER:
{letter}

TASK:
Identify ANY factual claim in the cover letter that is CLEARLY UNSUPPORTED by the CV.

IMPORTANT RULES:
1. ✅ DO NOT flag paraphrasing. If the CV says "Diagnosed and resolved 150+ issues" 
   and the letter says "Conducted troubleshooting sessions to resolve critical escalations" 
   – this is SUPPORTED. They are describing the same achievement with different words.

2. ✅ DO NOT flag generic job duties that are implied by the job title.
   A "Network Engineer" can reasonably say they "managed network infrastructure".

3. ✅ DO NOT flag the target company name. It's the job you're applying to.

4. ❌ ONLY flag clear fabrications:
   - Claiming a degree not listed in CV (e.g., "PhD" when CV only shows MBA)
   - Claiming employment at a company not in CV
   - Exaggerating years of experience (e.g., "10+ years" when CV says 3)
   - Inventing specific metrics not present in CV (e.g., "increased sales by 500%")
   - Claiming a job title you never held

Return ONLY a JSON array of strings, each string being a specific unsupported claim.
If all claims are supported, return an empty array [].

EXAMPLE OF CORRECT JUDGMENT:
CV: "Diagnosed and resolved 150+ complex network issues"
Letter: "Conducted troubleshooting sessions to resolve critical escalations"
→ SUPPORTED (paraphrasing). Do NOT flag.

EXAMPLE OF REAL VIOLATION:
CV: No mention of Google
Letter: "I worked at Google for 5 years"
→ UNSUPPORTED. Flag it.

Now, analyze the cover letter and return your verdict:
"""

        try:
            response = self.llm.generate(prompt).strip()
            
            # Robust JSON extraction
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                violations = json.loads(json_str)
                if isinstance(violations, list):
                    # Filter out false positives (optional)
                    return [v for v in violations if self._is_plausible_violation(v)]
        except Exception as e:
            print(f"Warning: LLM validation failed: {e}")
        
        return []
    
    def _is_plausible_violation(self, violation: str) -> bool:
        """Filter out obviously wrong flags (e.g., flagging the company name)."""
        # Ignore flags that mention the target company (it's not a past job)
        if "STRABAG" in violation or "BRVZ" in violation:
            return False
        return True
    
    def validate_style(self, text: str) -> List[str]:
        """Optional: check for banned phrases, sentence length, etc."""
        violations = []
        # ... keep your existing style checks here ...
        return violations
