"""
Match Scorer v3.2 – Weighted scoring based on CV facts vs. JD must-haves.
"""

import re
from typing import Dict, List, Optional
from difflib import SequenceMatcher


class MatchScorer:
    # Weights for different categories – adjust to your preference
    WEIGHTS = {
        "degree": 2.0,
        "experience_years": 2.0,
        "certification": 1.5,
        "skill": 1.0,
        "language": 1.0,
        "responsibility": 0.8,
    }

    # Hard reject patterns – if any appear, score = 0
    HARD_REJECT = [
        "citizenship required",
        "security clearance",
        "fluent german required",
        "native german",
        "10+ years",
        "15+ years",
    ]

    def __init__(self, llm_client, master_cv: str, exploration_rate: float = 0.15):
        self.llm = llm_client
        self.master_cv = master_cv
        self.exploration_rate = exploration_rate

    def evaluate(self, jd: Dict, cv_facts: Dict, force_effort: str = None) -> Dict:
        """
        Returns a score 1–10, plus breakdown and effort recommendation.
        """
        # ---------- Hard reject check ----------
        text = str(jd).lower()
        for pattern in self.HARD_REJECT:
            if pattern in text:
                return {
                    "score": 0,
                    "reject_reason": f"Hard reject: {pattern}",
                    "proceed": False,
                    "effort_class": "light",
                    "analysis": {},
                }

        # ---------- Flatten JD must_haves into a single searchable string ----------
        must_haves_raw = jd.get("must_haves", [])
        jd_text_parts = []
        for item in must_haves_raw:
            if isinstance(item, dict):
                # If it's a dict, combine all its values
                for key, val in item.items():
                    if isinstance(val, str):
                        jd_text_parts.append(val)
                    elif isinstance(val, list):
                        jd_text_parts.extend([str(v) for v in val])
                    else:
                        jd_text_parts.append(str(val))
            elif isinstance(item, str):
                jd_text_parts.append(item)
            else:
                jd_text_parts.append(str(item))
        jd_text = " ".join(jd_text_parts).lower()

        # ---------- Score calculation ----------
        total_possible = 0.0
        earned = 0.0
        details = []

        # --- 1. Degree match ---
        cv_degrees = [d.lower() for d in cv_facts.get("degrees", [])]
        degree_weight = self.WEIGHTS["degree"]
        total_possible += degree_weight

        for degree in ["mba", "msc", "mca", "bsc", "ba", "phd"]:
            if degree in jd_text and any(degree in d for d in cv_degrees):
                earned += degree_weight
                details.append(f"✓ Degree '{degree}' matches")
                break
        else:
            details.append("✗ No matching degree found")

        # --- 2. Experience years ---
        exp_weight = self.WEIGHTS["experience_years"]
        total_possible += exp_weight
        jd_exp = self._extract_required_years(jd_text)
        cv_exp = self._safe_int(cv_facts.get("years_experience", 0))
        if jd_exp is not None:
            if cv_exp >= jd_exp:
                earned += exp_weight
                details.append(f"✓ Experience: {cv_exp} years (requires {jd_exp})")
            else:
                ratio = cv_exp / jd_exp if jd_exp > 0 else 0
                earned += exp_weight * min(ratio, 0.5)
                details.append(f"⚠ Experience: {cv_exp}/{jd_exp} years – partial credit")
        else:
            earned += exp_weight * 0.8
            details.append(f"✓ No year requirement – {cv_exp} years is sufficient")

        # --- 3. Certification match ---
        cert_weight = self.WEIGHTS["certification"]
        total_possible += cert_weight
        cv_certs = [c.lower() for c in cv_facts.get("certifications", [])]
        jd_certs = self._extract_certifications(jd_text)
        if jd_certs:
            matched = any(any(cert in jd_cert for cert in cv_certs) for jd_cert in jd_certs)
            if matched:
                earned += cert_weight
                details.append(f"✓ Certification match")
            else:
                details.append("✗ No matching certification")
        else:
            earned += cert_weight
            details.append(f"✓ No certification required")

        # --- 4. Skill/keyword overlap ---
        skill_weight = self.WEIGHTS["skill"]
        total_possible += skill_weight
        cv_skills = set(s.lower() for s in cv_facts.get("skills", []))
        jd_keywords = self._extract_keywords(jd_text)
        if jd_keywords:
            matches = cv_skills & jd_keywords
            match_ratio = len(matches) / len(jd_keywords) if jd_keywords else 0
            earned += skill_weight * match_ratio
            details.append(f"✓ Skill overlap: {len(matches)}/{len(jd_keywords)} keywords")
        else:
            earned += skill_weight * 0.7
            details.append(f"✓ No explicit skills extracted")

        # --- 5. Language match (German/English) ---
        lang_weight = self.WEIGHTS["language"]
        total_possible += lang_weight
        cv_langs = [l.lower() for l in cv_facts.get("languages", [])]
        jd_needs_german = "german" in jd_text or "deutsch" in jd_text
        jd_needs_english = "english" in jd_text or "englisch" in jd_text

        if jd_needs_german and not any("german" in l or "deutsch" in l for l in cv_langs):
            details.append("✗ German required but not in CV")
        elif jd_needs_english and not any("english" in l or "englisch" in l for l in cv_langs):
            details.append("✗ English required but not in CV")
        else:
            earned += lang_weight
            details.append("✓ Language requirements met")

        # --- 6. Achievements (bonus) ---
        if len(cv_facts.get("key_achievements", [])) >= 2:
            earned += 0.5
            total_possible += 0.5
            details.append("✓ +0.5 for multiple quantified achievements")

        # ---------- Normalize to 1–10 scale ----------
        raw_score = (earned / total_possible) * 10 if total_possible > 0 else 5
        score = max(1, min(10, round(raw_score)))

        # ---------- Exploration override ----------
        import random
        is_exploration = False
        if score < 6 and random.random() < self.exploration_rate:
            is_exploration = True
            score = 6

        # ---------- Effort class ----------
        effort = force_effort
        if not effort:
            if score >= 8:
                effort = "light"
            elif score >= 6:
                effort = "standard"
            else:
                effort = "deep"

        return {
            "score": score,
            "reject_reason": None,
            "proceed": True,
            "effort_class": effort,
            "effort_config": self.EFFORT_CLASSES[effort],
            "analysis": {
                "is_exploration": is_exploration,
                "confidence": "high" if score >= 7 else "medium",
                "details": details,
                "leverage_points": self._extract_leverage_points(cv_facts, jd),
            },
        }

    # ---------- Helper methods ----------
    EFFORT_CLASSES = {
        "light": {"max_bullet_changes": 1, "description": "Minimal"},
        "standard": {"max_bullet_changes": 3, "description": "Balanced"},
        "deep": {"max_bullet_changes": 5, "description": "Deep"},
    }

    def _safe_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def _extract_required_years(self, text: str) -> Optional[int]:
        patterns = [
            r'(\d+)\+?\s*years?',
            r'(\d+)\s*\+\s*years?',
            r'(\d+)-year',
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                return int(match.group(1))
        return None

    def _extract_certifications(self, text: str) -> List[str]:
        # Add common certifications you care about
        certs = ["pmp", "prince2", "scrum", "safe", "itil", "aws", "azure", "cissp", "ceh"]
        found = []
        for cert in certs:
            if cert in text:
                found.append(cert)
        return found

    def _extract_keywords(self, text: str) -> set:
        # Simple keyword extraction – you can expand this
        common_skills = {
            "python", "java", "javascript", "sql", "linux", "windows",
            "agile", "scrum", "kanban", "jira", "confluence",
            "network", "security", "cloud", "aws", "azure",
            "project management", "leadership", "communication",
        }
        found = set()
        for skill in common_skills:
            if skill in text:
                found.add(skill)
        return found

    def _extract_leverage_points(self, cv_facts: Dict, jd: Dict) -> List[str]:
        points = []
        if cv_facts.get("years_experience"):
            points.append(f"{cv_facts['years_experience']} years experience")
        if cv_facts.get("degrees"):
            points.append(f"Degree: {cv_facts['degrees'][0]}")
        if cv_facts.get("key_achievements"):
            points.append(f"Proven results: {cv_facts['key_achievements'][0][:50]}...")
        return points[:3]
