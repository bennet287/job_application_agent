"""
Context-Aware Browser Planner v3.1 - Structured Failure Context
"""

import json
from typing import List, Dict, Optional
from core.browser_executor import PageContext
from core.action_protocol import Action, ActionProtocol


class ContextAwarePlanner:
    def __init__(self):
        from utils.llm_client import LLMClient
        self.llm = LLMClient()
        self.step_budget = 15
        self.current_step = 0
    
    def plan_next_action(self, context: PageContext, user_data: Dict, 
                         history: List[Dict], goal: str) -> Optional[Action]:
        """
        v3.1: history is now List[Dict] with structured failure context.
        """
        if self.current_step >= self.step_budget:
            return Action.parse("STOP|BUDGET_EXCEEDED")
        
        self.current_step += 1
        
        prompt = self._build_prompt(context, user_data, history, goal)
        response = self.llm.generate(prompt, system_prompt=self._system_prompt())
        
        actions = ActionProtocol.parse_response(response)
        return actions[0] if actions else Action.parse("STOP|CONFUSION")
    
    def _build_prompt(self, context: PageContext, user_data: Dict, 
                      history: List[Dict], goal: str) -> str:
        
        buttons_str = '\n'.join([f'  - "{b}"' for b in context.buttons[:10]])
        inputs_str = '\n'.join([
            f'  - "{inp["label"]}" ({inp["type"]})' 
            for inp in context.inputs[:10]
        ])
        
        # v3.1: Format structured history with failure context
        history_str = self._format_history(history)
        
        # v3.1: Include DOM hash for state tracking
        dom_state = f"DOM State: {context.dom_hash}" if context.dom_hash else ""
        
        return f"""Current Page:
URL: {context.url}
Title: {context.title}
{dom_state}

Available Elements:
Buttons:
{buttons_str or '  (none)'}

Input Fields:
{inputs_str or '  (none)'}

User Data:
- Name: {user_data.get('first_name')} {user_data.get('last_name')}
- Email: {user_data.get('email')}
- Phone: {user_data.get('phone')}

Previous Actions:
{history_str or '  (none)'}

Goal: {goal}

STRICT PROTOCOL:
NAVIGATE|url
CLICK|button_text
FILL|field_label|value
UPLOAD|field_label|file_path
STOP|REASON (SUCCESS, BUDGET_EXCEEDED, NO_MATCHING_FIELDS, REQUIRES_HUMAN, CONFUSION)

Rules:
1. Use exact button/field labels from Available Elements
2. If label not found with confidence > 0.7, STOP|NO_MATCHING_FIELDS
3. One action per response
4. STOP with specific reason code

NEXT ACTION:"""
    
    def _format_history(self, history: List[Dict]) -> str:
        """v3.1: Format structured history."""
        lines = []
        for i, h in enumerate(history[-5:], 1):
            action = h.get('action', 'unknown')
            success = '✓' if h.get('success') else '✗'
            error = h.get('error', '')
            retry = f" (retry {h.get('retry_count', 0)})" if h.get('retry_count') else ""
            
            if error:
                lines.append(f"  {i}. {success} {action}{retry} - Error: {error}")
            else:
                lines.append(f"  {i}. {success} {action}{retry}")
        
        return '\n'.join(lines)
    
    def _system_prompt(self) -> str:
        return """You are a browser automation planner.
Output strict pipe-delimited actions only.
NO explanations. NO natural language.
Available STOP reasons: SUCCESS, BUDGET_EXCEEDED, NO_MATCHING_FIELDS, REQUIRES_HUMAN, CONFUSION"""
    
    def generate_initial_plan(self, url: str, user_data: Dict, cv_path: str) -> List[Action]:
        plan_template = [
            f"NAVIGATE|{url}",
            "WAIT|2",
            "CLICK|Alle akzeptieren",
            "CLICK|Jetzt bewerben",
            f"FILL|Vorname|{user_data.get('first_name', '')}",
            f"FILL|Nachname|{user_data.get('last_name', '')}",
            f"FILL|E-Mail|{user_data.get('email', '')}",
            f"FILL|Telefon|{user_data.get('phone', '')}",
            f"UPLOAD|Lebenslauf|{cv_path}",
            "STOP|SUCCESS"
        ]
        return [Action.parse(a) for a in plan_template if Action.parse(a)]
    
    def reset_budget(self):
        self.current_step = 0