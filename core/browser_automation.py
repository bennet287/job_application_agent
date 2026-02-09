from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import pyperclip  # pip install pyperclip


class BrowserAutomation:
    def __init__(self):
        self.driver = None
    
    def start(self):
        """Start browser."""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        self.driver = webdriver.Chrome(options=options)
        return self
    
    def fill_form(self, url: str, data: dict):
        """
        Fill application form.
        data = {
            'first_name': '...',
            'last_name': '...',
            'email': '...',
            'phone': '...',
            'cover_letter': '...',
            'cv_path': '...'
        }
        """
        self.driver.get(url)
        time.sleep(3)  # Let page load
        
        # Try to find and fill common fields
        field_mapping = {
            'first_name': ['firstName', 'first_name', 'firstname', 'fname'],
            'last_name': ['lastName', 'last_name', 'lastname', 'lname'],
            'email': ['email', 'email_address'],
            'phone': ['phone', 'phoneNumber', 'mobile'],
        }
        
        filled = {}
        
        for data_key, possible_names in field_mapping.items():
            if data_key not in data:
                continue
                
            for name in possible_names:
                try:
                    # Try by name
                    field = self.driver.find_element(By.NAME, name)
                    field.clear()
                    field.send_keys(data[data_key])
                    filled[data_key] = True
                    break
                except NoSuchElementException:
                    try:
                        # Try by ID
                        field = self.driver.find_element(By.ID, name)
                        field.clear()
                        field.send_keys(data[data_key])
                        filled[data_key] = True
                        break
                    except NoSuchElementException:
                        continue
        
        # Handle cover letter (textarea)
        if 'cover_letter' in data:
            cl_filled = False
            for name in ['cover_letter', 'coverLetter', 'message', 'description']:
                try:
                    field = self.driver.find_element(By.NAME, name)
                    field.clear()
                    field.send_keys(data['cover_letter'])
                    cl_filled = True
                    break
                except:
                    try:
                        field = self.driver.find_element(By.TAG_NAME, 'textarea')
                        field.clear()
                        field.send_keys(data['cover_letter'])
                        cl_filled = True
                        break
                    except:
                        continue
            
            if not cl_filled:
                # Copy to clipboard for manual paste
                pyperclip.copy(data['cover_letter'])
                print("⚠ Cover letter copied to clipboard - please paste manually")
        
        # Handle file upload
        if 'cv_path' in data:
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                file_input.send_keys(data['cv_path'])
                filled['cv'] = True
            except:
                print("⚠ Could not auto-upload CV - please upload manually")
        
        return filled
    
    def screenshot(self, filename: str):
        """Save screenshot."""
        self.driver.save_screenshot(filename)
    
    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()


def auto_fill_application(url: str, user_data: dict, cover_letter: str, cv_path: str):
    """Main automation function."""
    automation = BrowserAutomation().start()
    
    try:
        data = {
            **user_data,
            'cover_letter': cover_letter,
            'cv_path': cv_path
        }
        
        filled = automation.fill_form(url, data)
        
        print(f"\n✓ Auto-filled: {', '.join(filled.keys())}")
        print("⚠ Please review and complete any remaining fields")
        
        return automation  # Return instance so user can control it
        
    except Exception as e:
        print(f"✗ Automation error: {e}")
        automation.close()
        return None