import json
import random
from typing import Dict, Optional


class MatchScorer:
    EFFORT_CLASSES = {
        "light": {"max_bullet_changes": 1, "description": "Minimal"},
        "standard": {"max_bullet_changes": 3, "description": "Balanced"},
        "deep": {"max_bullet_changes": 5, "description": "Deep"}
    }
    
    HARD_REJECT = ["citizenship required", "security clearance", "fluent german required", "native german", "10+ years", "15+ years"]
    
    def __init__(self, llm_client, master_cv: str, exploration_rate: float = 0.15):
        self.llm = llm_client
        self.master_cv = master_cv
        self.exploration_rate = exploration_rate
    
    def evaluate(self, jd: Dict, cv_facts: Dict, force_effort: str = None) -> Dict:
        # Check hard rejects
        text = json.dumps(jd).lower()
        for pattern in self.HARD_REJECT:
            if pattern in text:
                return {"score": 0, "reject_reason": f"Hard reject: {pattern}", "proceed": False, "effort_class": "light", "analysis": {}}
        
        # Simple score based on experience
        try:
            exp = int(cv_facts.get("years_experience", 0))
        except:
            exp = 0
        
        score = 5
        if exp >= 2: 
            score += 1
        if exp >= 4: 
            score += 1
        
        # Check degrees
        degrees = [d.lower() for d in cv_facts.get("degrees", [])]
        if "mba" in degrees or "msc" in degrees:
            score += 1
        
        score = max(1, min(10, score))
        
        # Exploration override
        is_exploration = False
        if score < 6 and random.random() < self.exploration_rate:
            is_exploration = True
            score = 6
        
        effort = force_effort if force_effort else ("standard" if score >= 6 else "light")
        
        return {
            "score": score,
            "reject_reason": None,
            "proceed": True,
            "effort_class": effort,
            "effort_config": self.EFFORT_CLASSES[effort],
            "analysis": {
                "is_exploration": is_exploration,
                "leverage_points": [f"{cv_facts.get('years_experience', 'unknown')} years experience", "Relevant degrees"],
                "confidence": "medium"
            }
        }
