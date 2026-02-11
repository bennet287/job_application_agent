import click
import json
import re
import pyperclip
from datetime import datetime
from pathlib import Path
from selenium.webdriver.common.by import By

from config import settings
from core.jd_processor import JDProcessor
from core.match_scorer import MatchScorer
from core.cv_surgical_editor import SurgicalCVEditor
from core.cover_letter import AdaptiveCoverLetterGenerator
from utils.llm_client import LLMClient
from database.models import init_db
from database.manager import DatabaseManager
from core.fatigue_monitor import FatigueMonitor
from core.decision_rationale import DecisionRationale
from core.hybrid_browser_automation import run_hybrid_automation


@click.group()
def cli():
    """Job Application Agent CLI - CV is the single source of truth"""
    pass


@cli.command()
def setup():
    """Initialize database, permissions, and git repo."""
    from database.migrations import MigrationManager
    from utils.permissions import PermissionManager
    from utils.git_tracker import init_cv_repo

    mg = MigrationManager(str(settings.DB_PATH))
    mg.apply_pending()

    pm = PermissionManager(str(settings.PROJECT_ROOT))
    pm.setup()

    init_cv_repo(settings.CV_VERSIONS_DIR)

    click.echo("Setup complete.")


@cli.command()
def status():
    """Check daily status."""
    fatigue = FatigueMonitor(str(settings.DB_PATH))
    can_proceed, fat_status = fatigue.check_and_enforce()

    click.echo(f"Status: {fat_status['state']}")
    click.echo(f"Reviewed: {fat_status['reviewed_today']}/{fat_status['daily_cap']}")
    if not can_proceed:
        click.echo(f"Resume: {fat_status.get('resume_time', 'Tomorrow')}")


def extract_cv_facts(cv_text: str) -> dict:
    """Extract ALL facts from CV including personal info."""
    facts = {
        'raw_text': cv_text,
        'name': None,
        'email': None,
        'phone': None,
        'years_experience': None,
        'degrees': [],
        'certifications': [],
        'skills': [],
        'companies': [],
        'roles': [],
        'key_achievements': [],
        'languages': [],
        'locations': []
    }

    # Name extraction - IMPROVED with better patterns
    lines = cv_text.split('\n')
    
    # Try first 15 lines for name (increased from 10)
    first_lines = '\n'.join(lines[:15])
    
    # Pattern 1: Standard capitalized name at start of line
    # Pattern 2: All caps name
    # Pattern 3: Name: label
    # Pattern 4: Name in header format (larger text often at top)
    name_patterns = [
        r'^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})\s*$',  # Bennet Allryn B
        r'^([A-Z][A-Z\s]+[A-Z])\s*$',  # BENNET ALLRYN B
        r'Name[:\s]+([^\n]+)',  # Name: Bennet Allryn B
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+)\s*\n',  # First Last at very start
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, first_lines, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            # Validate: reasonable length, not just a single word, not a common word
            if 3 < len(name) < 50 and ' ' in name and name.lower() not in ['curriculum vitae', 'resume', 'cv']:
                facts['name'] = name.title() if name.isupper() else name
                break

    # If still no name, try line 1 or 2 directly (common CV format)
    if not facts['name']:
        for i in range(min(3, len(lines))):
            line = lines[i].strip()
            # Skip empty lines and common headers
            if line and line.lower() not in ['curriculum vitae', 'resume', 'cv', 'personal information']:
                # Check if it looks like a name (2-3 words, capitalized)
                words = line.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                    facts['name'] = line
                    break

    # Email - IMPROVED pattern
    email_match = re.search(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
        cv_text
    )
    if email_match:
        facts['email'] = email_match.group(0).lower()

    # Phone - IMPROVED patterns
    phone_patterns = [
        r'(\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\+\d[\d\s\-]{7,20}',  # Simple international format
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, cv_text)
        if match:
            phone = match.group(0)
            phone = re.sub(r'\s+', ' ', phone).strip()
            if len(phone) >= 7:
                facts['phone'] = phone
                break

    # Experience years - IMPROVED PATTERNS
    exp_patterns = [
        r'(\d+)\+?\s*years?\s+(?:of\s+)?(?:relevant\s+)?(?:professional\s+)?(?:work\s+)?experience',
        r'experience[:\s]+(\d+)\+?\s*years?',
        r'(\d+)\s*years.*?experience',
        r'with\s+(\d+)\+?\s*years?',
        r'(?:over\s+)?(\d+)\+?\s*years?',
        r'(\d+)\+?\s*yrs?\s+(?:of\s+)?exp',  # Short form
    ]
    for pattern in exp_patterns:
        match = re.search(pattern, cv_text, re.IGNORECASE)
        if match:
            facts['years_experience'] = match.group(1)
            break

    # Degree extraction
    degree_mappings = [
        (r'\bMBA\b', 'MBA'),
        (r'\bMSc\b', 'MSc'),
        (r'\bM\.Sc\.', 'MSc'),
        (r'\bMCA\b', 'MCA'),
        (r'\bM\.C\.A\.', 'MCA'),
        (r'\bMA\b', 'MA'),
        (r'\bBSc\b', 'BSc'),
        (r'\bB\.Sc\.', 'BSc'),
        (r'\bBCA\b', 'BCA'),
        (r'\bBA\b', 'BA'),
        (r'\bPhD\b', 'PhD'),
        (r'\bPh\.D\.', 'PhD'),
    ]

    found_degrees = set()
    for pattern, degree_name in degree_mappings:
        if re.search(pattern, cv_text, re.IGNORECASE):
            normalized = degree_name.replace('.', '').upper()
            if normalized not in found_degrees:
                found_degrees.add(normalized)
                facts['degrees'].append(degree_name)

    # Achievements
    achievement_pattern = r'(?:•|\*|-)\s*([^.]*(?:\d+%|\d+\s*(?:million|k|thousand|x)|\$?\d+[KkMm])[^.]*\.)'
    for match in re.finditer(achievement_pattern, cv_text, re.IGNORECASE):
        achievement = match.group(1).strip()
        if len(achievement) > 15:
            facts['key_achievements'].append(achievement)

    facts['key_achievements'] = facts['key_achievements'][:3]
    facts['summary'] = cv_text[:500]

    return facts



def validate_against_cv(generated_text: str, cv_facts: dict) -> list:
    """Check generated text against CV facts."""
    violations = []

    if cv_facts is None:
        return violations

    # Check experience years
    if cv_facts.get('years_experience'):
        exp_pattern = r'(\d+)\+?\s*years?\s+(?:of\s+)?experience'
        for match in re.finditer(exp_pattern, generated_text, re.IGNORECASE):
            claimed_years = match.group(1)
            if claimed_years != cv_facts['years_experience']:
                violations.append(
                    f"EXPERIENCE MISMATCH: Claims {claimed_years} years, "
                    f"but CV states {cv_facts['years_experience']} years"
                )

    return violations


@cli.command()
@click.argument('input_data')
@click.option('--force-effort', type=click.Choice(['light', 'standard', 'deep']))
def process(input_data, force_effort):
    """Process job application with CV as ultimate authority."""
    start_time = datetime.now()

    # Fatigue check
    fatigue = FatigueMonitor(str(settings.DB_PATH))
    can_proceed, fat_status = fatigue.check_and_enforce()
    if not can_proceed:
        click.echo(f"STOP: {fat_status['message']}")
        return

    llm = LLMClient()
    Session = init_db(str(settings.DB_PATH))
    db = DatabaseManager(Session)

    # =====================================================================
    # STEP 1: LOAD CV - THE BIBLE
    # =====================================================================
    click.echo("="*70)
    click.echo("LOADING CV (SOURCE OF TRUTH)")
    click.echo("="*70)

    try:
        from docx import Document
        doc = Document(settings.ASSETS_DIR / 'master_cv.docx')
        cv_text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

        if len(cv_text) < 100:
            raise ValueError("CV appears empty or corrupted")

        click.echo(f"✓ CV loaded: {len(cv_text)} characters")

    except Exception as e:
        click.echo(f"✗ CRITICAL: Cannot read master_cv.docx: {e}")
        click.echo("Place your CV at: assets/master_cv.docx")
        return

        # Extract facts from CV
    cv_facts = extract_cv_facts(cv_text)

    # DEBUG: Show what we found
    click.echo(f"\nDEBUG CV Parsing:")
    click.echo(f"  Raw name found: '{cv_facts.get('name')}'")
    click.echo(f"  Email found: '{cv_facts.get('email')}'")
    click.echo(f"  Phone found: '{cv_facts.get('phone')}'")

    # CRITICAL: Prompt if name missing
    if not cv_facts.get('name'):
        click.echo("\n⚠️ Could not confidently detect your name from the CV.")
        click.echo("  This is needed for form auto-fill.")
        cv_facts['name'] = click.prompt(
            "Please enter your full name exactly as you want it used",
            type=str
        )
        click.echo(f"  ✓ Using: {cv_facts['name']}")

    # Display extracted facts
    click.echo("\nCV FACTS EXTRACTED:")
    if cv_facts.get('name'):
        click.echo(f"  • Name: {cv_facts['name']}")
    if cv_facts.get('email'):
        click.echo(f"  • Email: {cv_facts['email']}")
    if cv_facts.get('phone'):
        click.echo(f"  • Phone: {cv_facts['phone']}")
    if cv_facts.get('years_experience'):
        click.echo(f"  • Experience: {cv_facts['years_experience']} years")
    if cv_facts.get('degrees'):
        click.echo(f"  • Degrees: {', '.join(cv_facts['degrees'])}")
    if cv_facts.get('key_achievements'):
        click.echo(f"  • Key achievements: {len(cv_facts['key_achievements'])} with metrics")

    # =====================================================================
    # STEP 2: PARSE JOB DESCRIPTION
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("PROCESSING JOB DESCRIPTION")
    click.echo("="*70)

    processor = JDProcessor(llm)

    if input_data.startswith('pasted:'):
        jd = processor.process(input_data[7:])
    else:
        jd = processor.process(input_data)

    # =====================================================================
    # STEP 3: HUMAN VERIFICATION (USER IS GOD)
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("VERIFY REQUIREMENTS (USER CONFIRMATION REQUIRED)")
    click.echo("="*70)

    for i, req in enumerate(jd.get('must_haves', []), 1):
        click.echo(f"  {i}. {req}")

    action = click.prompt(
        "\n[c=confirm facts correct, e=edit, s=skip this job]", 
        type=click.Choice(['c', 'e', 's'])
    )

    if action == 's':
        click.echo("Skipped by user.")
        return
    elif action == 'e':
        idx = click.prompt("Edit which requirement (number)", type=int) - 1
        new_text = click.prompt("Corrected text")
        jd['must_haves'][idx] = new_text
        click.echo("Updated. CV facts remain unchanged.")

    jd['human_verified'] = True

    # =====================================================================
    # STEP 4: SCORE MATCH (CV-BACKED ANALYSIS)
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("SCORING MATCH (BASED ON CV FACTS ONLY)")
    click.echo("="*70)

    scorer = MatchScorer(llm, cv_text, settings.EXPLORATION_RATE)
    result = scorer.evaluate(jd, cv_facts, force_effort)

    if result['reject_reason']:
        click.echo(f"REJECTED: {result['reject_reason']}")
        return

    click.echo(f"\nScore: {result['score']}/10")
    click.echo(f"Confidence: {result['analysis'].get('confidence', 'unknown')}")
    click.echo(f"Effort: {result['effort_class']}")

    # Show what the score is based on
    click.echo("\nBased on CV facts:")
    for point in result['analysis'].get('leverage_points', [])[:3]:
        click.echo(f"  ✓ {point}")

    if not click.confirm("\nProceed with application?"):
        click.echo("Aborted by user.")
        return

    # =====================================================================
    # STEP 5: CV TAILORING (SURGICAL, FACT-PRESERVING)
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("CV TAILORING (PRESERVING ALL FACTS)")
    click.echo("="*70)

    editor = SurgicalCVEditor(settings.ASSETS_DIR / 'master_cv.docx', llm)
    cv_result = editor.create_tailored_cv(
        company=jd.get('company_name', 'Unknown_Company'),
        role=jd.get('role_title', 'Unknown_Role'),
        jd_data=jd,
        analysis=result['analysis'],
        cv_facts=cv_facts,
        max_changes=result['effort_config']['max_bullet_changes']
    )

    if cv_result['changes']:
        click.echo(f"\nProposed changes: {len(cv_result['changes'])}")
        for change in cv_result['changes']:
            click.echo(f"\n  Original: {change['original'][:60]}...")
            click.echo(f"  New:      {change['new'][:60]}...")
            click.echo(f"  Reason:   {change['reason']}")

        if not click.confirm("\nApprove these changes?"):
            cv_result = {
                'pdf': str(settings.ASSETS_DIR / 'master_cv.pdf'),
                'changes': [],
                'hash': 'master'
            }
            click.echo("Using original CV.")
    else:
        click.echo("No changes needed.")

    # =====================================================================
    # STEP 6: COVER LETTER (CV-FACTS ONLY, USER APPROVES)
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("COVER LETTER GENERATION (CV FACTS ONLY)")
    click.echo("="*70)

    cl_gen = AdaptiveCoverLetterGenerator(llm)

    # Generate with strict CV fact enforcement
    variants = cl_gen.generate_variants(jd, result['analysis'], cv_facts)

    # Validate each variant against CV
    click.echo("\nValidating against CV facts...")
    for name, text in variants.items():
        violations = validate_against_cv(text, cv_facts)
        if violations:
            click.echo(f"  ⚠ {name}: {len(violations)} issues found")
            for v in violations[:2]:
                click.echo(f"    - {v}")
        else:
            click.echo(f"  ✓ {name}: All facts verified")

    # Show variants
    click.echo("\n--- GENERATED VARIANTS ---")
    for name, text in variants.items():
        click.echo(f"\n[{name.upper()}] {len(text)} chars")
        # Show first 2 lines
        lines = text.split('\n')[:2]
        for line in lines:
            preview = line[:80] + "..." if len(line) > 80 else line
            click.echo(f"  {preview}")

    # User selects
    choice = click.prompt(
        "\nSelect variant to use", 
        type=click.Choice(['full', 'compress', 'truncate']),
        default='full'
    )

    cover_letter = variants.get(choice, variants['full'])

    # Final validation check
    final_violations = validate_against_cv(cover_letter, cv_facts)
    if final_violations:
        click.echo("\n⚠ WARNING: Issues detected in selected variant:")
        for v in final_violations:
            click.echo(f"  - {v}")
        click.echo("Please edit to fix these issues.")

    # Optional user edit
    if click.confirm("Edit this cover letter?"):
        cover_letter = click.prompt(
            "Enter corrected cover letter", 
            type=str, 
            default=cover_letter
        )

    # Display final with clear marking
    click.echo(f"\n{'='*70}")
    click.echo("FINAL COVER LETTER (VERIFY BEFORE USE)")
    click.echo(f"{'='*70}")
    click.echo(cover_letter)
    click.echo(f"{'='*70}")
    click.echo(f"Length: {len(cover_letter)} characters")

    # Final user confirmation
    if not click.confirm("\nIs this cover letter accurate and ready to use?"):
        click.echo("Application cancelled by user.")
        return

        # =====================================================================
    # Step 7: Browser Automation (AI-Powered or Assist)
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("BROWSER AUTOMATION (AI-Powered)")
    click.echo("="*70)

    # Prepare user data FROM CV
    cv_facts = cv_facts or {}
    cv_facts.setdefault('name', '')
    cv_facts.setdefault('email', '')
    cv_facts.setdefault('phone', '')

    name_parts = (cv_facts.get('name') or '').split()
    user_data = {
        'first_name': name_parts[0] if name_parts else '',
        'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
        'email': cv_facts.get('email', ''),
        'phone': cv_facts.get('phone', ''),
    }

    click.echo(f"\nAuto-fill data from CV:")
    click.echo(f"  Name: {user_data['first_name']} {user_data['last_name']}")
    click.echo(f"  Email: {user_data['email'] or 'Not found'}")
    click.echo(f"  Phone: {user_data['phone'] or 'Not found'}")

    url = jd.get('source_url', '')
    if not url:
        click.echo("No URL provided - manual mode only")
        auto_level = 'manual'
    else:
        # Check if AI browser is available
        ai_available = (
            settings.LLM_BROWSER_PROVIDER != 'ollama' and
            bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)
        )
        
        default_level = 'ai' if ai_available else 'assist'
        
        auto_level = click.prompt(
            "Automation level",
            type=click.Choice(['ai', 'assist', 'manual']),
            default=default_level
        )

    # In the AI automation section of commands.py:

if auto_level == 'ai':
    try:
        from core.hybrid_browser_automation import run_hybrid_automation

        click.echo("\n  🤖 Starting Hybrid Browser Automation...")
        click.echo(f"  🧠 Planner: Context-aware | Executor: Selenium")
        
        # Get or create database session and application ID
        # This assumes you have application_id from earlier in the process
        result = run_hybrid_automation(
            url=url,
            user_data=user_data,
            cover_letter=cover_letter,
            cv_path=cv_result['pdf'],
            session=db.session if 'db' in locals() else None,  # Pass session
            application_id=app_id  # Pass application ID from earlier step
        )

        if result.success:
            click.echo("\n  ✅ Automation completed")
            click.echo(f"  🔢 Actions: {len(result.actions_taken)}")
            if result.screenshot_path:
                click.echo(f"  📸 Screenshot: {result.screenshot_path}")
        else:
            click.echo("\n  ⚠️  Automation incomplete")
            auto_level = 'assist'

    except Exception as e:
        click.echo(f"\n  ❌ Error: {e}")
        auto_level = 'assist'

    if auto_level == 'assist':
        import webbrowser
        import pyperclip

        webbrowser.open(url)
        pyperclip.copy(cover_letter)

        click.echo(f"\n  ✓ Opened {url}")
        click.echo("  ✓ Cover letter copied to clipboard")
        click.echo(f"  ✓ CV ready: {cv_result['pdf']}")
        click.echo("\n  Please fill the form manually")
        click.pause("Press any key when done...")

    else:  # manual
        click.echo(f"\n  URL: {url}")
        click.echo("  Manual mode - copy cover letter from above")
        click.pause("Press any key when done...")   

    # =====================================================================
    # STEP 8: LOG APPLICATION
    # =====================================================================
    company_name = jd.get('company_name') or 'Unknown_Company'
    role_title = jd.get('role_title') or 'Unknown_Role'

    app_id = db.create_application({
        'company_slug': slugify(company_name),
        'company_name': company_name,
        'role_title': role_title,
        'match_score': result['score'],
        'cv_file_path': cv_result['pdf'],
        'cover_letter_constraint_type': 'none',
        'cover_letter_length': len(cover_letter),
        'llm_model': settings.LLM_MODEL,
        'date_processed': datetime.now(),
        'process_latency_seconds': int((datetime.now() - start_time).total_seconds())
    })

    # Save rationale
    rationale_mgr = DecisionRationale(settings.ASSETS_DIR)
    rationale_mgr.create(app_id, slugify(company_name), result['score'], result['analysis'], jd)

    click.echo(f"\n✓ Application {app_id} logged successfully.")


def slugify(text: str) -> str:
    if not text:
        return 'unknown'
    return re.sub(r'[^\w]+', '_', text.lower()).strip('_')[:50]


if __name__ == '__main__':
    cli()