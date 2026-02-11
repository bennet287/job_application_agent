"""
Strict Action Protocol v3.1 - Semantic Validation
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re


@dataclass
class Action:
    type: str
    params: List[str]
    raw: str
    
    # v3.1: Add reason codes for STOP
    STOP_REASONS = {
        'SUCCESS': 'Task completed successfully',
        'BUDGET_EXCEEDED': 'Step budget reached',
        'NO_MATCHING_FIELDS': 'Required fields not found',
        'REQUIRES_HUMAN': 'Human intervention needed',
        'CONFUSION': 'Planner uncertain',
        'ERROR': 'Execution error'
    }
    
    @classmethod
    def parse(cls, line: str) -> Optional["Action"]:
        line = line.strip()
        if not line or line.startswith('#'):
            return None
        
        parts = line.split('|')
        if len(parts) < 1:
            return None
        
        action_type = parts[0].upper()
        params = [p.strip() for p in parts[1:]]
        
        valid_types = {'NAVIGATE', 'CLICK', 'FILL', 'UPLOAD', 'SELECT', 
                      'WAIT', 'SCREENSHOT', 'STOP', 'REPORT'}
        
        if action_type not in valid_types:
            return None
        
        # v3.1: Normalize STOP reason codes
        if action_type == 'STOP' and params:
            reason = params[0].upper()
            if reason in cls.STOP_REASONS:
                params[0] = reason
        
        return cls(type=action_type, params=params, raw=line)
    
    def to_executor_call(self) -> tuple:
        method_map = {
            'NAVIGATE': ('navigate', {'url': self.params[0] if self.params else ''}),
            'CLICK': ('click_button', {'text': self.params[0] if self.params else ''}),
            'FILL': ('fill_input', {
                'label': self.params[0] if len(self.params) > 0 else '',
                'value': self.params[1] if len(self.params) > 1 else ''
            }),
            'UPLOAD': ('upload_file', {
                'label': self.params[0] if len(self.params) > 0 else '',
                'path': self.params[1] if len(self.params) > 1 else ''
            }),
            'SELECT': ('select_option', {
                'label': self.params[0] if len(self.params) > 0 else '',
                'option': self.params[1] if len(self.params) > 1 else ''
            }),
            'WAIT': ('wait', {'seconds': int(self.params[0]) if self.params else 2}),
            'SCREENSHOT': ('screenshot', {'path': self.params[0] if self.params else 'screenshot.png'}),
            'STOP': ('stop', {'reason': self.params[0] if self.params else 'COMPLETE'}),
            'REPORT': ('report', {'message': self.params[0] if self.params else ''}),
        }
        return method_map.get(self.type, (None, {}))
    
    # v3.1: Get STOP reason description
    def get_stop_reason(self) -> str:
        if self.type == 'STOP' and self.params:
            return self.STOP_REASONS.get(self.params[0], self.params[0])
        return 'Unknown'


class ActionSchema:
    """v3.1: Semantic validation schema for actions."""
    
    SCHEMAS = {
        'FILL': {
            'min_params': 2,
            'validate_label_exists': True,
            'validate_value_non_empty': True,
            'confidence_threshold': 0.7
        },
        'UPLOAD': {
            'min_params': 2,
            'validate_path_exists': True,
            'validate_is_file': True
        },
        'CLICK': {
            'min_params': 1,
            'validate_label_exists': True,
            'confidence_threshold': 0.6
        },
        'SELECT': {
            'min_params': 2,
            'validate_label_exists': True
        }
    }
    
    @classmethod
    def validate(cls, action: Action, context: Any = None) -> tuple:
        """
        Validate action against schema and context.
        Returns: (is_valid, error_message, confidence)
        """
        schema = cls.SCHEMAS.get(action.type, {})
        
        # Check param count
        if len(action.params) < schema.get('min_params', 0):
            return False, f"{action.type} requires {schema['min_params']} params", 0.0
        
        # v3.1: Context-aware validation
        if context and hasattr(context, 'buttons'):
            return cls._validate_against_context(action, context, schema)
        
        return True, "", 1.0
    
    @classmethod
    def _validate_against_context(cls, action: Action, context: Any, schema: Dict) -> tuple:
        """Validate action against PageContext."""
        threshold = schema.get('confidence_threshold', 0.0)
        
        if action.type in ['CLICK', 'FILL', 'SELECT', 'UPLOAD']:
            label = action.params[0]
            
            # v3.1: Fuzzy match against available elements
            if action.type == 'CLICK':
                confidence = cls._fuzzy_match(label, context.buttons)
            else:
                input_labels = [inp.get('label', '') for inp in context.inputs]
                file_labels = context.file_inputs
                confidence = cls._fuzzy_match(label, input_labels + file_labels)
            
            if confidence < threshold:
                return False, f"Label '{label}' confidence {confidence:.2f} below threshold {threshold}", confidence
            
            return True, "", confidence
        
        return True, "", 1.0
    
    @staticmethod
    def _fuzzy_match(query: str, candidates: List[str]) -> float:
        """
        v3.1: Normalized fuzzy matching.
        Returns confidence score 0.0-1.0
        """
        if not query or not candidates:
            return 0.0
        
        query_norm = ActionSchema._normalize(query)
        
        best_score = 0.0
        for candidate in candidates:
            cand_norm = ActionSchema._normalize(candidate)
            
            # Exact match
            if query_norm == cand_norm:
                return 1.0
            
            # Substring match
            if query_norm in cand_norm or cand_norm in query_norm:
                score = len(query_norm) / max(len(query_norm), len(cand_norm))
                best_score = max(best_score, score)
            
            # Word overlap
            query_words = set(query_norm.split())
            cand_words = set(cand_norm.split())
            if query_words and cand_words:
                overlap = len(query_words & cand_words) / len(query_words | cand_words)
                best_score = max(best_score, overlap)
        
        return best_score
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for matching."""
        import unicodedata
        text = text.lower().strip()
        text = unicodedata.normalize('NFKD', text)
        text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
        text = re.sub(r'\s+', ' ', text)     # Normalize whitespace
        text = re.sub(r'\s*\*\s*', '', text) # Remove required markers
        text = re.sub(r'\s*\(required\)\s*', '', text)
        return text


class ActionProtocol:
    @staticmethod
    def parse_response(text: str) -> List[Action]:
        actions = []
        for line in text.split('\n'):
            cleaned = re.sub(r'^\s*\d+[\.\)]\s*', '', line.strip())
            action = Action.parse(cleaned)
            if action:
                actions.append(action)
        return actions
    
    @staticmethod
    def validate_action(action: Action, context: Any = None) -> tuple:
        """v3.1: Use semantic schema validation."""
        return ActionSchema.validate(action, context)