"""
Hybrid Browser Automation v3.1 - FIXED VALIDATION LOGIC
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
    stop_reason: str = ""
    metrics_report: Dict = field(default_factory=dict)
    page_type: str = "UNKNOWN"


class HybridBrowserAutomation:
    def __init__(self, headless: bool = False):
        self.planner = ContextAwarePlanner()
        self.executor = BrowserExecutor(headless=headless)
        self.max_recovery = 3
        self.consecutive_failures = 0
    
    def _extract_company_slug(self, url: str) -> str:
        """Extract company name from URL for screenshot naming."""
        domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
        return domain or "unknown"
    
    def run_application(self, url: str, user_data: Dict, 
                   cover_letter: str, cv_path: Path,
                   session=None, application_id: int = None) -> HybridAutomationResult:
        """Execute full application workflow."""
        result = HybridAutomationResult()
        history: List[Dict] = []
        
        try:
            print("  🌐 Navigating...")
            if not self.executor.navigate(url):
                result.errors.append("Navigation failed")
                return result
            
            time.sleep(2)
            context = self.executor.extract_page_context()
            result.page_type = context.page_type
            
            print(f"  📄 Detected page type: {context.page_type}")
            
            if context.page_type == "JOB_PORTAL_LISTING":
                print("\n  ⚠️  This is a job search portal, not an application form.")
                print("  👉 Please manually select a job and re-run with that URL")
                result.stop_reason = "WRONG_PAGE_TYPE"
                result.success = False
                
            elif context.page_type in ["JOB_APPLICATION_PAGE", "JOB_APPLICATION_FORM", "UNKNOWN"]:
                if context.page_type == "JOB_APPLICATION_PAGE":
                    print("\n  ✅ This is a job page with apply button.")
                elif context.page_type == "JOB_APPLICATION_FORM":
                    print("\n  ✅ This is a direct application form.")
                else:
                    print("\n  ❓ Unknown page type, attempting anyway...")
                
                self._run_application_workflow(url, user_data, cv_path, result, history, context, application_id)
            
            screenshot_path = f"app_{int(time.time())}.png"
            if self.executor.screenshot(screenshot_path):
                result.screenshot_path = screenshot_path
            
            result.metrics_report = self.executor.get_metrics_report()
            
            print(f"\n  ✅ Final: {len(result.actions_taken)} actions, stopped: {result.stop_reason}")
            
        except Exception as e:
            result.errors.append(f"Fatal: {str(e)}")
            import traceback
            traceback.print_exc()
            
        finally:
            if session and application_id:
                try:
                    from database.models import save_application_metrics
                    save_application_metrics(session, application_id, {
                        'automation_mode': 'ai',
                        'stop_reason': result.stop_reason,
                        'actions_taken': result.actions_taken,
                        'errors': result.errors,
                        'metrics_report': result.metrics_report,
                        'screenshot_path': result.screenshot_path,
                        'page_type': result.page_type
                    })
                    print(f"  💾 Metrics saved")
                except Exception as e:
                    print(f"  ⚠️  Failed to save metrics: {e}")
            
            print("\n  🔍 Review browser, press Enter to close...")
            input()
            self.executor.close()
        
        return result
    
    def _run_application_workflow(self, url: str, user_data: Dict, 
                                   cv_path: Path, result: HybridAutomationResult,
                                   history: List[Dict], context: PageContext,
                                   application_id: int = None):
        """Run the application filling workflow with UNIVERSAL field matching."""
        
        # Get base navigation plan
        template_actions = self.planner.generate_initial_plan(
            url, user_data, str(cv_path), context.page_type
        )
        
        print(f"\n  🧠 Base plan: {len(template_actions)} actions")
        
        # Track if we've clicked apply button (form will load after)
        clicked_apply = False
        
        for action in template_actions:
            # Check if this is an apply button click
            if action.type == 'CLICK' and ('bewerben' in action.raw.lower() or 'apply' in action.raw.lower()):
                clicked_apply = True
            
            print(f"\n  ▶️  {action.raw}")
            
            # FIXED: Conditional validation based on action type
            # Only validate actions that must exist on CURRENT page state
            needs_validation = action.type in ['CLICK', 'FILL', 'UPLOAD']
            is_valid = True
            error = None
            confidence = 1.0
            
            if needs_validation:
                is_valid, error, confidence = ActionProtocol.validate_action(action, context)
                
                if not is_valid:
                    # For CLICK actions, this is a real failure (button should exist)
                    if action.type == 'CLICK':
                        print(f"     ⚠️  Validation failed: {error} (confidence: {confidence:.2f})")
                        # Try anyway - maybe fuzzy matching is too strict
                        print(f"     🔄 Attempting execution despite validation failure...")
                        is_valid = True  # Override for clicks
                    
                    # For FILL/UPLOAD, this might be because form hasn't loaded yet
                    elif action.type in ['FILL', 'UPLOAD']:
                        print(f"     ⏳ Form field not yet available (confidence: {confidence:.2f})")
                        print(f"     🔄 Will attempt execution anyway - form may load dynamically")
                        is_valid = True  # Override for form fields
            
            if not is_valid:
                history.append({
                    'action': action.raw,
                    'success': False,
                    'error': f"Validation: {error}",
                    'retry_count': 0
                })
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_recovery:
                    print(f"     🛑 Max failures reached")
                    break
                continue
            
            # Execute the action
            success, msg = self._execute_with_recovery(
                action, context, user_data, cv_path, history
            )
            
            if success:
                result.actions_taken.append(action.raw)
                self._track_progress(action, result.fields_filled)
                self.consecutive_failures = 0
                print(f"     ✅ Success")
                
                # Mark that we clicked the apply button (form will load after waits)
                if action.type == 'CLICK' and ('bewerben' in action.raw.lower() or 'apply' in action.raw.lower()):
                    clicked_apply = True
                
                if action.type == 'STOP':
                    result.stop_reason = action.get_stop_reason()
                    break
            else:
                self.consecutive_failures += 1
                print(f"     ❌ Failed: {msg}")
                if self.consecutive_failures >= self.max_recovery:
                    print(f"     🛑 Max failures reached")
                    break
            
            # Refresh context after state-changing actions
            if action.type in ['NAVIGATE', 'CLICK', 'WAIT']:
                time.sleep(1)
                
                # Special handling for apply button click
                if action.type == 'CLICK' and any(x in action.raw.lower() for x in ['bewerben', 'apply']):
                    print(f"     ⏳ Apply button clicked, waiting for form...")
                    
                    # Dynamic wait for new tab (max 10 seconds)
                    start_time = time.time()
                    tab_switched = False
                    while time.time() - start_time < 10:
                        if self.executor.switch_to_new_tab():
                            print(f"     ✅ Form opened in new tab")
                            tab_switched = True
                            break
                        time.sleep(0.5)
                    
                    # Wait for form inputs to appear (dynamic)
                    input_count = self.executor.wait_for_form_inputs(timeout=15)
                    if input_count > 0:
                        print(f"     ✅ Form loaded ({input_count} inputs detected)")
                    else:
                        print(f"     ⚠️  Form inputs not detected after 15s")

                    # Refresh context after tab switch or wait
                    context = self.executor.extract_page_context()
                    print(f"     🔄 Post-apply context: {len(context.inputs)} inputs, {len(context.buttons)} buttons")
                else:
                    context = self.executor.extract_page_context()
                    print(f"     🔄 Context refreshed: {len(context.inputs)} inputs, {len(context.buttons)} buttons")

        # After base plan completes, if we clicked "apply", generate and execute dynamic fills
        if clicked_apply:
            print(f"\n  🎯 Base plan complete. Generating dynamic form fills...")
            
            # Get fresh context with form fields
            context = self.executor.extract_page_context()
            print(f"  📋 Form state: {len(context.inputs)} input fields detected")
            
            if len(context.inputs) > 0:
                # Import FieldMatcher for dynamic field matching
                from core.field_matcher import FieldMatcher
                
                cv_facts_raw = {
                    'first_name': user_data.get('first_name'),
                    'last_name': user_data.get('last_name'),
                    'email': user_data.get('email'),
                    'phone': user_data.get('phone'),
                    'address_raw': user_data.get('address_raw'),
                    'address_line1': user_data.get('address_line1'),
                    'city': user_data.get('city'),
                    'postcode': user_data.get('postcode'),
                    'country': user_data.get('country'),
                    'linkedin': user_data.get('linkedin'),
                    'github': user_data.get('github'),
                    'website': user_data.get('website'),
                    'resume_path': str(cv_path),
                    'cover_letter_path': user_data.get('cover_letter_path')
                }
                
                # Prepare cv_facts to include parsed address components
                cv_facts = FieldMatcher.prepare_cv_facts(cv_facts_raw)
                
                print(f"  📋 CV facts: {', '.join([k for k, v in cv_facts.items() if v])}")
                
                fill_actions = self.planner.generate_fill_plan(context, cv_facts)
                
                if fill_actions:
                    print(f"  ✅ Generated {len(fill_actions)} field actions")
                    
                    # Execute each fill action
                    for fill_action in fill_actions:
                        print(f"\n  ▶️  {fill_action.raw}")
                        
                        fill_success, fill_msg = self._execute_with_recovery(
                            fill_action, context, user_data, cv_path, history
                        )
                        
                        if fill_success:
                            result.actions_taken.append(fill_action.raw)
                            self._track_progress(fill_action, result.fields_filled)
                            print(f"     ✅ Success")
                        else:
                            print(f"     ⚠️  {fill_msg}")
                else:
                    print(f"  ⚠️  No field matches found - form uses non-standard labels")
            else:
                print(f"  ⚠️  No input fields detected on form")
        
        result.final_url = self.executor.driver.current_url
        result.success = len(result.actions_taken) >= 2
        
        # Take final screenshot with meaningful name
        company_slug = self._extract_company_slug(self.executor.driver.current_url)
        if application_id:
            screenshot_name = f"app_{application_id}_{company_slug}_{int(time.time())}.png"
        else:
            screenshot_name = f"app_{company_slug}_{int(time.time())}.png"
        
        screenshot_path = Path("assets") / "screenshots" / screenshot_name
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.executor.screenshot(str(screenshot_path)):
            result.screenshot_path = str(screenshot_path)
            print(f"\n  📸 Screenshot saved: {screenshot_name}")

    
    def _execute_with_recovery(self, action: Action, context: PageContext,
                               user_data: Dict, cv_path: Path, history: List[Dict]) -> tuple:
        
        action = self._substitute_action(action, user_data, cv_path)
        
        success, msg = self.executor.execute_action(action)
        
        history_entry = {
            'action': action.raw,
            'success': success,
            'error': None if success else msg,
            'retry_count': 0
        }
        
        if not success:
            # Try recovery for critical failures
            if 'not found' in msg.lower() or 'unresolved' in msg.lower():
                print(f"     🔄 Element not found, attempting recovery...")
                failure_context = {
                    'failed_action': action.raw,
                    'error': msg,
                    'element_missing': True,
                    'retry_count': 1
                }
                
                recovery = self.planner.plan_next_action(
                    context, user_data, history, 
                    json.dumps(failure_context)
                )
                
                if recovery and recovery.type != 'STOP':
                    print(f"     🔄 Recovery: {recovery.raw}")
                    r_success, r_msg = self.executor.execute_action(recovery)
                    history_entry['retry_count'] = 1
                    history_entry['recovery_success'] = r_success
                    history.append(history_entry)
                    return r_success, f"Recovery: {r_msg}"
        
        history.append(history_entry)
        return success, msg
    
    def _substitute_action(self, action: Action, user_data: Dict, 
                          cv_path: Path) -> Action:
        new_params = []
        for p in action.params:
            p = p.replace('{first_name}', user_data.get('first_name', ''))
            p = p.replace('{last_name}', user_data.get('last_name', ''))
            p = p.replace('{email}', user_data.get('email', ''))
            p = p.replace('{phone}', user_data.get('phone', ''))
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