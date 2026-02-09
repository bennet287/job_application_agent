import random
import json
import re
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConstraintProfile:
    type: str = "none"
    limit: Optional[int] = None
    strategy: str = "full"


class AdaptiveCoverLetterGenerator:
    BANNED_PHRASES = {
        "passionate about", "excited to", "thrilled to", "love to",
        "perfect fit", "ideal candidate", "unique combination",
        "think outside the box", "synergy", "leverage my skills",
        "track record of success", "results-oriented", "dynamic",
        "utilize my", "utilizing my"
    }
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def generate_variants(self, jd: Dict, analysis: Dict, cv_facts: Dict) -> Dict[str, str]:
        variants = {}
        variants["full"] = self._generate_full(jd, analysis, cv_facts)
        variants["compress"] = self._generate_compressed(jd, analysis, cv_facts, 1000)
        variants["truncate"] = self._generate_truncated(jd, analysis, cv_facts, 400)
        return variants
    
    def _generate_full(self, jd: Dict, analysis: Dict, cv_facts: Dict) -> str:
        company = jd.get("company_name", "your company")
        role = jd.get("role_title", "the position")
        exp_years = cv_facts.get("years_experience", "")
        
        prompt = f"""Write a complete cover letter for {role} at {company}.

CANDIDATE CV FACTS (USE ONLY THESE):
- Experience: {exp_years if exp_years else "See CV"} years
- Background: {cv_facts.get("summary", "Experienced professional")[:200]}
- Top achievement: {cv_facts.get("key_achievements", [""])[0][:150] if cv_facts.get("key_achievements") else "Delivered successful projects"}

REQUIREMENTS:
1. Opening: State interest in {role} at {company}
2. Body 1: Connect CV background to job requirements
3. Body 2: Mention ONE specific achievement with metrics
4. Closing: Request interview, professional sign-off
5. Use ONLY facts provided above
6. Do NOT use: passionate, excited, thrilled, perfect fit, synergy
7. Total: 200-300 words
8. Format: Just the letter text, no headers or meta commentary

Write the actual cover letter now:"""

        response = self.llm.generate(prompt).strip()
        response = self._clean_meta_text(response)
        
        if len(response) < 100:
            response = self._fallback_letter(jd, cv_facts)
        
        return response
    
    def _generate_compressed(self, jd: Dict, analysis: Dict, cv_facts: Dict, target_chars: int) -> str:
        company = jd.get("company_name", "your company")
        role = jd.get("role_title", "the position")
        exp_years = cv_facts.get("years_experience", "")
        
        prompt = f"""Write a concise cover letter (150 words max) for {role} at {company}.

CV FACTS:
- {exp_years if exp_years else "Experienced"} professional
- {cv_facts.get("key_achievements", [""])[0][:100] if cv_facts.get("key_achievements") else "Proven track record"}

Structure:
1. Interest in role + brief background (1 sentence)
2. One key achievement with metric (1-2 sentences)
3. Closing with contact request (1 sentence)

No buzzwords. Just the letter text:"""

        response = self.llm.generate(prompt).strip()
        response = self._clean_meta_text(response)
        
        if len(response) > target_chars:
            response = response[:target_chars-3] + "..."
        
        return response
    
    def _generate_truncated(self, jd: Dict, analysis: Dict, cv_facts: Dict, limit: int) -> str:
        company = jd.get("company_name", "your company")
        role = jd.get("role_title", "the position")
        
        achievement = cv_facts.get("key_achievements", [""])[0] if cv_facts.get("key_achievements") else ""
        metric_match = re.search(r"(\d+%|\d+\s*(?:million|k|projects))", achievement, re.IGNORECASE)
        metric = metric_match.group(1) if metric_match else "proven results"
        
        template = f"Dear Hiring Manager, I am applying for the {role} position at {company}. With {cv_facts.get('years_experience', 'relevant')} years of experience delivering {metric}, I am confident in my ability to contribute effectively. I look forward to discussing this opportunity. Sincerely,"
        
        prompt = f"""Improve this cover letter (keep under 50 words, same facts):

{template}

Rewrite:"""

        response = self.llm.generate(prompt).strip()
        response = self._clean_meta_text(response)
        
        if len(response) > limit:
            response = response[:limit-3] + "..."
        
        return response
    
    def _clean_meta_text(self, text: str) -> str:
        prefixes = [
            r"^(?:Here is|Here\'s|Below is|Following is).*?:\s*",
            r"^(?:I have written|I\'ve written|This is).*?:\s*",
            r"^(?:Cover letter|Letter):\s*",
            r"^[\"\"\"']+",
        ]
        
        for prefix in prefixes:
            text = re.sub(prefix, "", text, flags=re.IGNORECASE)
        
        suffixes = [
            r"\s*(?:Let me know|Please let me know|I hope|Hope this).*?$",
            r"\s*\[.*?\]\s*$",
        ]
        
        for suffix in suffixes:
            text = re.sub(suffix, "", text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _fallback_letter(self, jd: Dict, cv_facts: Dict) -> str:
        company = jd.get("company_name", "your company")
        role = jd.get("role_title", "the position")
        exp_years = cv_facts.get("years_experience", "relevant")
        
        achievement = cv_facts.get("key_achievements", [""])[0] if cv_facts.get("key_achievements") else "delivered key projects"
        
        return f"""Dear Hiring Manager,

I am writing to apply for the {role} position at {company}. With {exp_years} years of experience in the field, I have developed strong capabilities aligned with your requirements.

In my recent role, I {achievement}. This experience has prepared me to contribute effectively to your team.

I would welcome the opportunity to discuss how my background matches your needs. Thank you for your consideration.

Sincerely,
[Your Name]"""
    
    def validate_against_cv(self, text: str, cv_facts: Dict) -> List[str]:
        """Check text against CV facts - be reasonable."""
        violations = []
        
        # Only check hard facts (years of experience)
        cv_years = cv_facts.get("years_experience")
        if cv_years:
            for match in re.finditer(r"(\d+)\+?\s*years?", text, re.IGNORECASE):
                claimed = match.group(1)
                if claimed != cv_years:
                    violations.append(f"Claims {claimed} years but CV says {cv_years}")
        
        # Check for invented degrees (strict)
        cv_degrees = [d.lower() for d in cv_facts.get("degrees", [])]
        degree_mentions = re.findall(r'\b(MCA|MBA|MSc|MA|BSc|BCA|BA|PhD)\b', text, re.IGNORECASE)
        for degree in degree_mentions:
            if degree.lower() not in cv_degrees:
                violations.append(f"Mentions '{degree}' not found in CV degrees: {cv_facts.get('degrees')}")
        
        # DON'T flag standard professional phrases like "asset to your team", "contribute", etc.
        # These are opinions, not factual claims
        
        return violations
    
    def save(self, application_id: int, company_slug: str, letter: str,
             output_dir: Path, constraint: ConstraintProfile) -> str:
        constraint_tag = f"{constraint.type}{constraint.limit or ''}"
        filename = f"{application_id:04d}_{company_slug}_{constraint_tag}_cl.txt"
        filepath = output_dir / filename
        
        with open(filepath, "w") as f:
            f.write(letter)
        
        import os
        os.chmod(filepath, 0o600)
        
        return str(filepath)
