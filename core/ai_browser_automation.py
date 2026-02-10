"""
AI Browser Automation - Production Implementation
Uses browser-use library with Gemini/Ollama for autonomous form filling
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContext

from config import settings


@dataclass
class AIAutomationResult:
    success: bool
    filled_fields: Dict[str, bool]
    errors: list
    screenshot_path: Optional[str] = None
    final_url: Optional[str] = None


class AIBrowserAutomator:
    """
    Fully autonomous browser automation using AI.
    No rules, no XPath - pure AI vision and reasoning.
    """

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.agent: Optional[Agent] = None
        self.llm = self._get_llm()

    def _get_llm(self):
        """Initialize LLM based on settings."""
        if settings.LLM_PROVIDER == 'gemini':
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",  # Fast, cheap, good for automation
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.1  # Low temperature for deterministic actions
            )
        elif settings.LLM_PROVIDER == 'ollama':
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.LLM_MODEL,
                base_url="http://localhost:11434",
                temperature=0.1
            )
        else:
            raise ValueError(f"AI automation requires 'gemini' or 'ollama', got: {settings.LLM_PROVIDER}")

    async def fill_application(
        self,
        url: str,
        user_data: Dict[str, str],
        cover_letter: str,
        cv_path: Path
    ) -> AIAutomationResult:
        """
        Autonomously fill job application form.

        The AI will:
        1. Navigate to the URL
        2. Handle cookie consent
        3. Find and click apply button
        4. Fill all form fields
        5. Upload CV
        6. Fill cover letter
        7. Stop before submit (for user review)
        """
        result = AIAutomationResult(
            success=False,
            filled_fields={},
            errors=[]
        )

        try:
            # Initialize browser
            self.browser = Browser(config=BrowserConfig(headless=False))

            # Create task description for AI
            task = self._create_task(url, user_data, cover_letter, cv_path)

            # Create AI agent
            self.agent = Agent(
                task=task,
                llm=self.llm,
                browser=self.browser,
            )

            print("  🤖 AI Agent starting...")
            print(f"  🌐 URL: {url}")
            print(f"  👤 Candidate: {user_data.get('first_name', '')} {user_data.get('last_name', '')}")

            # Run the agent
            await self.agent.run()

            # Get final state
            result.success = True
            result.filled_fields = {
                'form_accessed': True,
                'ai_completed': True
            }
            result.final_url = self.agent.browser_context.page.url if self.agent.browser_context else url

            print("  ✅ AI automation completed")
            print("  ⚠️  Please review the form before submitting")

        except Exception as e:
            result.errors.append(str(e))
            print(f"  ❌ AI automation failed: {e}")

            # Take screenshot for debugging
            try:
                if self.agent and self.agent.browser_context:
                    await self.agent.browser_context.page.screenshot(path="error_screenshot.png")
                    result.screenshot_path = "error_screenshot.png"
            except:
                pass

        return result

    def _create_task(
        self,
        url: str,
        user_data: Dict[str, str],
        cover_letter: str,
        cv_path: Path
    ) -> str:
        """Create detailed task prompt for AI agent."""

        task = f"""Fill out a job application form on the website: {url}

CANDIDATE INFORMATION:
- First Name: {user_data.get('first_name', '')}
- Last Name: {user_data.get('last_name', '')}
- Email: {user_data.get('email', '')}
- Phone: {user_data.get('phone', '')}
- CV File Location: {cv_path.absolute()}
- Cover Letter: {cover_letter[:500]}... [truncated for brevity]

STEP-BY-STEP INSTRUCTIONS:

1. NAVIGATE TO PAGE
   - Go to: {url}
   - Wait for page to fully load

2. HANDLE COOKIE CONSENT (if present)
   - Look for buttons like "Alle Cookies akzeptieren", "Accept all", "Zustimmen"
   - Click the accept/confirm button
   - Wait for cookie banner to disappear

3. FIND AND CLICK APPLY BUTTON
   - Look for: "Jetzt bewerben", "Bewerben", "Apply", "Apply now", "Online bewerben"
   - Scroll down if needed to find the button
   - Click it and wait for form to load

4. FILL PERSONAL INFORMATION
   - First Name (Vorname): {user_data.get('first_name', '')}
   - Last Name (Nachname): {user_data.get('last_name', '')}
   - Email (E-Mail): {user_data.get('email', '')}
   - Phone (Telefon/Handy): {user_data.get('phone', '')}

   Look for fields labeled:
   - German: "Vorname", "Nachname", "E-Mail", "Telefon", "Handy", "Mobil"
   - English: "First name", "Last name", "Email", "Phone", "Mobile"

5. UPLOAD CV
   - Find file upload field (usually labeled "Lebenslauf", "CV", "Resume", "Dokument")
   - Upload the file from: {cv_path.absolute()}
   - Wait for upload to complete

6. FILL COVER LETTER
   - Find textarea labeled "Anschreiben", "Cover Letter", "Motivation", "Message"
   - Paste the complete cover letter text provided above
   - Ensure all text is entered

7. FINAL CHECK
   - Verify all required fields are filled
   - Look for any red asterisks (*) indicating required fields
   - Fill any missing required fields

8. STOP BEFORE SUBMIT
   - DO NOT click the final submit button
   - Wait for user confirmation
   - The form should be ready for manual review

IMPORTANT NOTES:
- If any field is not found, scroll down to check if it\'s below the fold
- Handle any popups or modals that appear
- If the page is in German, look for German field labels
- If upload fails, note it but continue with other fields
- Take your time - accuracy is more important than speed
"""
        return task

    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()


# Synchronous wrapper for CLI compatibility
def run_ai_automation(url: str, user_data: dict, cover_letter: str, cv_path: str):
    """
    Synchronous wrapper for AI automation.
    Returns the automator instance for further control.
    """
    async def _run():
        automator = AIBrowserAutomator()
        result = await automator.fill_application(url, user_data, cover_letter, Path(cv_path))
        return automator, result

    return asyncio.run(_run())