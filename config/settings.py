"""
Configuration settings for Job Application Agent
All paths, API keys, and system limits defined here
"""

import os
from pathlib import Path

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

ASSETS_DIR = PROJECT_ROOT / 'assets'
CV_VERSIONS_DIR = ASSETS_DIR / 'cv_versions'
COVER_LETTERS_DIR = ASSETS_DIR / 'cover_letters'
DECISIONS_DIR = ASSETS_DIR / 'decisions'
DB_PATH = PROJECT_ROOT / 'applications.db'

# Create directories if they don't exist
for directory in [ASSETS_DIR, CV_VERSIONS_DIR, COVER_LETTERS_DIR, DECISIONS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# LLM CONFIGURATION - SPLIT BY CAPABILITY
# ============================================================================

# =============================================================================
# TEXT PROCESSING LLM (Ollama recommended for privacy/cost)
# Used for: CV analysis, cover letter generation, scoring, JD parsing
# =============================================================================
LLM_TEXT_PROVIDER = os.getenv('LLM_TEXT_PROVIDER', 'ollama')
LLM_TEXT_MODEL = os.getenv('LLM_TEXT_MODEL', 'llama3.1:8b')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')

# =============================================================================
# BROWSER AUTOMATION LLM (MUST support tool-calling)
# Used for: AI browser automation only
# Options: gemini (recommended, free), openai
# =============================================================================
LLM_BROWSER_PROVIDER = os.getenv('LLM_BROWSER_PROVIDER', 'gemini')
LLM_BROWSER_MODEL = os.getenv('LLM_BROWSER_MODEL', 'gemini-1.5-flash')

# =============================================================================
# API KEYS (only needed for browser provider and non-local text providers)
# =============================================================================

# GEMINI API KEY - Get from https://aistudio.google.com/app/apikey
# Free tier: 15 requests/minute, 1500 requests/day
# SECURITY: Load from environment variable, fallback to empty string
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# If environment variable not set, you can temporarily uncomment and set here:
# ⚠️  WARNING: Do not commit API keys to git! Use .env file instead.

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

# =============================================================================
# DEEPSEEK (Cloud - FREE TIER) - Alternative text provider
# =============================================================================
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'

# General LLM settings
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))

# ============================================================================
# BROWSER AUTOMATION
# ============================================================================
BROWSER_PROFILE_PATH = os.getenv('BROWSER_PROFILE_PATH', '')

# ============================================================================
# OPERATIONAL LIMITS
# ============================================================================
DAILY_APPLICATION_CAP = int(os.getenv('DAILY_CAP', '5'))

# TESTING MODE: Set to 0 for rapid testing, 0.5 for production
MIN_HOURS_BETWEEN_APPS = float(os.getenv('MIN_HOURS', '0'))

EXPLORATION_RATE = float(os.getenv('EXPLORATION_RATE', '0.15'))

# ============================================================================
# VERSIONING
# ============================================================================
RATIONALE_FRAMEWORK_VERSION = "v2.1"
PROMPT_VERSION = "2025.01.15"

# ============================================================================
# FILE PERMISSIONS (for permission enforcement)
# ============================================================================
SENSITIVE_FILE_PERMS = 0o600  # Master CV, DB, decisions
DIR_PERMS = 0o700             # Assets directories
REGULAR_FILE_PERMS = 0o644    # Code files
EXECUTABLE_PERMS = 0o755      # Scripts