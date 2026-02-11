# core/__init__.py - UPDATED
from .jd_processor import JDProcessor
from .match_scorer import MatchScorer
from .cv_surgical_editor import SurgicalCVEditor
from .cover_letter import AdaptiveCoverLetterGenerator
from .fatigue_monitor import FatigueMonitor
from .decision_rationale import DecisionRationale

# v3.1: New hybrid browser automation
from .hybrid_browser_automation import HybridBrowserAutomation, run_hybrid_automation

__all__ = [
    'JDProcessor',
    'MatchScorer', 
    'SurgicalCVEditor',
    'AdaptiveCoverLetterGenerator',
    'FatigueMonitor',
    'DecisionRationale',
    'HybridBrowserAutomation',
    'run_hybrid_automation',
]