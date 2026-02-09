import re
from typing import Tuple, List


class CoverLetterValidator:
    BANNED_PHRASES = {
        'passionate about', 'excited to', 'thrilled to', 'love to',
        'perfect fit', 'ideal candidate', 'unique combination',
        'think outside the box', 'synergy', 'leverage my skills',
        'track record of success', 'results-oriented', 'dynamic',
        'utilize my', 'utilizing my'
    }
    
    def validate(self, text: str) -> Tuple[bool, List[str]]:
        violations = []
        text_lower = text.lower()
        
        # Check banned phrases
        for phrase in self.BANNED_PHRASES:
            if phrase in text_lower:
                violations.append(f"BANNED_PHRASE: '{phrase}'")
        
        # Check sentence length variation
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        
        if len(sentences) >= 3:
            lengths = [len(s.split()) for s in sentences]
            short_pct = sum(1 for l in lengths if l < 8) / len(lengths)
            long_pct = sum(1 for l in lengths if l > 20) / len(lengths)
            
            if short_pct < 0.2:
                violations.append(f"LOW_VARIATION: Only {short_pct:.0%} short sentences (target 30%)")
            if long_pct < 0.15:
                violations.append(f"LOW_VARIATION: Only {long_pct:.0%} long sentences (target 20%)")
        
        # Check for company reference
        if not re.search(r'\b(your|you|company|organization)\b', text_lower):
            violations.append("NO_COMPANY_REFERENCE: Must reference specific company context")
        
        # Check for specific detail (project, metric, tool)
        has_specific = bool(re.search(r'\b\d+%|\d+x|\$?\d+K|\b(project|initiative|engagement)\b', text))
        if not has_specific:
            violations.append("NO_SPECIFIC_DETAIL: Include concrete project or metric")
        
        return len(violations) == 0, violations