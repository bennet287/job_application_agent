"""
Action Protocol v3.1 - Strict Protocol + Semantic Validation
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Action:
    """Represents a parsed action."""
    type: str
    params: List[str]
    raw: str
    
    @staticmethod
    def parse(raw: str) -> Optional['Action']:
        """Parse action from raw string. FIXED: Proper splitting."""
        if not raw or not isinstance(raw, str):
            return None
        
        raw = raw.strip()
        if not raw:
            return None
        
        # Split on | character
        parts = raw.split('|')
        if not parts:
            return None
        
        action_type = parts[0].strip().upper()
        params = [p.strip() for p in parts[1:] if p.strip()]
        
        # Validate action type
        valid_types = ['NAVIGATE', 'CLICK', 'FILL', 'UPLOAD', 'WAIT', 'STOP', 'REPORT', 'DATE', 'CHECKBOX', 'SELECT']
        if action_type not in valid_types:
            print(f"⚠️  Unknown action type: {action_type}, defaulting to REPORT")
            action_type = 'REPORT'
            params = [raw]  # Use full string as report message
        
        return Action(action_type, params, raw)
    
    def to_executor_call(self) -> Tuple[str, Dict]:
        """Convert to executor method call. FIXED: Proper param handling."""
        if self.type == 'NAVIGATE':
            return ('navigate', {'url': self.params[0] if self.params else ''})
        
        elif self.type == 'CLICK':
            return ('click_button', {'text': self.params[0] if self.params else ''})
        
        elif self.type == 'FILL':
            if len(self.params) >= 2:
                return ('fill_input', {'label': self.params[0], 'value': self.params[1]})
            elif len(self.params) == 1:
                return ('fill_input', {'label': self.params[0], 'value': ''})
            else:
                return (None, {})
        
        elif self.type == 'UPLOAD':
            if len(self.params) >= 2:
                return ('upload_file', {'label': self.params[0], 'path': self.params[1]})
            elif len(self.params) == 1:
                return ('upload_file', {'label': self.params[0], 'path': ''})
            else:
                return (None, {})
        
        elif self.type == 'WAIT':
            # FIXED: Handle int conversion safely
            seconds = 2  # default
            if self.params:
                try:
                    seconds = int(self.params[0])
                except (ValueError, TypeError):
                    print(f"⚠️  WAIT param '{self.params[0]}' is not a number, using default 2s")
                    seconds = 2
            return ('do_wait', {'seconds': seconds})
        
        elif self.type == 'DATE':
            if len(self.params) >= 2:
                return ('handle_date_field', {'label': self.params[0], 'days_from_now': int(self.params[1])})
            elif len(self.params) == 1:
                return ('handle_date_field', {'label': self.params[0], 'days_from_now': 1})
            else:
                return (None, {})
        
        elif self.type == 'CHECKBOX':
            if len(self.params) >= 1:
                return ('click_checkbox', {'label': self.params[0], 'threshold': 0.6})
            else:
                return (None, {})
        
        elif self.type == 'SELECT':
            if len(self.params) >= 2:
                return ('select_dropdown', {'label': self.params[0], 'value': self.params[1], 'threshold': 0.7})
            else:
                return (None, {})
        
        elif self.type == 'STOP':
            return ('stop', {'reason': self.params[0] if self.params else 'UNKNOWN'})
        
        elif self.type == 'REPORT':
            return ('report', {'message': self.params[0] if self.params else ''})
        
        else:
            return (None, {})
    
    def get_stop_reason(self) -> str:
        """Get stop reason for STOP actions."""
        if self.type == 'STOP' and self.params:
            return self.params[0]
        return 'UNKNOWN'


class ActionProtocol:
    """Protocol for action validation and parsing."""
    
    @staticmethod
    def parse_response(response: str) -> List[Action]:
        """Parse LLM response into actions."""
        actions = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Remove any markdown formatting
            line = line.replace('```', '').strip()
            action = Action.parse(line)
            if action:
                actions.append(action)
        return actions
    
    @staticmethod
    def validate_action(action: Action, context) -> Tuple[bool, str, float]:
        """Validate action against page context."""
        from core.browser_executor import PageContext
        
        if not isinstance(context, PageContext):
            return True, "No context available", 1.0
        
        if action.type == 'NAVIGATE':
            return True, "Navigate always valid", 1.0
        
        elif action.type == 'WAIT':
            return True, "Wait always valid", 1.0
        
        elif action.type == 'STOP':
            return True, "Stop always valid", 1.0
        
        elif action.type == 'REPORT':
            return True, "Report always valid", 1.0
        
        elif action.type == 'CLICK':
            if not action.params:
                return False, "No button specified", 0.0
            
            target = action.params[0]
            # Fuzzy match against available buttons
            best_score = ActionSchema._fuzzy_match(target, context.buttons)
            
            if best_score >= 0.6:
                return True, f"Button found (confidence: {best_score:.2f})", best_score
            else:
                return False, f"Button '{target}' not found (best match: {best_score:.2f})", best_score
        
        elif action.type == 'FILL':
            if len(action.params) < 1:
                return False, "No field specified", 0.0
            
            target = action.params[0]
            input_labels = [inp.get('label', '') for inp in context.inputs]
            best_score = ActionSchema._fuzzy_match(target, input_labels)
            
            if best_score >= 0.7:
                return True, f"Field found (confidence: {best_score:.2f})", best_score
            else:
                return False, f"Field '{target}' not found (best match: {best_score:.2f})", best_score
        
        elif action.type == 'UPLOAD':
            if len(action.params) < 1:
                return False, "No upload field specified", 0.0
            
            # Check if file inputs exist
            if context.file_inputs:
                return True, f"File input available", 1.0
            else:
                return False, "No file input found", 0.0
        
        return True, "Unknown action type, allowing", 0.5


class ActionSchema:
    """Schema definitions for actions."""
    
    @staticmethod
    def _fuzzy_match(target: str, candidates: List[str]) -> float:
        """Simple fuzzy matching. Returns score 0.0-1.0."""
        if not target or not candidates:
            return 0.0
        
        target_lower = target.lower()
        best_score = 0.0
        
        for candidate in candidates:
            if not candidate:
                continue
            
            candidate_lower = candidate.lower()
            
            # Exact match
            if target_lower == candidate_lower:
                return 1.0
            
            # Contains match
            if target_lower in candidate_lower or candidate_lower in target_lower:
                score = 0.8
                if score > best_score:
                    best_score = score
                continue
            
            # Word overlap
            target_words = set(target_lower.split())
            candidate_words = set(candidate_lower.split())
            if target_words and candidate_words:
                overlap = len(target_words & candidate_words)
                total = len(target_words | candidate_words)
                if total > 0:
                    score = overlap / total
                    if score > best_score:
                        best_score = score
        
        return best_score