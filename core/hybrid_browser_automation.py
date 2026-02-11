"""
Hybrid Browser Automation v3.1 - Structured Failure + Observability
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from core.browser_planner import ContextAwarePlanner
from core.browser_executor import BrowserExecutor, PageContext, ActionMetrics
from core.action_protocol import Action, ActionProtocol


@dataclass
class HybridAutomationResult:
    success: bool = False
    actions_taken: List[str] = field(default_factory=list)
    fields_filled: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    final_url: str = ""
    screenshot_path: Optional[str] = None
    stop_reason: str = ""  # v3.1
    metrics_report: Dict = field(default_factory=dict)  # v3.1


class HybridBrowserAutomation:
    def __init__(self, headless: bool = False):
        self.planner = ContextAwarePlanner()
        self.executor = BrowserExecutor(headless=headless)
        self.max_recovery = 3
        self.consecutive_failures = 0
    
    def run_application(self, url: str, user_data: Dict, 
                   cover_letter: str, cv_path: Path,
                   session=None, application_id: int = None) -> HybridAutomationResult:
        """
        Execute full application workflow with feedback loop.
        
        Args:
            url: Job application URL
            user_data: Dict with first_name, last_name, email, phone
            cover_letter: Cover letter text to paste
            cv_path: Path to CV file
            session: Optional SQLAlchemy session for metrics saving
            application_id: Optional application ID for metrics saving
        """
        result = HybridAutomationResult()
        # v3.1: Structured history with failure context
        history: List[Dict] = []
        
        try:
            print("  🌐 Navigating...")
            if not self.executor.navigate(url):
                result.errors.append("Navigation failed")
                return result
            
            time.sleep(2)
            context = self.executor.extract_page_context()
            
            template_actions = self.planner.generate_initial_plan(url, user_data, str(cv_path))
            
            for action in template_actions:
                # v3.1: Validate against context before execution
                is_valid, error, confidence = ActionProtocol.validate_action(action, context)
                
                if not is_valid:
                    print(f"  ⚠️  Validation failed: {error} (confidence: {confidence:.2f})")
                    history.append({
                        'action': action.raw,
                        'success': False,
                        'error': f"Validation: {error}",
                        'retry_count': 0
                    })
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_recovery:
                        break
                    continue
                
                success, msg = self._execute_with_recovery(
                    action, context, user_data, cover_letter, cv_path, history
                )
                
                if success:
                    result.actions_taken.append(action.raw)
                    self._track_progress(action, result.fields_filled)
                    self.consecutive_failures = 0
                    
                    # v3.1: Capture stop reason
                    if action.type == 'STOP':
                        result.stop_reason = action.get_stop_reason()
                        break
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_recovery:
                        print(f"  ⚠️  Max failures reached, switching to adaptive")
                        break
                
                time.sleep(1)
                context = self.executor.extract_page_context()
            
            # Adaptive mode...
            if self.consecutive_failures > 0 and self.consecutive_failures < self.max_recovery:
                print("  🧠 Adaptive planning...")
                self.planner.reset_budget()
                
                for _ in range(10):
                    action = self.planner.plan_next_action(context, user_data, history, "Fill job application")
                    
                    if not action or action.type == 'STOP':
                        result.stop_reason = action.get_stop_reason() if action else "Unknown"
                        break
                    
                    success, msg = self._execute_with_recovery(
                        action, context, user_data, cover_letter, cv_path, history
                    )
                    
                    if success:
                        result.actions_taken.append(action.raw)
                        self._track_progress(action, result.fields_filled)
                        if action.type == 'STOP':
                            result.stop_reason = action.get_stop_reason()
                            break
                    
                    time.sleep(1)
                    context = self.executor.extract_page_context()
            
            result.final_url = self.executor.driver.current_url
            result.success = len(result.actions_taken) >= 3
            
            screenshot_path = f"app_{int(time.time())}.png"
            if self.executor.screenshot(screenshot_path):
                result.screenshot_path = screenshot_path
            
            # v3.1: Collect metrics
            result.metrics_report = self.executor.get_metrics_report()
            
            print(f"  ✅ {len(result.actions_taken)} actions, stopped: {result.stop_reason}")
            
        except Exception as e:
            result.errors.append(f"Fatal: {str(e)}")
            
        finally:
            # ===================================================================
            # v3.1: Save metrics to database before closing
            # ===================================================================
            if session and application_id:
                try:
                    from database.models import save_application_metrics
                    save_application_metrics(session, application_id, {
                        'automation_mode': 'ai',
                        'stop_reason': result.stop_reason,
                        'actions_taken': result.actions_taken,
                        'errors': result.errors,
                        'metrics_report': result.metrics_report,
                        'screenshot_path': result.screenshot_path
                    })
                    print(f"  💾 Metrics saved to database (application_id: {application_id})")
                except Exception as e:
                    print(f"  ⚠️  Failed to save metrics: {e}")
            
            print("  🔍 Review browser, press Enter to close...")
            input()
            self.executor.close()
        
        return result
    
    def _execute_with_recovery(self, action: Action, context: PageContext,
                               user_data: Dict, cover_letter: str, 
                               cv_path: Path, history: List[Dict]) -> tuple:
        
        action = self._substitute_action(action, user_data, cover_letter, cv_path)
        
        is_valid, error, confidence = ActionProtocol.validate_action(action, context)
        if not is_valid:
            history.append({
                'action': action.raw,
                'success': False,
                'error': f"Pre-validation: {error}",
                'retry_count': 0
            })
            return False, error
        
        print(f"  ▶️  {action.raw[:60]}... (confidence: {confidence:.2f})")
        
        success, msg = self.executor.execute_action(action)
        
        history_entry = {
            'action': action.raw,
            'success': success,
            'error': None if success else msg,
            'retry_count': 0
        }
        
        if not success:
            # v3.1: Structured recovery with failure context
            failure_context = {
                'failed_action': action.raw,
                'error': msg,
                'element_missing': 'not found' in msg.lower() or 'unresolved' in msg.lower(),
                'retry_count': 1
            }
            
            recovery = self.planner.plan_next_action(
                context, user_data, history, 
                json.dumps(failure_context)  # Structured, not prose
            )
            
            if recovery and recovery.type != 'STOP':
                print(f"  🔄 Recovery: {recovery.raw}")
                r_success, r_msg = self.executor.execute_action(recovery)
                history_entry['retry_count'] = 1
                history_entry['recovery_success'] = r_success
                history.append(history_entry)
                return r_success, f"Recovery: {r_msg}"
        
        history.append(history_entry)
        return success, msg
    
    def _substitute_action(self, action: Action, user_data: Dict, 
                          cover_letter: str, cv_path: Path) -> Action:
        new_params = []
        for p in action.params:
            p = p.replace('{first_name}', user_data.get('first_name', ''))
            p = p.replace('{last_name}', user_data.get('last_name', ''))
            p = p.replace('{email}', user_data.get('email', ''))
            p = p.replace('{phone}', user_data.get('phone', ''))
            p = p.replace('{cover_letter}', cover_letter[:500])
            p = p.replace('{cv_path}', str(cv_path))
            new_params.append(p)
        
        new_raw = f"{action.type}|" + "|".join(new_params)
        return Action(action.type, new_params, new_raw)
    
    def _track_progress(self, action: Action, fields_filled: Dict):
        if action.type == 'FILL' and len(action.params) >= 2:
            fields_filled[action.params[0]] = True
        elif action.type == 'UPLOAD':
            fields_filled[f"upload_{action.params[0]}"] = True


def run_hybrid_automation(url, user_data, cover_letter, cv_path, auto_submit=False):
    auto = HybridBrowserAutomation(headless=False)
    return auto.run_application(url, user_data, cover_letter, Path(cv_path))