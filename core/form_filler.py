"""
Form Filler - Rule-based browser automation with German site support
Fixed version with better cookie handling and field detection
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import time
import pyperclip

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    ElementNotInteractableException,
    TimeoutException
)


class ConservativeFormFiller:
    """
    Conservative form filler with explicit waits and German site support.
    """
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
    
    def start(self) -> 'ConservativeFormFiller':
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
    
    def prepare(self, url: str, cv_path: Path, cover_letter: str, user_data: dict = None) -> Dict:
        """
        Navigate to URL and fill application form.
        
        Returns dict of filled fields and status.
        """
        if not self.driver:
            self.start()
        
        if not url:
            raise ValueError("No URL provided for browser automation")
        
        result = {
            'success': False,
            'filled_fields': {},
            'errors': []
        }
        
        try:
            # Navigate
            self.driver.get(url)
            time.sleep(4)
            
            # Handle cookies
            if not self._handle_cookies():
                result['errors'].append("Could not handle cookies automatically")
            
            # Check if on job description page, click apply
            if not self._is_application_form():
                if not self._click_apply_button():
                    result['errors'].append("Could not find apply button")
                else:
                    time.sleep(3)
                    # Handle cookies again after navigation
                    self._handle_cookies()
            
            # Wait for form to load
            time.sleep(2)
            
            # Fill form
            if user_data:
                filled = self._fill_personal_data(user_data)
                result['filled_fields'].update(filled)
            
            # Fill cover letter
            if cover_letter and self._fill_cover_letter(cover_letter):
                result['filled_fields']['cover_letter'] = True
            
            # Upload CV
            if cv_path and cv_path.exists() and self._upload_cv(cv_path):
                result['filled_fields']['cv'] = True
            
            result['success'] = len(result['filled_fields']) > 0
            
        except Exception as e:
            result['errors'].append(str(e))
        
        return result
    
    def _handle_cookies(self) -> bool:
        """
        Handle cookie consent with multiple strategies.
        Updated for German sites like XAL.
        """
        # Cookie button variations (text, description)
        cookie_buttons: List[tuple] = [
            # German - XAL style
            ("//button[contains(text(), 'Alle Cookies')]", "Alle Cookies"),
            ("//button[contains(text(), 'Alle akzeptieren')]", "Alle akzeptieren"),
            ("//a[contains(text(), 'Alle Cookies')]", "Alle Cookies link"),
            ("//button[contains(text(), 'Zustimmen')]", "Zustimmen"),
            ("//button[contains(text(), 'Akzeptieren')]", "Akzeptieren"),
            # English
            ("//button[contains(text(), 'Accept all')]", "Accept all"),
            ("//button[contains(text(), 'Accept')]", "Accept"),
            ("//button[contains(text(), 'Allow all')]", "Allow all"),
            ("//button[contains(text(), 'I agree')]", "I agree"),
            # CSS selectors
            ("[data-testid='cookie-accept']", "testid"),
            ("#onetrust-accept-btn-handler", "OneTrust"),
            (".cookie-consent__accept", "consent class"),
        ]
        
        for xpath, desc in cookie_buttons:
            try:
                if xpath.startswith("//"):
                    # XPath - wait for clickable
                    btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                else:
                    # CSS Selector
                    btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, xpath))
                    )
                
                # Scroll and click via JavaScript (bypasses overlay issues)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", 
                    btn
                )
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", btn)
                
                print(f"  ✓ Handled cookies: {desc}")
                time.sleep(2)  # Wait for modal to close
                return True
                
            except:
                continue
        
        return False
    
    def _is_application_form(self) -> bool:
        """Check if current page has application form fields."""
        indicators = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id="email"]',
            'textarea',
            'input[type="file"]',
            'button[type="submit"]',
            'form',
        ]
        
        for selector in indicators:
            try:
                self.driver.find_element(By.CSS_SELECTOR, selector)
                return True
            except:
                continue
        
        return False
    
    def _click_apply_button(self) -> bool:
        """Click apply button on job description page."""
        apply_variations = [
            "Jetzt bewerben",
            "Bewerben", 
            "Apply",
            "Apply now",
            "Online bewerben",
        ]
        
        for text in apply_variations:
            try:
                # Try button
                xpath = f'//button[contains(text(), "{text}")]'
                btn = self.driver.find_element(By.XPATH, xpath)
                
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", 
                    btn
                )
                time.sleep(1)
                btn.click()
                print(f"  ✓ Clicked apply: {text}")
                return True
                
            except:
                try:
                    # Try link
                    xpath = f'//a[contains(text(), "{text}")]'
                    btn = self.driver.find_element(By.XPATH, xpath)
                    
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", 
                        btn
                    )
                    time.sleep(1)
                    btn.click()
                    print(f"  ✓ Clicked apply link: {text}")
                    return True
                    
                except:
                    continue
        
        return False
    
    def _fill_personal_data(self, user_data: dict) -> Dict[str, bool]:
        """Fill name, email, phone with German support."""
        filled = {}
        
        # Field mappings with German variants
        field_mapping = {
            'first_name': {
                'names': [
                    'firstName', 'first_name', 'firstname', 'fname',
                    'Vorname', 'vorname', 'first-name',
                    'candidate_first_name', 'applicant_first_name'
                ],
                'label_texts': ['Vorname', 'First name', 'First Name']
            },
            'last_name': {
                'names': [
                    'lastName', 'last_name', 'lastname', 'lname',
                    'Nachname', 'nachname', 'last-name',
                    'candidate_last_name', 'applicant_last_name'
                ],
                'label_texts': ['Nachname', 'Last name', 'Last Name', 'Surname']
            },
            'email': {
                'names': [
                    'email', 'email_address', 'emailAddress', 'e-mail',
                    'E-Mail', 'E-mail', 'e_mail',
                    'candidate_email', 'applicant_email'
                ],
                'label_texts': ['E-Mail', 'Email', 'E-mail', 'Mail']
            },
            'phone': {
                'names': [
                    'phone', 'phoneNumber', 'mobile', 'tel', 'telephone',
                    'Telefon', 'telefon', 'Handy', 'Mobil', 'handy', 'mobil',
                    'phone-input', 'mobile-number',
                    'candidate_phone', 'applicant_phone'
                ],
                'label_texts': ['Telefon', 'Phone', 'Mobile', 'Handy', 'Mobil']
            },
        }
        
        for key, config in field_mapping.items():
            if key not in user_data or not user_data[key]:
                continue
            
            value = user_data[key]
            found = False
            
            # Try by name attribute
            for name in config['names']:
                try:
                    field = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.NAME, name))
                    )
                    self._safe_fill(field, value)
                    filled[key] = True
                    found = True
                    print(f"  ✓ Filled {key}")
                    break
                except:
                    continue
            
            if found:
                continue
            
            # Try by ID
            for name in config['names']:
                try:
                    field = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.ID, name))
                    )
                    self._safe_fill(field, value)
                    filled[key] = True
                    found = True
                    print(f"  ✓ Filled {key} (by id)")
                    break
                except:
                    continue
            
            if found:
                continue
            
            # Try by label text
            for label_text in config['label_texts']:
                try:
                    # Find label, then associated input
                    label = self.driver.find_element(
                        By.XPATH, 
                        f"//label[contains(text(), '{label_text}')]"
                    )
                    input_id = label.get_attribute('for')
                    if input_id:
                        field = self.driver.find_element(By.ID, input_id)
                    else:
                        # Input inside label
                        field = label.find_element(By.TAG_NAME, 'input')
                    
                    self._safe_fill(field, value)
                    filled[key] = True
                    found = True
                    print(f"  ✓ Filled {key} (by label)")
                    break
                except:
                    continue
            
            if not found:
                print(f"  ⚠ Field not found: {key}")
        
        return filled
    
    def _safe_fill(self, field, value: str):
        """Safely fill a field with scrolling and retries."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Scroll into view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", 
                    field
                )
                time.sleep(0.5)
                
                # Clear and fill
                field.clear()
                field.send_keys(value)
                return
                
            except ElementNotInteractableException:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                raise
    
    def _fill_cover_letter(self, cover_letter: str) -> bool:
        """Find and fill cover letter textarea."""
        # Try various selectors
        selectors = [
            '//textarea[contains(@name, "cover")]',
            '//textarea[contains(@name, "letter")]',
            '//textarea[contains(@name, "message")]',
            '//textarea[contains(@name, "description")]',
            '//textarea[contains(@id, "cover")]',
            '//textarea[contains(@id, "letter")]',
            '//textarea[contains(@placeholder, "cover" or "letter" or "motivation")]',
            '//label[contains(text(), "Anschreiben")]/following-sibling::textarea',
            '//label[contains(text(), "Cover")]/following-sibling::textarea',
            'textarea',
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    field = self.driver.find_element(By.XPATH, selector)
                else:
                    field = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                # Check if it's a large textarea (cover letter size)
                size = field.size
                if size['height'] < 100 and selector != 'textarea':
                    continue  # Probably not a cover letter field
                
                self._safe_fill(field, cover_letter)
                print("  ✓ Filled cover letter")
                return True
                
            except:
                continue
        
        # Fallback: copy to clipboard
        pyperclip.copy(cover_letter)
        print("  ⚠ Cover letter copied to clipboard - please paste manually")
        return False
    
    def _upload_cv(self, cv_path: Path) -> bool:
        """Upload CV file."""
        selectors = [
            'input[type="file"]',
            'input[name*="resume"]',
            'input[name*="cv"]',
            'input[name*="attachment"]',
            'input[name*="document"]',
            'input[id*="file"]',
            'input[id*="cv"]',
            'input[accept*=".pdf"]',
        ]
        
        for selector in selectors:
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                # Make visible if hidden
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; "
                    "arguments[0].style.visibility = 'visible';",
                    file_input
                )
                
                file_input.send_keys(str(cv_path.absolute()))
                print("  ✓ Uploaded CV")
                return True
                
            except:
                continue
        
        print("  ⚠ Could not auto-upload CV - please upload manually")
        return False
    
    def find_submit_button(self):
        """Find submit button."""
        selectors = [
            '//button[contains(text(), "Submit")]',
            '//button[contains(text(), "Apply")]',
            '//button[contains(text(), "Send")]',
            '//button[contains(text(), "Absenden")]',
            '//button[contains(text(), "Bewerbung absenden")]',
            '//button[contains(text(), "Jetzt bewerben")]',
            'button[type="submit"]',
            'input[type="submit"]',
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
    
    def take_screenshot(self, filename: str):
        """Save screenshot for debugging."""
        if self.driver:
            self.driver.save_screenshot(filename)
    
    def close(self):
        """Close browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


def auto_fill_application(url: str, user_data: dict, cover_letter: str, cv_path: str):
    """
    Factory function for CLI compatibility.
    Returns the filler instance for further control.
    """
    filler = ConservativeFormFiller()
    result = filler.prepare(
        url=url,
        cv_path=Path(cv_path),
        cover_letter=cover_letter,
        user_data=user_data
    )
    return filler