"""
Context-Aware Browser Planner v4.0 – Universal, no hardcoded fields.
"""

from typing import List, Dict, Optional
from core.action_protocol import Action
from core.browser_executor import PageContext
from core.field_matcher import FieldMatcher


class ContextAwarePlanner:
    def __init__(self):
        self.step_budget = 15
        self.current_step = 0
    
    def generate_initial_plan(self, url: str, user_data: Dict, cv_path: str, page_type: str = "UNKNOWN") -> List[Action]:
        """Always the same start: navigate, cookies, click apply."""
        base = [
            f"NAVIGATE|{url}",
            "WAIT|3",
            "REPORT|Check for cookies",
        ]
        if page_type == "JOB_PORTAL_LISTING":
            base.append("STOP|WRONG_PAGE_TYPE")
        else:
            base.extend([
                "WAIT|2",
                "CLICK|Jetzt bewerben",
                "WAIT|5",
                "REPORT|Switch to form tab",
            ])
        return [Action.parse(a) for a in base if Action.parse(a)]

    def generate_fill_plan(self, context: PageContext, cv_facts: Dict) -> List[Action]:
        """Dynamically create FILL/UPLOAD actions for every matching field."""
        actions = []
        
        # Prepare CV facts with all possible field expansions
        prepared_facts = FieldMatcher.prepare_cv_facts(cv_facts)
        
        print(f"    🧠 Matching {len(context.inputs)} form fields to CV facts...")
        
        for inp in context.inputs:
            label = inp.get('label', '')
            if not label:
                continue
            
            # Special case: date fields
            if any(term in label.lower() for term in ['start date', 'earliest start', 'availability', 'available from']):
                # Use a special DATE action
                action = Action.parse(f"DATE|{label}|1")  # 1 = tomorrow
                if action:
                    actions.append(action)
                    print(f"       ✓ {label} → [DATE: tomorrow]")
                continue
            
            match = FieldMatcher.match_field(label, prepared_facts)
            if match:
                fact_key, value = match
                if inp.get('type') == 'file' or 'upload' in label.lower():
                    action = Action.parse(f"UPLOAD|{label}|{value}")
                else:
                    action = Action.parse(f"FILL|{label}|{value}")
                
                if action:
                    actions.append(action)
                    print(f"       ✓ {label} → {fact_key}")
            else:
                print(f"       ⚠ {label} → no match")
        
        if not actions:
            print("    ⚠️  No fields matched - form may use non-standard labels")
        
        return actions

    def reset_budget(self):
        self.current_step = 0
