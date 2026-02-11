"""
Browser Executor v3.1 - DOM Stability + Observability
"""

import time
import hashlib
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    StaleElementReferenceException, WebDriverException
)

from core.action_protocol import Action


@dataclass
class PageContext:
    url: str
    title: str
    buttons: List[str]
    inputs: List[Dict]
    file_inputs: List[str]
    textareas: List[str]
    select_boxes: List[str]
    visible_text: str
    # v3.1: Add DOM snapshot hash for observability
    dom_hash: str = ""


@dataclass
class ActionMetrics:
    """v3.1: Observability metrics per action."""
    action: str
    start_time: float
    end_time: float = 0.0
    success: bool = False
    error: Optional[str] = None
    dom_hash_before: str = ""
    dom_hash_after: str = ""
    retry_count: int = 0
    
    @property
    def latency(self) -> float:
        return self.end_time - self.start_time


class BrowserExecutor:
    def __init__(self, headless: bool = False):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.action_log: List[Dict] = []
        self.metrics: List[ActionMetrics] = []  # v3.1
    
    # v3.1: DOM stability check
    def _wait_for_dom_stable(self, timeout: int = 5) -> bool:
        """Wait for DOM to stabilize (no changes for 500ms)."""
        try:
            prev_hash = ""
            stable_count = 0
            
            for _ in range(timeout * 2):
                curr_hash = self._compute_dom_hash()
                if curr_hash == prev_hash:
                    stable_count += 1
                    if stable_count >= 2:  # 1 second stable
                        return True
                else:
                    stable_count = 0
                prev_hash = curr_hash
                time.sleep(0.5)
            
            return False
        except:
            return True  # Proceed anyway if check fails
    
    def _compute_dom_hash(self) -> str:
        """Compute hash of current DOM state."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            # Hash of element count + visible text length
            elements = len(self.driver.find_elements(By.XPATH, "//*"))
            text_len = len(body.text)
            return hashlib.md5(f"{elements}:{text_len}".encode()).hexdigest()[:8]
        except:
            return "unknown"
    
    # v3.1: Wrapped execution with stability and retry
    def _execute_with_stability(self, method, **kwargs) -> Tuple[bool, str]:
        """Execute method with DOM stability check and retry."""
        max_retries = 3
        dom_hash_before = self._compute_dom_hash()
        
        for attempt in range(max_retries):
            try:
                # Wait for DOM stable before action
                if not self._wait_for_dom_stable(timeout=3):
                    if attempt < max_retries - 1:
                        continue
                
                # Re-fetch element if needed (for click/fill)
                success = method(**kwargs)
                
                if success:
                    return True, f"Success on attempt {attempt + 1}"
                
            except StaleElementReferenceException:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return False, "Element became stale"
            except WebDriverException as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return False, str(e)
        
        return False, "Max retries exceeded"
    
    def navigate(self, url: str) -> bool:
        try:
            self.driver.get(url)
            self._wait_for_dom_stable()
            self._log_action("navigate", url, True)
            return True
        except Exception as e:
            self._log_action("navigate", url, False, str(e))
            return False
    
    # v3.1: Fuzzy label matching with confidence
    def _resolve_label(self, label: str, candidates: List[str], threshold: float = 0.6) -> Tuple[Optional[str], float]:
        """Resolve label using fuzzy matching."""
        from core.action_protocol import ActionSchema
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = ActionSchema._fuzzy_match(label, [candidate])
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate
        
        return best_match, best_score
    
    def click_button(self, text: str, threshold: float = 0.6) -> bool:
        # v3.1: Get current buttons and resolve fuzzy match
        context = self.extract_page_context()
        resolved, confidence = self._resolve_label(text, context.buttons, threshold)
        
        if not resolved:
            self._log_action("click", f"{text} (unresolved)", False, f"No match above {threshold}")
            return False
        
        # Try to click resolved label
        xpath = f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{resolved.lower()}')]"
        
        def do_click():
            element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            element.click()
            time.sleep(1)
            return True
        
        success, msg = self._execute_with_stability(do_click)
        self._log_action("click", f"{text} -> {resolved} ({confidence:.2f})", success, None if success else msg)
        return success
    
    def fill_input(self, label: str, value: str, threshold: float = 0.7) -> bool:
        # v3.1: Resolve label against available inputs
        context = self.extract_page_context()
        input_labels = [inp.get('label', '') for inp in context.inputs]
        resolved, confidence = self._resolve_label(label, input_labels, threshold)
        
        if not resolved:
            self._log_action("fill", f"{label}={value} (unresolved)", False, f"No match above {threshold}")
            return False
        
        # Try multiple strategies with resolved label
        strategies = [
            lambda: self._fill_by_label_for(resolved, value),
            lambda: self._fill_by_placeholder(resolved, value),
            lambda: self._fill_by_following(resolved, value),
        ]
        
        for strategy in strategies:
            success, msg = self._execute_with_stability(strategy)
            if success:
                self._log_action("fill", f"{label} -> {resolved}={value} ({confidence:.2f})", True)
                return True
        
        self._log_action("fill", f"{label}={value}", False, "All strategies failed")
        return False
    
    def _fill_by_label_for(self, label: str, value: str) -> bool:
        label_elem = self.driver.find_element(By.XPATH, f"//label[contains(text(), '{label}')]")
        input_id = label_elem.get_attribute('for')
        if input_id:
            input_field = self.driver.find_element(By.ID, input_id)
            input_field.clear()
            input_field.send_keys(value)
            return True
        return False
    
    def _fill_by_placeholder(self, label: str, value: str) -> bool:
        input_field = self.driver.find_element(
            By.XPATH, 
            f"//input[contains(@placeholder, '{label}') or contains(@name, '{label.lower()}')]"
        )
        input_field.clear()
        input_field.send_keys(value)
        return True
    
    def _fill_by_following(self, label: str, value: str) -> bool:
        input_field = self.driver.find_element(
            By.XPATH,
            f"//*[contains(text(), '{label}')]/following::input[1]"
        )
        input_field.clear()
        input_field.send_keys(value)
        return True
    
    def upload_file(self, label: str, path: str) -> bool:
        def do_upload():
            input_field = self.driver.find_element(
                By.XPATH,
                f"//input[@type='file'] | //label[contains(text(), '{label}')]/following::input[@type='file'][1]"
            )
            input_field.send_keys(path)
            return True
        
        success, msg = self._execute_with_stability(do_upload)
        self._log_action("upload", f"{label}={path}", success, None if success else msg)
        return success
    
    def wait(self, seconds: int = 2) -> bool:
        time.sleep(seconds)
        return True
    
    def screenshot(self, path: str) -> bool:
        try:
            self.driver.save_screenshot(path)
            return True
        except:
            return False
    
    def stop(self, reason: str = "COMPLETE") -> bool:
        self._log_action("STOP", reason, True)
        return True
    
    def report(self, message: str) -> bool:
        self._log_action("REPORT", message, True)
        return True
    
    def extract_page_context(self) -> PageContext:
        url = self.driver.current_url
        title = self.driver.title
        
        buttons = []
        try:
            for elem in self.driver.find_elements(By.XPATH, "//button | //a[@role='button']"):
                text = elem.text or elem.get_attribute('value') or ''
                if text.strip():
                    buttons.append(text.strip())
        except:
            pass
        
        inputs = []
        try:
            for elem in self.driver.find_elements(By.XPATH, "//input[@type='text'] | //input[@type='email'] | //input[@type='tel']"):
                label = elem.get_attribute('placeholder') or elem.get_attribute('aria-label') or elem.get_attribute('name') or 'unknown'
                inputs.append({
                    'label': label,
                    'type': elem.get_attribute('type') or 'text',
                    'required': elem.get_attribute('required') is not None
                })
        except:
            pass
        
        file_inputs = []
        try:
            for elem in self.driver.find_elements(By.XPATH, "//input[@type='file']"):
                file_inputs.append('File upload')
        except:
            pass
        
        visible_text = ""
        try:
            visible_text = self.driver.find_element(By.TAG_NAME, "body").text[:2000]
        except:
            pass
        
        # v3.1: Include DOM hash
        dom_hash = self._compute_dom_hash()
        
        return PageContext(
            url=url, title=title, buttons=buttons, inputs=inputs,
            file_inputs=file_inputs, textareas=[], select_boxes=[],
            visible_text=visible_text, dom_hash=dom_hash
        )
    
    def execute_action(self, action: Action) -> Tuple[bool, str]:
        """v3.1: Execute with metrics collection."""
        import time
        
        metric = ActionMetrics(
            action=action.raw,
            start_time=time.time(),
            dom_hash_before=self._compute_dom_hash()
        )
        
        method_name, kwargs = action.to_executor_call()
        
        if not method_name:
            metric.end_time = time.time()
            metric.success = False
            metric.error = f"Unknown action type: {action.type}"
            self.metrics.append(metric)
            return False, metric.error
        
        method = getattr(self, method_name, None)
        if not method:
            metric.end_time = time.time()
            metric.success = False
            metric.error = f"Method not implemented: {method_name}"
            self.metrics.append(metric)
            return False, metric.error
        
        try:
            # v3.1: Add confidence threshold for fuzzy matching
            if action.type in ['CLICK', 'FILL']:
                kwargs['threshold'] = 0.6 if action.type == 'CLICK' else 0.7
            
            success = method(**kwargs)
            metric.end_time = time.time()
            metric.success = success
            metric.dom_hash_after = self._compute_dom_hash()
            self.metrics.append(metric)
            
            if success:
                return True, f"Executed in {metric.latency:.2f}s"
            else:
                return False, "Execution returned False"
                
        except Exception as e:
            metric.end_time = time.time()
            metric.success = False
            metric.error = str(e)
            metric.dom_hash_after = self._compute_dom_hash()
            self.metrics.append(metric)
            return False, f"Exception: {str(e)}"
    
    def get_metrics_report(self) -> Dict:
        """v3.1: Generate observability report."""
        if not self.metrics:
            return {}
        
        total = len(self.metrics)
        successful = sum(1 for m in self.metrics if m.success)
        avg_latency = sum(m.latency for m in self.metrics) / total
        
        return {
            'total_actions': total,
            'successful': successful,
            'failed': total - successful,
            'success_rate': successful / total,
            'avg_latency': avg_latency,
            'actions': [
                {
                    'action': m.action,
                    'success': m.success,
                    'latency': m.latency,
                    'error': m.error,
                    'dom_changed': m.dom_hash_before != m.dom_hash_after
                }
                for m in self.metrics
            ]
        }
    
    def _log_action(self, action: str, target: str, success: bool, error: Optional[str] = None):
        self.action_log.append({
            "action": action,
            "target": target,
            "success": success,
            "error": error
        })
    
    def close(self):
        self.driver.quit()
    
    def get_log(self) -> List[Dict]:
        return self.action_log