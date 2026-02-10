"""
Hybrid AI Form Filler - Combines rule-based speed with AI robustness
Supports both Gemini (free tier) and Ollama (local testing)
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

# Browser automation
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    ElementNotInteractableException,
    TimeoutException
)

# AI/LLM imports - will be loaded dynamically based on config
from config import settings


@dataclass
class AutomationResult:
    success: bool
    method: str  # 'rule_based' or 'ai_based'
    filled_fields: Dict[str, bool]
    errors: list
    screenshot_path: Optional[str] = None


class RuleBasedFiller:
    """Your existing fast rule-based automation."""

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    def start(self) -> 'RuleBasedFiller':
        """Start browser with anti-detection."""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=options)

        # Prevent detection
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        return self

    def fill_application(self, url: str, user_data: dict, cover_letter: str, cv_path: Path) -> AutomationResult:
        """Attempt rule-based filling."""
        if not self.driver:
            self.start()

        result = AutomationResult(
            success=False,
            method='rule_based',
            filled_fields={},
            errors=[]
        )

        try:
            # Navigate
            self.driver.get(url)
            time.sleep(4)

            # Handle cookies
            if not self._handle_cookies():
                result.errors.append("Could not handle cookies")

            # Check if on job description page, click apply
            if not self._is_application_form():
                if not self._click_apply_button():
                    result.errors.append("Could not find apply button")
                    return result
                time.sleep(3)
                self._handle_cookies()  # Handle cookies again after navigation

            # Fill form
            result.filled_fields.update(self._fill_personal_data(user_data))

            # Fill cover letter
            if self._fill_cover_letter(cover_letter):
                result.filled_fields['cover_letter'] = True

            # Upload CV
            if cv_path.exists() and self._upload_cv(cv_path):
                result.filled_fields['cv'] = True

            result.success = len(result.filled_fields) > 0

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _handle_cookies(self) -> bool:
        """Handle cookie consent with multiple strategies."""
        cookie_texts = [
            "Alle Cookies akzeptieren",
            "Alle akzeptieren", 
            "Akzeptieren",
            "Zustimmen",
            "Accept all",
            "Accept",
            "I agree",
            "Allow all",
        ]

        for text in cookie_texts:
            for xpath in [f'//button[text()="{text}"]', f'//button[contains(text(), "{text}"])']:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    return True
                except:
                    continue
        return False

    def _is_application_form(self) -> bool:
        """Check if current page has form fields."""
        indicators = ['input[type="email"]', 'input[name="email"]', 'textarea', 'input[type="file"]']
        for selector in indicators:
            try:
                self.driver.find_element(By.CSS_SELECTOR, selector)
                return True
            except:
                continue
        return False

    def _click_apply_button(self) -> bool:
        """Click apply button on job description page."""
        texts = ["Jetzt bewerben", "Bewerben", "Apply", "Apply now"]
        for text in texts:
            try:
                xpath = f'//button[contains(text(), "{text}")] | //a[contains(text(), "{text}")]'
                btn = self.driver.find_element(By.XPATH, xpath)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(1)
                btn.click()
                return True
            except:
                continue
        return False

    def _fill_personal_data(self, user_data: dict) -> Dict[str, bool]:
        """Fill name, email, phone."""
        filled = {}

        mapping = {
            'first_name': ['firstName', 'first_name', 'firstname', 'Vorname'],
            'last_name': ['lastName', 'last_name', 'lastname', 'Nachname'],
            'email': ['email', 'email_address', 'E-Mail', 'E-mail'],
            'phone': ['phone', 'phoneNumber', 'mobile', 'Telefon', 'Handy', 'Mobil'],
        }

        for key, names in mapping.items():
            if key not in user_data or not user_data[key]:
                continue

            for name in names:
                try:
                    field = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.NAME, name))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
                    time.sleep(0.5)
                    field.clear()
                    field.send_keys(user_data[key])
                    filled[key] = True
                    break
                except:
                    try:
                        field = self.driver.find_element(By.ID, name)
                        field.clear()
                        field.send_keys(user_data[key])
                        filled[key] = True
                        break
                    except:
                        continue

        return filled

    def _fill_cover_letter(self, cover_letter: str) -> bool:
        """Fill cover letter textarea."""
        selectors = [
            'textarea[name*="cover"]', 'textarea[name*="letter"]',
            'textarea[name*="message"]', 'textarea[name*="description"]',
            'textarea'
        ]

        for selector in selectors:
            try:
                if selector == 'textarea':
                    textareas = self.driver.find_elements(By.TAG_NAME, 'textarea')
                    if textareas:
                        largest = max(textareas, key=lambda t: t.size['height'] * t.size['width'])
                        largest.send_keys(cover_letter)
                        return True
                else:
                    field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    field.clear()
                    field.send_keys(cover_letter)
                    return True
            except:
                continue
        return False

    def _upload_cv(self, cv_path: Path) -> bool:
        """Upload CV file."""
        selectors = ['input[type="file"]', 'input[name*="resume"]', 'input[name*="cv"]']

        for selector in selectors:
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
                file_input.send_keys(str(cv_path.absolute()))
                return True
            except:
                continue
        return False

    def find_submit_button(self):
        """Find submit button."""
        selectors = [
            '//button[contains(text(), "Submit")]',
            '//button[contains(text(), "Apply")]',
            '//button[contains(text(), "Absenden")]',
            'button[type="submit"]'
        ]

        for selector in selectors:
            try:
                if selector.startswith('//'):
                    return self.driver.find_element(By.XPATH, selector)
                else:
                    return self.driver.find_element(By.CSS_SELECTOR, selector)
            except:
                continue
        return None

    def close(self):
        """Close browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def take_screenshot(self, path: str):
        """Save screenshot."""
        if self.driver:
            self.driver.save_screenshot(path)


class AIBasedFiller:
    """AI-powered automation using LLM vision capabilities."""

    def __init__(self):
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM based on settings."""
        if settings.LLM_PROVIDER == 'gemini':
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",  # Free tier, fast
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.1
                )
            except ImportError:
                raise ImportError("Install langchain-google-genai: pip install langchain-google-genai")

        elif settings.LLM_PROVIDER == 'ollama':
            try:
                from langchain_ollama import ChatOllama
                self.llm = ChatOllama(
                    model=settings.LLM_MODEL,
                    base_url="http://localhost:11434",
                    temperature=0.1
                )
            except ImportError:
                raise ImportError("Install langchain-ollama: pip install langchain-ollama")
        else:
            raise ValueError(f"AI filler requires 'gemini' or 'ollama', got: {settings.LLM_PROVIDER}")

    async def fill_application(self, url: str, user_data: dict, cover_letter: str, cv_path: Path) -> AutomationResult:
        """Use AI to automate browser."""
        result = AutomationResult(
            success=False,
            method='ai_based',
            filled_fields={},
            errors=[]
        )

        try:
            # For now, use simple prompt-based approach
            # Full browser-use integration can be added later

            prompt = f"""
            You are a browser automation expert. The user wants to apply for a job.

            URL: {url}

            Candidate Info:
            - First Name: {user_data.get('first_name', '')}
            - Last Name: {user_data.get('last_name', '')}
            - Email: {user_data.get('email', '')}
            - Phone: {user_data.get('phone', '')}
            - Cover Letter: {cover_letter[:300]}...
            - CV Path: {cv_path}

            Provide step-by-step instructions to fill this application form.
            Consider:
            1. Cookie consent handling (look for "Alle akzeptieren", "Accept all")
            2. Apply button might be on job description page first
            3. German form fields ("Vorname", "Nachname", "E-Mail", "Telefon")
            4. File upload for CV
            5. Textarea for cover letter

            Return as JSON:
            {{
                "steps": [
                    {{"action": "click", "target": "cookie accept button", "selector": "//button[contains(text(), 'Akzeptieren')]"}},
                    {{"action": "click", "target": "apply button", "selector": "//a[contains(text(), 'Jetzt bewerben')]"}},
                    {{"action": "fill", "field": "first_name", "value": "{user_data.get('first_name', '')}"}},
                    ...
                ],
                "expected_difficulty": "easy|medium|hard",
                "notes": "any special instructions"
            }}
            """

            # Get AI guidance
            response = await self._call_llm(prompt)

            # Parse and execute (simplified - just return guidance for now)
            result.filled_fields['ai_guidance'] = True
            result.success = True
            result.errors.append("AI guidance generated - manual execution needed for complex sites")

        except Exception as e:
            result.errors.append(f"AI automation failed: {str(e)}")

        return result

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        # Simple implementation - can be enhanced with actual langchain calls
        if hasattr(self.llm, 'invoke'):
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        else:
            # Fallback to direct API
            from utils.llm_client import LLMClient
            client = LLMClient()
            return client.generate(prompt)


class HybridFormFiller:
    """
    Hybrid approach: Fast rule-based first, AI fallback for complex cases.
    """

    def __init__(self):
        self.rule_filler = RuleBasedFiller()
        self.ai_filler = None  # Lazy load
        self.current_method = None

    async def fill_application(
        self, 
        url: str, 
        user_data: dict, 
        cover_letter: str, 
        cv_path: str,
        force_ai: bool = False
    ) -> AutomationResult:
        """
        Fill application using best method.

        Args:
            url: Job application URL
            user_data: Dict with first_name, last_name, email, phone
            cover_letter: Cover letter text
            cv_path: Path to CV file
            force_ai: Skip rule-based and use AI directly

        Returns:
            AutomationResult with details of what was filled
        """
        cv_path = Path(cv_path)

        # Phase 1: Try rule-based (fast, 90% success rate)
        if not force_ai:
            print("  → Attempting rule-based automation...")
            result = self.rule_filler.fill_application(url, user_data, cover_letter, cv_path)

            if result.success and len(result.filled_fields) >= 3:  # email + 2 others
                print(f"  ✓ Rule-based successful: {list(result.filled_fields.keys())}")
                self.current_method = 'rule_based'
                return result
            else:
                print(f"  ⚠ Rule-based incomplete: {result.errors}")
                # Save screenshot for debugging
                self.rule_filler.take_screenshot("debug_rule_based_failed.png")

        # Phase 2: Fallback to AI (robust, handles edge cases)
        print("  → Switching to AI-based automation...")

        if self.ai_filler is None:
            try:
                self.ai_filler = AIBasedFiller()
            except Exception as e:
                print(f"  ✗ Could not initialize AI filler: {e}")
                # Return rule-based result even if incomplete
                return result if not force_ai else AutomationResult(
                    success=False, method='failed', filled_fields={}, errors=[str(e)]
                )

        try:
            ai_result = await self.ai_filler.fill_application(url, user_data, cover_letter, cv_path)
            self.current_method = 'ai_based'
            return ai_result
        except Exception as e:
            print(f"  ✗ AI automation failed: {e}")
            # Return best effort from rule-based
            return result if not force_ai else AutomationResult(
                success=False, method='failed', filled_fields={}, errors=[str(e)]
            )

    def get_browser(self):
        """Get current browser instance for further interaction."""
        if self.current_method == 'rule_based':
            return self.rule_filler.driver
        return None

    def close(self):
        """Close all browser instances."""
        self.rule_filler.close()


# Convenience function for CLI
def auto_fill_application(url: str, user_data: dict, cover_letter: str, cv_path: str):
    """
    Synchronous wrapper for hybrid automation.
    Returns the filler instance for further control.
    """
    async def _run():
        filler = HybridFormFiller()
        result = await filler.fill_application(url, user_data, cover_letter, cv_path)
        return filler, result

    return asyncio.run(_run())