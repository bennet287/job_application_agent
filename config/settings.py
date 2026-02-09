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
# LLM CONFIGURATION - GEMINI
# ============================================================================

# Provider selection: 'ollama', 'openai', 'gemini', 'deepseek'
#LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')

# =============================================================================
# GEMINI (Google - FREE TIER AVAILABLE)
# Get API key from: https://aistudio.google.com/app/apikey
# Free tier: 15 requests/minute, 1500 requests/day
# =============================================================================
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
LLM_MODEL = os.getenv('LLM_MODEL', 'llama3.1:8b')

# =============================================================================
# OLLAMA (Local - FULLY FREE, PRIVATE)
# Install from: https://ollama.com/

# Then run: ollama pull llama3.1:8b
# =============================================================================
OLLAMA_URL = "http://localhost:11434/api/generate"

# =============================================================================
# DEEPSEEK (Cloud - FREE TIER)
# Get API key from: https://platform.deepseek.com/
# =============================================================================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'

# =============================================================================
# OPENAI (Paid - MOST CAPABLE)
# =============================================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

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
MIN_HOURS_BETWEEN_APPS = float(os.getenv('MIN_HOURS', '0'))  # ← CHANGED for testing

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
