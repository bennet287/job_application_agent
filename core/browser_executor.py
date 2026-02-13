"""
Browser Executor v3.1 - DOM Stability + Observability + Smart Page Detection
"""

from multiprocessing import context
import time
import hashlib
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException
)
from sqlalchemy import text
from urllib.parse import urlparse
from datetime import datetime, timedelta

from core.action_protocol import Action


# ATS Platform Fingerprints - known application systems
ATS_FINGERPRINTS = {
    'csod.com': {
        'name': 'Cornerstone OnDemand',
        'form_wait_seconds': 5,
        'uses_iframes': False,
        'cookie_btn': 'Akzeptieren',
        'input_strategy': 'label-first'
    },
    'greenhouse.io': {
        'name': 'Greenhouse',
        'form_wait_seconds': 3,
        'uses_iframes': False,
        'cookie_btn': 'Accept Cookies',
        'input_strategy': 'label-first'
    },
    'personio.de': {
        'name': 'Personio',
        'form_wait_seconds': 4,
        'uses_iframes': True,
        'cookie_btn': 'Alle akzeptieren',
        'input_strategy': 'iframe-first'
    },
    'workday.com': {
        'name': 'Workday',
        'form_wait_seconds': 6,
        'uses_iframes': True,
        'cookie_btn': 'OK',
        'input_strategy': 'iframe-first'
    },
    'lever.co': {
        'name': 'Lever',
        'form_wait_seconds': 3,
        'uses_iframes': False,
        'cookie_btn': 'Accept',
        'input_strategy': 'label-first'
    }
}


@dataclass
class PageContext:
    url: str
    title: str
    buttons: List[str]
    inputs: List[Dict]
    file_inputs: List[str]
    textareas: List[Dict]
    select_boxes: List[str]
    visible_text: str
    dom_hash: str = ""
    page_type: str = "UNKNOWN"


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
        options.add_argument('--disable-notifications')

        self.driver = webdriver.Chrome(options=options)
        self.driver_wait = WebDriverWait(self.driver, 10)
        self.action_log: List[Dict] = []
        self.metrics: List[ActionMetrics] = []
        self.ats_config: Optional[Dict] = None  # Detected ATS platform config

    def _wait_for_dom_stable(self, timeout: int = 5) -> bool:
        """Wait for DOM to stabilize (no changes for 500ms)."""
        try:
            prev_hash = ""
            stable_count = 0

            for _ in range(timeout * 2):
                curr_hash = self._compute_dom_hash()
                if curr_hash == prev_hash:
                    stable_count += 1
                    if stable_count >= 2:
                        return True
                else:
                    stable_count = 0
                prev_hash = curr_hash
                time.sleep(0.5)

            return False
        except:
            return True

    def _compute_dom_hash(self) -> str:
        """Compute hash of current DOM state."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            elements = len(self.driver.find_elements(By.XPATH, "//*"))
            text_len = len(body.text)
            return hashlib.md5(f"{elements}:{text_len}".encode()).hexdigest()[:8]
        except:
            return "unknown"

    def _execute_with_stability(self, method, **kwargs) -> Tuple[bool, str]:
        """Execute method with DOM stability check and retry."""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if not self._wait_for_dom_stable(timeout=3):
                    if attempt < max_retries - 1:
                        continue

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
            
            # Detect ATS platform
            self._detect_ats_platform(url)
            if self.ats_config:
                print(f"    🏢 Detected ATS: {self.ats_config['name']}")
            
            self._log_action("navigate", url, True)
            return True
        except Exception as e:
            self._log_action("navigate", url, False, str(e))
            return False
    
    def _detect_ats_platform(self, url: str):
        """Detect known ATS platform from URL."""
        domain = urlparse(url).netloc
        for ats_domain, config in ATS_FINGERPRINTS.items():
            if ats_domain in domain:
                self.ats_config = config
                return
        self.ats_config = None

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

    def click_checkbox(self, label: str, threshold: float = 0.6) -> bool:
        """Click a checkbox - ultra robust version with fuzzy matching."""
        print(f"    🔲 CHECKBOX: '{label}'")
        
        clean_label = label.replace('*', '').strip().lower()
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Refresh context
                self._wait_for_dom_stable(timeout=2)
                
                # Get all checkboxes on the page
                checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
                print(f"      Found {len(checkboxes)} checkboxes")
                
                for i, checkbox in enumerate(checkboxes):
                    try:
                        # Find associated label
                        checkbox_id = checkbox.get_attribute('id')
                        checkbox_name = checkbox.get_attribute('name')
                        
                        label_elem = None
                        label_text = ""
                        
                        # Try to find label by 'for' attribute
                        if checkbox_id:
                            try:
                                label_elem = self.driver.find_element(By.XPATH, f"//label[@for='{checkbox_id}']")
                                label_text = (label_elem.text or '').strip()
                            except:
                                pass
                        
                        # If no label found, try parent element
                        if not label_elem:
                            try:
                                parent = checkbox.find_element(By.XPATH, "..")
                                label_text = (parent.text or '').strip()
                            except:
                                pass
                        
                        # Check if this is the checkbox we want
                        label_lower = label_text.lower()
                        
                        # Match criteria
                        is_match = (
                            clean_label in label_lower or
                            label_lower in clean_label or
                            ('agree' in clean_label and 'agree' in label_lower) or
                            ('consent' in clean_label and ('consent' in label_lower or 'data' in label_lower)) or
                            ('i agree' in label_lower and 'agree' in clean_label)
                        )
                        
                        if is_match:
                            print(f"      ✓ Checkbox {i+1} matches: '{label_text[:50]}'")
                            
                            # Scroll and click
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                            time.sleep(0.3)
                            
                            # Check if already checked
                            if checkbox.is_selected():
                                print(f"      ✅ Already checked")
                                return True
                            
                            # Click using JavaScript
                            self.driver.execute_script("arguments[0].click();", checkbox)
                            time.sleep(0.5)
                            
                            # Verify
                            if checkbox.is_selected():
                                print(f"      ✅ Checked successfully")
                                return True
                            else:
                                # Try clicking the label instead
                                if label_elem:
                                    self.driver.execute_script("arguments[0].click();", label_elem)
                                    time.sleep(0.5)
                                    if checkbox.is_selected():
                                        print(f"      ✅ Checked via label")
                                        return True
                            
                    except Exception as e:
                        continue
                
                print(f"      ⚠️  No matching checkbox found")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    
            except Exception as e:
                print(f"      ⚠️  Error: {str(e)[:60]}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return False

    def click_button(self, text: str, threshold: float = 0.6) -> bool:
        context = self.extract_page_context()
        print(f"    🔍 Looking for: '{text}'")
        print(f"    📋 Available: {context.buttons[:10]}")

        resolved, confidence = self._resolve_label(text, context.buttons, threshold)
        print(f"    🎯 Resolved: '{resolved}' (confidence: {confidence:.2f})")

        if confidence < threshold:
            print(f"    ❌ Below threshold {threshold}")
            return False

        strategies = [
            f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), '{resolved.lower()}')]",
            f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), '{resolved.lower()}')]",
            f"//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), '{resolved.lower()}')]",
            f"//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), '{resolved.lower()}')]",
            f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', 'abcdefghijklmnopqrstuvwxyzäöü'), '{resolved.lower()}')]",
        ]

        def do_click():
            for xpath in strategies:
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            elem.click()
                            time.sleep(1)
                            return True
                except:
                    continue
            return False

        success, msg = self._execute_with_stability(do_click)
        self._log_action("click", f"{text} -> {resolved} ({confidence:.2f})", success, None if success else msg)
        return success

    def accept_cookies(self) -> bool:
        """Try multiple cookie consent patterns - improved for German sites."""
        patterns = [
            "Alle akzeptieren",
            "Alle Cookies akzeptieren",
            "Zustimmen",
            "Akzeptieren",
            "Einverstanden",
            "Verstanden",
            "OK",
            "Ja",
            "Accept all cookies",
            "Accept all",
            "I agree",
            "Agree",
            "Allow all",
            "Continue",
        ]

        for pattern in patterns:
            if self.click_button(pattern, threshold=0.8):
                print(f"    ✅ Accepted cookies: '{pattern}'")
                return True

        print("    ⚠️  Could not find cookie button automatically")
        return False

    def switch_to_new_tab(self) -> bool:
        """Switch to the most recently opened tab."""
        try:
            handles = self.driver.window_handles

            if len(handles) > 1:
                self.driver.switch_to.window(handles[-1])
                print(f"    🔄 Switched to new tab: {self.driver.current_url[:60]}...")
                self._wait_for_dom_stable(timeout=3)
                return True
            return False
        except Exception as e:
            print(f"    ⚠️  Failed to switch tab: {e}")
            return False

    def close_current_tab_and_switch_back(self) -> bool:
        """Close current tab and switch back to first tab."""
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(handles[0])
                return True
            return False
        except:
            return False

    def switch_to_form_iframe(self) -> bool:
        """Try to find and switch to form iframe."""
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            for i, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(iframe)
                    inputs = self.driver.find_elements(By.TAG_NAME, 'input')
                    if len(inputs) > 2:
                        print(f"    🔄 Switched to iframe {i + 1} with {len(inputs)} inputs")
                        return True
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
                    continue
            return False
        except:
            return False

    def _detect_inputs(self) -> List[Dict]:
        """Detect all input fields with improved label finding for ATS systems - FIXED to detect SELECT elements."""
        inputs = []

        try:
            labels = self.driver.find_elements(By.TAG_NAME, 'label')
            print(f"    DEBUG: Found {len(labels)} <label> elements")

            for label in labels:
                try:
                    label_text = (label.text or '').strip()
                    if not label_text:
                        continue

                    input_elem = None
                    input_type = 'text'

                    # Check for SELECT elements first
                    try:
                        select_elem = label.find_element(By.XPATH, ".//select")
                        if select_elem:
                            inputs.append({
                                'label': label_text,
                                'type': 'select',
                                'input_type': 'select',
                                'required': '*' in label_text or select_elem.get_attribute('required') is not None
                            })
                            print(f"       OK: label '{label_text[:30]}' -> SELECT element")
                            continue
                    except:
                        pass

                    # Check for SELECT via @for attribute
                    try:
                        label_for = label.get_attribute('for')
                        if label_for:
                            select_elem = self.driver.find_element(By.XPATH, f"//select[@id='{label_for}']")
                            if select_elem:
                                inputs.append({
                                    'label': label_text,
                                    'type': 'select',
                                    'input_type': 'select',
                                    'required': '*' in label_text or select_elem.get_attribute('required') is not None
                                })
                                print(f"       OK: label '{label_text[:30]}' -> SELECT by @for")
                                continue
                    except:
                        pass

                    # Check for INPUT elements
                    try:
                        input_elem = label.find_element(By.XPATH, ".//input")
                    except:
                        pass

                    if not input_elem:
                        try:
                            input_elem = label.find_element(By.XPATH, "./following-sibling::input[1]")
                        except:
                            pass

                    if not input_elem:
                        try:
                            input_elem = label.find_element(By.XPATH, "./following-sibling::*[1]//input")
                        except:
                            pass

                    if input_elem:
                        input_type = input_elem.get_attribute('type') or 'text'
                        inputs.append({
                            'label': label_text,
                            'type': input_type,
                            'input_type': input_type,
                            'required': '*' in label_text or input_elem.get_attribute('required') is not None
                        })
                        print(f"       OK: label '{label_text[:30]}' -> input type={input_type}")
                except:
                    continue

            if len(inputs) < 3:
                print("    DEBUG: Few inputs from labels, trying placeholders...")
                xpath = "//input[@placeholder]"
                for elem in self.driver.find_elements(By.XPATH, xpath):
                    placeholder = elem.get_attribute('placeholder')
                    if placeholder:
                        inputs.append({
                            'label': placeholder,
                            'type': elem.get_attribute('type') or 'text',
                            'required': elem.get_attribute('required') is not None
                        })

            if len(inputs) < 3:
                print("    DEBUG: Trying to find inputs by nearby text...")
                all_inputs = self.driver.find_elements(
                    By.XPATH,
                    "//input[@type='text' or @type='email' or not(@type)]"
                )
                for inp in all_inputs:
                    try:
                        prev_text = inp.find_element(By.XPATH, "./preceding-sibling::*[1]").text
                        if prev_text and len(prev_text) < 50:
                            inputs.append({
                                'label': prev_text,
                                'type': inp.get_attribute('type') or 'text',
                                'required': False
                            })
                    except:
                        pass

            # ----- DETECT DATE PICKER BUTTONS -----
            try:
                date_xpath = (
                    "//*[self::button or self::div or self::span]["
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', "
                    "'abcdefghijklmnopqrstuvwxyzäöü'), 'earliest start') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', "
                    "'abcdefghijklmnopqrstuvwxyzäöü'), 'start date')]"
                )
                date_elems = self.driver.find_elements(By.XPATH, date_xpath)
                for elem in date_elems:
                    text = (elem.text or '').strip()
                    if text and len(text) < 50:
                        inputs.append({
                            'label': text,
                            'type': 'date_button',
                            'required': True
                        })
                        print(f"       ✓ Date picker: '{text[:30]}'")
            except Exception as e:
                print(f"    ⚠️  Date picker detection error: {e}")
            # --------------------------------------

            # ----- DETECT SALARY FIELDS -----
            try:
                salary_xpath = (
                    "//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', "
                    "'abcdefghijklmnopqrstuvwxyzäöü'), 'salary') or "
                    "contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ', "
                    "'abcdefghijklmnopqrstuvwxyzäöü'), 'salary')]"
                )
                salary_inputs = self.driver.find_elements(By.XPATH, salary_xpath)
                for inp in salary_inputs:
                    label = inp.get_attribute('placeholder') or inp.get_attribute('name') or 'Salary'
                    inputs.append({
                        'label': label,
                        'type': inp.get_attribute('type') or 'text',
                        'required': False
                    })
                    print(f"       ✓ Salary field: '{label}'")
            except Exception as e:
                print(f"    ⚠️  Salary detection error: {e}")
            # ---------------------------------

            print(f"    DEBUG: Total inputs detected: {len(inputs)}")

        except Exception as e:
            print(f"    WARNING: Error detecting inputs: {e}")

        return inputs

    def _detect_textareas(self) -> List[Dict]:
        textareas = []
        try:
            for elem in self.driver.find_elements(By.TAG_NAME, "textarea"):
                label = elem.get_attribute('aria-label') or elem.get_attribute('placeholder')

                if not label:
                    try:
                        label_elem = elem.find_element(By.XPATH, "./preceding-sibling::label")
                        label = label_elem.text
                    except:
                        pass

                if not label:
                    label = elem.get_attribute('name') or 'textarea'

                textareas.append({
                    'label': label.replace('\n', ' ').strip(),
                    'type': 'textarea',
                    'required': elem.get_attribute('required') is not None
                })
        except:
            return textareas

        return textareas

    def fill_input(self, label: str, value: str, threshold: float = 0.7) -> bool:
        """Fill input by finding label text and associated input field."""
        print(f"    🔍 FILL: Looking for label '{label}'")

        search_label = label.replace('*', '').strip()
        label_elem = None

        try:
            label_elem = self.driver.find_element(
                By.XPATH,
                f"//label[contains(normalize-space(text()), '{search_label}')]"
            )
            print("    ✓ Found label with contains()")
        except Exception as e:
            print(f"    ⚠️  Contains search failed: {e}")

        if not label_elem:
            try:
                label_elem = self.driver.find_element(By.XPATH, f"//label[text()='{label}']")
                print("    ✓ Found exact label match")
            except:
                pass

        if not label_elem:
            try:
                all_labels = self.driver.find_elements(By.TAG_NAME, 'label')
                for lbl in all_labels:
                    lbl_text = (lbl.text or '').strip()
                    if search_label.lower() in lbl_text.lower():
                        label_elem = lbl
                        print(f"    ✓ Found label by iteration: '{lbl_text}'")
                        break
            except:
                pass

        if not label_elem:
            print("    ❌ Label not found")
            self._log_action("fill", f"{label}={value} (unresolved)", False, "Label not found")
            return False

        actual_label_text = (label_elem.text or '').strip()
        print(f"    📋 Actual label text: '{actual_label_text}'")

        input_field = None

        try:
            input_field = label_elem.find_element(By.XPATH, ".//input")
            print("    ✓ Found input inside label")
        except:
            pass

        if not input_field:
            try:
                input_field = label_elem.find_element(By.XPATH, "./following-sibling::input[1]")
                print("    ✓ Found input as sibling")
            except:
                pass

        if not input_field:
            try:
                input_field = label_elem.find_element(By.XPATH, "./parent::*/following-sibling::*[1]//input")
                print("    ✓ Found input in parent's sibling")
            except:
                pass

        if not input_field:
            try:
                input_field = self.driver.find_element(
                    By.XPATH,
                    f"//label[contains(normalize-space(text()), '{search_label}')]/following::input[1]"
                )
                print("    ✓ Found input by document order")
            except:
                pass

        if not input_field:
            print("    ❌ No input found for label")
            self._log_action("fill", f"{label}={value}", False, "No input for label")
            return False

        # --- ROBUST FILL: Use JavaScript to bypass overlays ---
        try:
            # Scroll into view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                input_field
            )
            time.sleep(0.3)
            
            # Force focus and set value via JavaScript (bypasses click interception)
            self.driver.execute_script(
                "arguments[0].focus(); arguments[0].value = arguments[1];",
                input_field, value
            )
            
            # Trigger change event (some sites listen for it)
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                input_field
            )
            
            print(f"    ✅ Filled '{label}' with '{value}' (JS)")
            self._log_action("fill", f"{label}={value}", True)
            return True
            
        except Exception as e:
            print(f"    ❌ Error filling: {e}")
            self._log_action("fill", f"{label}={value}", False, f"Error: {e}")
            return False

    def select_dropdown(self, label: str, value: str, threshold: float = 0.7) -> bool:
        """Select value from a dropdown/select element - WORKING VERSION for csod.com."""
        print(f"    🔽 DROPDOWN: '{label}' = '{value}'")
        
        try:
            # Find the label
            label_elem = None
            label_variations = [
                label,
                label.replace('*', ''),
                label.replace('*', '').strip(),
            ]
            
            for lv in label_variations:
                try:
                    label_elem = self.driver.find_element(
                        By.XPATH, 
                        f"//label[contains(normalize-space(text()), '{lv}')]"
                    )
                    break
                except:
                    try:
                        label_elem = self.driver.find_element(
                            By.XPATH,
                            f"//label[contains(text(), '{lv}')]"
                        )
                        break
                    except:
                        continue
            
            if not label_elem:
                print(f"      ❌ Label not found")
                return False
            
            print(f"      ✓ Found label")
            
            # Find the select element - try multiple strategies
            select_elem = None
            
            # Strategy 1: Parent container
            try:
                parent = label_elem.find_element(By.XPATH, "..")
                select_elem = parent.find_element(By.TAG_NAME, "select")
                print(f"      ✓ Found select in parent")
            except:
                pass
            
            # Strategy 2: Following sibling
            if not select_elem:
                try:
                    select_elem = label_elem.find_element(By.XPATH, "./following-sibling::select[1]")
                    print(f"      ✓ Found select as following sibling")
                except:
                    pass
            
            # Strategy 3: Look in grandparent (for grouped forms)
            if not select_elem:
                try:
                    grandparent = label_elem.find_element(By.XPATH, "../..")
                    select_elem = grandparent.find_element(By.TAG_NAME, "select")
                    print(f"      ✓ Found select in grandparent")
                except:
                    pass
            
            # Strategy 4: Any select after the label in document
            if not select_elem:
                try:
                    select_elem = self.driver.find_element(
                        By.XPATH,
                        f"//label[contains(normalize-space(text()), '{label.replace('*', '')}')]/following::select[1]"
                    )
                    print(f"      ✓ Found select by document order")
                except:
                    pass
            
            if not select_elem:
                print(f"      ❌ No select element found")
                return False
            
            # Scroll into view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                select_elem
            )
            time.sleep(0.5)
            
            # Get all options
            options = select_elem.find_elements(By.TAG_NAME, "option")
            print(f"      📋 {len(options)} options available")
            
            # Find best match
            best_match = None
            
            for option in options:
                try:
                    opt_text = (option.text or '').strip()
                    opt_value = (option.get_attribute('value') or '').strip()
                    
                    # Skip empty/placeholder
                    if not opt_text or opt_text.lower() in ['please select', 'bitte wählen', 'select...', '']:
                        continue
                    
                    # Check for match
                    if value.lower() == opt_text.lower():
                        best_match = option
                        print(f"      ✓ Exact match: '{opt_text}'")
                        break
                    
                    if value.lower() in opt_text.lower():
                        best_match = option
                        print(f"      ✓ Partial match: '{opt_text}'")
                        break
                        
                    # Special case for Austria - check for German name too
                    if value.lower() == 'austria' and ('österreich' in opt_text.lower() or 'austria' in opt_text.lower()):
                        best_match = option
                        print(f"      ✓ Found Austria variant: '{opt_text}'")
                        break
                        
                except:
                    continue
            
            if not best_match:
                print(f"      ⚠️  No match found for '{value}'")
                # Show available options
                available = [opt.text for opt in options if opt.text.strip() and opt.text.lower() not in ['please select', 'bitte wählen']]
                print(f"      Available: {available[:10]}")
                return False
            
            # Select using JavaScript for reliability
            self.driver.execute_script("arguments[0].selected = true;", best_match)
            
            # Trigger change events
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                select_elem
            )
            time.sleep(0.5)
            
            # Verify
            selected_option = select_elem.find_element(By.CSS_SELECTOR, "option:checked")
            selected_text = selected_option.text if selected_option else ''
            
            print(f"      ✅ Selected: '{selected_text}'")
            return True
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return False

    def handle_date_field(self, label: str, days_from_now: int = 1) -> bool:
        """Handle date picker - robust version with partial text matching."""
        print(f"    📅 DATE: '{label}'")
        
        target_date = datetime.now() + timedelta(days=days_from_now)
        print(f"      Target: {target_date.strftime('%Y-%m-%d')}")
        
        clean_label = label.replace('*', '').strip().lower()
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self._wait_for_dom_stable(timeout=2)
                
                # Strategy 1: Find by partial label text match (case insensitive)
                date_input = None
                calendar_button = None
                
                # Get all labels and find the one containing our text
                all_labels = self.driver.find_elements(By.TAG_NAME, 'label')
                target_label = None
                
                for lbl in all_labels:
                    try:
                        text = (lbl.text or '').strip().lower()
                        if clean_label in text or text in clean_label:
                            target_label = lbl
                            print(f"      ✓ Found label: '{lbl.text}'")
                            break
                    except:
                        continue
                
                if target_label:
                    # Look for input in parent container
                    try:
                        parent = target_label.find_element(By.XPATH, "..")
                        # Try to find input
                        inputs = parent.find_elements(By.TAG_NAME, "input")
                        for inp in inputs:
                            if inp.is_displayed():
                                date_input = inp
                                print(f"      ✓ Found input in parent")
                                break
                        
                        # Try to find calendar button
                        buttons = parent.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.is_displayed():
                                calendar_button = btn
                                print(f"      ✓ Found button in parent")
                                break
                                
                    except Exception as e:
                        print(f"      ⚠️  Parent search failed: {e}")
                
                # Strategy 2: If we have a calendar button, click it
                if calendar_button:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", calendar_button)
                        time.sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", calendar_button)
                        print(f"      🗓️  Opened calendar")
                        time.sleep(2)
                        
                        if self._select_date_from_calendar(target_date):
                            return True
                    except Exception as e:
                        print(f"      ⚠️  Calendar button failed: {e}")
                
                # Strategy 3: Direct input
                if date_input:
                    # Try European format first
                    date_formats = [
                        target_date.strftime("%d.%m.%Y"),
                        target_date.strftime("%Y-%m-%d"),
                        target_date.strftime("%d/%m/%Y"),
                    ]
                    
                    for fmt in date_formats:
                        try:
                            # Clear
                            self.driver.execute_script("arguments[0].value = '';", date_input)
                            time.sleep(0.2)
                            
                            # Click and enter
                            date_input.click()
                            time.sleep(0.2)
                            date_input.clear()
                            date_input.send_keys(fmt)
                            time.sleep(0.3)
                            
                            # Trigger change
                            self.driver.execute_script(
                                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                                date_input
                            )
                            time.sleep(0.5)
                            
                            # Check
                            actual = date_input.get_attribute('value')
                            if actual:
                                print(f"      ✅ Entered: {actual}")
                                return True
                        except:
                            continue
                    
                    # JavaScript fallback
                    for fmt in date_formats:
                        try:
                            self.driver.execute_script(
                                "arguments[0].value = arguments[1];"
                                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                                date_input, fmt
                            )
                            time.sleep(0.5)
                            actual = date_input.get_attribute('value')
                            if actual:
                                print(f"      ✅ Set via JS: {actual}")
                                return True
                        except:
                            continue
                
                # Strategy 4: Look for any visible date input
                if not date_input:
                    try:
                        inputs = self.driver.find_elements(By.XPATH, "//input[@type='date' or contains(@class, 'date')]")
                        for inp in inputs:
                            if inp.is_displayed():
                                date_input = inp
                                print(f"      ✓ Found date input by type/class")
                                # Try to fill it
                                date_input.click()
                                date_input.clear()
                                date_input.send_keys(target_date.strftime("%d.%m.%Y"))
                                time.sleep(0.5)
                                if date_input.get_attribute('value'):
                                    print(f"      ✅ Filled generic date input")
                                    return True
                                break
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    print(f"      🔄 Retrying...")
                    time.sleep(1)
                    
            except Exception as e:
                print(f"      ⚠️  Error: {str(e)[:60]}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        print(f"      ❌ Failed after {max_retries} attempts")
        return False
    
    def _select_date_from_calendar(self, target_date: datetime) -> bool:
        """Select date from calendar popup."""
        try:
            day = target_date.day
            print(f"      📆 Selecting day {day}...")
            
            time.sleep(1.5)  # Wait for calendar
            
            # Multiple strategies to find the day
            selectors = [
                f"//td[not(contains(@class, 'disabled')) and text()='{day}']",
                f"//button[text()='{day}']",
                f"//div[contains(@class, 'day') and text()='{day}']",
                f"//td[@data-day='{day}']",
                f"//div[contains(@class, 'calendar')]//td[text()='{day}']",
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            # Check not disabled
                            classes = elem.get_attribute('class') or ''
                            if 'disabled' not in classes and 'muted' not in classes:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                time.sleep(0.3)
                                self.driver.execute_script("arguments[0].click();", elem)
                                print(f"      ✅ Selected day {day}")
                                time.sleep(0.5)
                                return True
                except:
                    continue
            
            # Try "Tomorrow" button if available
            try:
                tomorrow_btn = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(text(), 'Tomorrow') or contains(@aria-label, 'Tomorrow')]"
                )
                self.driver.execute_script("arguments[0].click();", tomorrow_btn)
                print(f"      ✅ Clicked 'Tomorrow'")
                return True
            except:
                pass
            
            print(f"      ⚠️  Could not select day {day}")
            return False
            
        except Exception as e:
            print(f"      ❌ Calendar error: {e}")
            return False

    def _fill_by_label_for(self, label: str, value: str) -> bool:
        """Fill input by finding label text, then associated input."""
        try:
            label_elem = self.driver.find_element(By.XPATH, f"//label[text()='{label}']")
            try:
                input_field = label_elem.find_element(By.XPATH, ".//input")
            except:
                input_field = self.driver.find_element(
                    By.XPATH,
                    f"//label[text()='{label}']/following::input[1]"
                )
            input_field.clear()
            input_field.send_keys(value)
            return True
        except:
            pass

        try:
            label_elem = self.driver.find_element(By.XPATH, f"//label[contains(text(), '{label}')]")
            try:
                input_field = label_elem.find_element(By.XPATH, ".//input")
            except:
                input_field = self.driver.find_element(
                    By.XPATH,
                    f"//label[contains(text(), '{label}')]/following::input[1]"
                )
            input_field.clear()
            input_field.send_keys(value)
            return True
        except:
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

    def _fill_by_name(self, label: str, value: str) -> bool:
        """Fill by input name attribute."""
        input_field = self.driver.find_element(
            By.XPATH,
            f"//input[contains(@name, '{label.lower()}')]"
        )
        input_field.clear()
        input_field.send_keys(value)
        return True

    def upload_file(self, label: str, path: str) -> bool:
        """Upload file with UNIVERSAL completion polling and filename length safety."""
        from pathlib import Path
        
        # ----- FILENAME LENGTH SAFETY (belt-and-suspenders) -----
        path_obj = Path(path)
        upload_path = path
        temp_file = None
        
        if len(path_obj.name) > 45:  # ATS limit is often 50, leave buffer
            print(f"      ⚠️  Filename too long ({len(path_obj.name)} chars), creating short copy...")
            import shutil
            # Create short filename: cv_<8-char-id>.docx
            short_id = str(int(time.time()))[-8:]
            short_name = f"cv_{short_id}{path_obj.suffix}"
            temp_file = path_obj.parent / short_name
            shutil.copy2(path_obj, temp_file)
            upload_path = str(temp_file)
            print(f"      📎 Using temporary: {short_name} ({len(short_name)} chars)")
        # ---------------------------------------------------------
        
        def do_upload():
            strategies = [
                "//input[@type='file']",
                f"//label[contains(text(), '{label}')]/following::input[@type='file'][1]",
                f"//div[contains(text(), '{label}')]//input[@type='file']",
                f"//button[contains(text(), '{label}')]/..//input[@type='file']",
            ]

            for xpath in strategies:
                try:
                    input_field = self.driver.find_element(By.XPATH, xpath)
                    if input_field.is_displayed() or True:
                        input_field.send_keys(upload_path)
                        
                        # ----- GENERIC UPLOAD WAIT (works on any site) -----
                        filename = Path(upload_path).name
                        print(f"      ⏳ Uploading {filename}...")
                        start = time.time()
                        uploaded = False
                        
                        while time.time() - start < 30:
                            # Check if filename appears anywhere in the page
                            if filename in self.driver.page_source:
                                uploaded = True
                                break
                            
                            # Check if the input's value is set (some browsers show it)
                            try:
                                input_val = input_field.get_attribute('value')
                                if input_val and filename in input_val:
                                    uploaded = True
                                    break
                            except:
                                pass
                            
                            # Check for upload success indicators
                            page_lower = self.driver.page_source.lower()
                            if any(indicator in page_lower for indicator in [
                                'uploaded', 'complete', 'success', 'done', 
                                'hochgeladen', 'erfolgreich', 'fertig'
                            ]):
                                uploaded = True
                                break
                            
                            time.sleep(0.5)
                        # ---------------------------------------------------
                        
                        if uploaded:
                            print(f"      ✅ Upload confirmed")
                        else:
                            print(f"      ⚠️  Upload may still be in progress (will proceed)")
                        
                        return True
                except Exception as e:
                    continue
            return False

        success, msg = self._execute_with_stability(do_upload)
        
        # Cleanup temp file if created
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
                print(f"      🧹 Cleaned up temporary file")
            except:
                pass
        
        self._log_action("upload", f"{label}={path}", success, None if success else msg)
        return success

    def wait(self, seconds: int = 2) -> bool:
        time.sleep(seconds)
        return True

    def do_wait(self, seconds: int = 2) -> bool:
        """Alias to support WAIT actions mapped to do_wait."""
        return self.wait(seconds)
    
    def wait_for_element(self, by: By, value: str, timeout: int = 10) -> bool:
        """Wait for an element to be present and visible (dynamic wait)."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False
    
    def wait_for_form_inputs(self, timeout: int = 15) -> int:
        """Wait for form inputs to appear and return count."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            inputs = self.driver.find_elements(By.XPATH, "//input[@type!='hidden']")
            if len(inputs) > 0:
                return len(inputs)
            time.sleep(0.5)
        return 0

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
        """REPORT action - for debugging and status updates."""
        self._log_action("REPORT", message, True)
        print(f"    📢 {message}")

        if "cookie" in message.lower():
            print("    🍪 Checking for cookie banner...")
            return self.accept_cookies()

        return True

    def extract_page_context(self) -> PageContext:
        url = self.driver.current_url
        title = self.driver.title

        try:
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text[:500]
            print(f"    🔍 DEBUG: Page text preview: {body_text[:100]}...")
        except:
            pass

        buttons = []
        try:
            selectors = [
                "//button",
                "//a[@role='button']",
                "//a[contains(@class, 'btn')]",
                "//input[@type='button']",
                "//input[@type='submit']",
                "//div[contains(@class, 'button')]",
                "//span[contains(@class, 'button')]",
                "//a[contains(@href, 'javascript')]",
            ]

            for selector in selectors:
                try:
                    for elem in self.driver.find_elements(By.XPATH, selector):
                        text = (elem.text or elem.get_attribute('value') or '').replace('\n', ' ').strip()
                        aria_label = (elem.get_attribute('aria-label') or '').replace('\n', ' ').strip()
                        if text:
                            buttons.append(text)
                        elif aria_label:
                            buttons.append(aria_label)
                except:
                    continue
        except:
            pass

        inputs = self._detect_inputs()
        textareas = []

        if len(inputs) < 3:
            print(f"    🔍 Only {len(inputs)} inputs found, checking for iframe...")
            if self.switch_to_form_iframe():
                iframe_inputs = self._detect_inputs()
                if len(iframe_inputs) > inputs:
                    inputs = iframe_inputs
                    print(f"    ✅ Found {len(inputs)} inputs in iframe")

                    iframe_buttons = []
                    try:
                        for selector in selectors:
                            try:
                                for elem in self.driver.find_elements(By.XPATH, selector):
                                    text = (elem.text or elem.get_attribute('value') or '').replace('\n', ' ').strip()
                                    aria_label = (elem.get_attribute('aria-label') or '').replace('\n', ' ').strip()
                                    if text:
                                        iframe_buttons.append(text)
                                    elif aria_label:
                                        iframe_buttons.append(aria_label)
                            except:
                                continue
                    except:
                        pass

                    if iframe_buttons:
                        buttons = iframe_buttons

                    textareas = self._detect_textareas()

                self.driver.switch_to.default_content()
            else:
                print("    ⚠️  No iframe with form found")

        if not textareas:
            textareas = self._detect_textareas()

        inputs.extend(textareas)

        seen = set()
        buttons = [x for x in buttons if not (x in seen or seen.add(x))]

        file_inputs = []
        try:
            for elem in self.driver.find_elements(By.XPATH, "//input[@type='file']"):
                file_inputs.append('File upload')
        except:
            pass

        visible_text = ""
        try:
            visible_text = self.driver.find_element(By.TAG_NAME, "body").text[:3000]
        except:
            pass

        dom_hash = self._compute_dom_hash()
        page_type = self._detect_page_type(url, title, visible_text, buttons)

        return PageContext(
            url=url,
            title=title,
            buttons=buttons,
            inputs=inputs,
            file_inputs=file_inputs,
            textareas=textareas,
            select_boxes=[],
            visible_text=visible_text,
            dom_hash=dom_hash,
            page_type=page_type
        )

    def _detect_page_type(self, url: str, title: str, visible_text: str, buttons: List[str]) -> str:
        """Detect page type - corrected logic for job portals vs applications."""
        text_lower = visible_text.lower()
        url_lower = url.lower()
        buttons_lower = [b.lower() for b in buttons]

        has_form_fields = any(x in text_lower for x in [
            'vorname', 'nachname', 'e-mail', 'email', 'telefon',
            'phone', 'mobil', 'adresse', 'anschreiben', 'lebenslauf'
        ])

        has_apply_button = any(x in buttons_lower for x in [
            'jetzt bewerben', 'online bewerben', 'bewerben', 'apply now',
            'apply', 'online-bewerbung'
        ])

        is_job_portal = any(x in text_lower for x in [
            'jobbörse', 'jobs', 'stellenangebote', 'careers',
            'job search', 'job overview', 'stellenanzeigen'
        ]) or 'jobs-overview' in url_lower

        if has_form_fields:
            return "JOB_APPLICATION_FORM"

        if has_apply_button and not has_form_fields:
            return "JOB_APPLICATION_PAGE"

        if is_job_portal and not has_apply_button and not has_form_fields:
            return "JOB_PORTAL_LISTING"

        return "UNKNOWN"

    def execute_action(self, action: Action) -> Tuple[bool, str]:
        """v3.1: Execute with metrics collection."""
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
            if action.type in ['CLICK', 'FILL']:
                kwargs['threshold'] = 0.6 if action.type == 'CLICK' else 0.7

            # Special handling for CLICK - try button first, then checkbox if failed
            if action.type == 'CLICK':
                success = self.click_button(**kwargs)
                if not success:
                    # Retry as checkbox
                    success = self.click_checkbox(**kwargs)
            else:
                success = method(**kwargs)
            
            metric.end_time = time.time()
            metric.success = success
            metric.dom_hash_after = self._compute_dom_hash()
            self.metrics.append(metric)

            if success:
                return True, f"Executed in {metric.latency:.2f}s"
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
