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
                "REPORT|Check for cookies",
            ])
        return [Action.parse(a) for a in base if Action.parse(a)]

    def generate_fill_plan(self, context: PageContext, cv_facts: Dict) -> List[Action]:
        """Generate actions for form fields."""
        actions = []
        
        prepared_facts = FieldMatcher.prepare_cv_facts(cv_facts)
        print(f"    🧠 Matching {len(context.inputs)} form fields...")
        
        for inp in context.inputs:
            # Use the EXACT label text from the form detection
            exact_label = (
                inp.get('label')
                or inp.get('placeholder')
                or inp.get('name')
                or inp.get('aria_label')
                or ''
            )
            label_lower = exact_label.lower()
            input_type = inp.get('type', 'text')
            detected_input_type = inp.get('input_type', input_type)
            is_required = inp.get('required', False)
            
            if not exact_label:
                continue
            
            # Debug print
            print(f"       Processing: '{exact_label}' (type: {input_type})")
            
            # Checkbox handling - use FieldMatcher for broader consent pattern matching
            if input_type == 'checkbox':
                # Check if this checkbox matches any consent pattern
                is_consent = False
                for pattern in FieldMatcher.FIELD_PATTERNS.get('consent', []):
                    if pattern in label_lower:
                        is_consent = True
                        break
                
                if is_consent:
                    action = Action.parse(f"CHECKBOX|{exact_label}")
                    if action:
                        actions.append(action)
                        print(f"       ✓ {exact_label} → [CHECKBOX]")
                else:
                    print(f"       ⚠ {exact_label} → optional checkbox, skip")
                continue
            
            # Date handling
            if any(term in label_lower for term in ['start date', 'earliest start', 'availability']):
                action = Action.parse(f"DATE|{exact_label}|1")
                if action:
                    actions.append(action)
                    print(f"       ✓ {exact_label} → [DATE]")
                continue
            
            # SELECT: Explicitly detected select elements OR common dropdown labels
            is_select = (
                detected_input_type == 'select' or 
                any(term in label_lower for term in ['country', 'nationality', 'gender', 'salutation', 'state', 'region'])
            )
            
            # Field matching
            match = FieldMatcher.match_field(exact_label, prepared_facts)
            if match:
                fact_key, value = match
                is_numeric_field = inp.get('is_numeric', False)
                
                if not value and not is_required:
                    print(f"       ⚠ {exact_label} → no data, skip")
                    continue

                if fact_key == 'salary_expectation' and is_numeric_field:
                    if isinstance(value, str) and value.strip().lower() == 'negotiable':
                        value = 50000
                        print(f"       ⚠ {exact_label} → numeric field, using default {value}")
                    else:
                        try:
                            value = int(float(str(value).replace(',', '').replace('.', '')))
                        except Exception:
                            value = 50000
                            print(f"       ⚠ {exact_label} → invalid numeric, using default {value}")
                
                # Determine action type
                if input_type == 'file' or 'upload' in label_lower:
                    action_str = f"UPLOAD|{exact_label}|{value}"
                elif is_select:
                    action_str = f"SELECT|{exact_label}|{value}"
                else:
                    action_str = f"FILL|{exact_label}|{value}"
                
                action = Action.parse(action_str)
                if action:
                    actions.append(action)
                    print(f"       ✓ {exact_label} → {fact_key}")
            else:
                print(f"       ⚠ {exact_label} → no match")
        
        print(f"    ✅ Generated {len(actions)} actions")
        return actions

    def _is_select_field(self, label: str, input_type: str) -> bool:
        """Check if a field is likely a select/dropdown."""
        # Common dropdown labels
        dropdown_labels = ['country', 'nationality', 'gender', 'salutation', 'title', 'state', 'region', 'province']
        return any(term in label.lower() for term in dropdown_labels) or input_type == 'select'

    def reset_budget(self):
        self.current_step = 0
