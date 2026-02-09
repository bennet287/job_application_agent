from datetime import datetime
from pathlib import Path
from typing import Dict
import json


class DecisionRationale:
    RATIONALE_FRAMEWORK_VERSION = "v2.1"
    
    def __init__(self, assets_dir: Path):
        self.decisions_dir = assets_dir / 'decisions'
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        import os
        os.chmod(self.decisions_dir, 0o700)
    
    def create(self, application_id: int, company_slug: str,
               match_score: int, analysis: Dict, jd: Dict,
               human_override: bool = False, override_reason: str = "") -> Path:
        
        timestamp = datetime.now().isoformat()
        filename = f"{application_id:04d}__{company_slug}__rationale.txt"
        filepath = self.decisions_dir / filename
        
        lines = [
            f"DECISION RATIONALE {self.RATIONALE_FRAMEWORK_VERSION}",
            f"{'='*70}",
            f"",
            f"Application ID: APP-{application_id:04d}-{company_slug}",
            f"Timestamp: {timestamp}",
            f"Company: {jd.get('company_name', 'Unknown')}",
            f"Role: {jd.get('role_title', 'Unknown')}",
            f"",
            f"DECISION FRAMEWORK CONTEXT",
            f"-------------------------",
            f"Version: {self.RATIONALE_FRAMEWORK_VERSION}",
            f"Effort class: {analysis.get('effort_class', 'standard')}",
            f"",
            f"MATCH ASSESSMENT",
            f"----------------",
            f"Score: {match_score}/10",
            f"Confidence: {analysis.get('confidence', 'unknown')}",
            f"Recommendation: {analysis.get('recommendation', 'unknown')}",
            f"Is exploration: {analysis.get('is_exploration', False)}",
            f"",
            f"Key Gaps:",
        ]
        
        for gap in analysis.get('key_gaps', []):
            lines.append(f"  - {gap}")
        
        lines.extend([f"", f"Unlearnable Gaps:"])  # FIXED: Added closing parenthesis
        
        unlearnable = analysis.get('unlearnable_gaps', [])
        if unlearnable:
            for gap in unlearnable:
                lines.append(f"  - {gap}")
        else:
            lines.append("  None")
        
        lines.extend([
            f"",
            f"DECISION",
            f"--------",
            f"Applied: YES",
        ])
        
        if human_override:
            lines.append(f"Human Override: YES")
            lines.append(f"Override Reason: {override_reason}")
        
        lines.extend([
            f"",
            f"Applied Because:",
            f"{override_reason if human_override else self._default_rationale(analysis)}",
            f"",
            f"STRATEGIC REFLECTION",
            f"--------------------",
            f"(Complete after outcome known)",
            f"",
            f"What worked:",
            f"  [To be completed]",
            f"",
            f"What to change next time:",
            f"  [To be completed]",
            f"",
            f"LLM CONTEXT",
            f"-----------",
            f"Model: {analysis.get('llm_model', 'unknown')}",
            f"Temperature: {analysis.get('llm_temperature', 'unknown')}",
            f"Prompt version: {analysis.get('prompt_version', 'unknown')}",
            f"",
            f"INTERPRETATION GUIDE",
            f"-------------------",
            f"This rationale was written under framework {self.RATIONALE_FRAMEWORK_VERSION}.",
            f"",
            f"Version history:",
            f"- v1.x: Early EU market entry, high exploration",
            f"- v2.0: Post-interview recalibration, quality over volume",
            f"- v2.1: Added effort class decoupling, fatigue circuit breaker",
            f"",
            f"{'='*70}",
            f"IMMUTABLE RECORD - DO NOT EDIT AFTER CREATION",
            f"{'='*70}",
        ])
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        import os
        os.chmod(filepath, 0o600)
        
        return filepath
    
    def update_reflection(self, filepath: Path, what_worked: str, what_to_change: str) -> bool:
        if not filepath.exists():
            return False
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        content = content.replace(
            "What worked:\n  [To be completed]",
            f"What worked:\n  {what_worked}"
        )
        content = content.replace(
            "What to change next time:\n  [To be completed]",
            f"What to change next time:\n  {what_to_change}"
        )
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return True
    
    def _default_rationale(self, analysis: Dict) -> str:
        leverage = analysis.get('negotiation_leverage', [])
        if leverage:
            return f"Strong leverage points: {', '.join(leverage[:3])}"
        return "Score indicated viable match with manageable gaps."