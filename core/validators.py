import re
from typing import Dict, List, Tuple, Set


class CVValidator:
    def __init__(self, master_cv: str):
        self.master_cv = master_cv
        self.master_numbers = self._extract_numbers(master_cv)
        self.master_nouns = self._extract_technical_nouns(master_cv)
    
    def validate_change(self, change: Dict) -> Tuple[bool, List[str]]:
        violations = []
        original = change.get('original', '')
        new = change.get('new', '')
        
        if not original or not new:
            return False, ["Empty text"]
        
        orig_nums = self._extract_numbers(original)
        new_nums = self._extract_numbers(new)
        if new_nums - orig_nums - self.master_numbers:
            violations.append("HALLUCINATED_METRICS")
        
        inflation = [
            (r'experience with', r'expert in'),
            (r'familiar with', r'proficient in'),
            (r'assisted', r'led'),
        ]
        
        for weak, strong in inflation:
            if re.search(weak, original.lower()) and re.search(strong, new.lower()):
                violations.append(f"INFLATION: {weak} -> {strong}")
        
        return len(violations) == 0, violations
    
    def _extract_numbers(self, text: str) -> Set[str]:
        pattern = r'\d+%|\d+x|\$\d+|\d+\s*(?:hours|days|weeks)'
        return set(re.findall(pattern, text, re.I))
    
    def _extract_technical_nouns(self, text: str) -> Set[str]:
        pattern = r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b'
        candidates = re.findall(pattern, text)
        common = {'The', 'A', 'An', 'I', 'We', 'They'}
        return {c for c in candidates if c not in common}


class CoverLetterValidator:
    BANNED = {
        'passionate about', 'excited to', 'thrilled to',
        'perfect fit', 'synergy', 'leverage my skills'
    }
    
    def validate(self, text: str) -> Tuple[bool, List[str]]:
        violations = []
        text_lower = text.lower()
        
        for phrase in self.BANNED:
            if phrase in text_lower:
                violations.append(f"BANNED: {phrase}")
        
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if len(sentences) >= 3:
            lengths = [len(s.split()) for s in sentences]
            short = sum(1 for l in lengths if l < 8) / len(lengths)
            long = sum(1 for l in lengths if l > 20) / len(lengths)
            
            if short < 0.2:
                violations.append("LOW_SHORT_VARIATION")
            if long < 0.15:
                violations.append("LOW_LONG_VARIATION")
        
        return len(violations) == 0, violations