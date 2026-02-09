import click
import json
import re
import pyperclip
from datetime import datetime
from pathlib import Path
from selenium.webdriver.common.by import By

from config import settings
from core import JDProcessor, MatchScorer, SurgicalCVEditor
from core import AdaptiveCoverLetterGenerator
from core import DecisionRationale, ConservativeFormFiller, FatigueMonitor
from database import init_db, DatabaseManager
from database.migrations import MigrationManager
from utils import LLMClient


@click.group()
def cli():
    """Job Application Agent CLI - CV is the single source of truth"""
    pass


@cli.command()
def setup():
    """Initialize database, permissions, and git repo."""
    mg = MigrationManager(str(settings.DB_PATH))
    mg.apply_pending()
    
    from utils.permissions import PermissionManager
    pm = PermissionManager(str(settings.PROJECT_ROOT))
    pm.setup()
    
    from utils.git_tracker import init_cv_repo
    init_cv_repo(settings.CV_VERSIONS_DIR)
    
    click.echo("Setup complete.")


@cli.command()
def status():
    """Check daily status."""
    fatigue = FatigueMonitor(str(settings.DB_PATH))
    can_proceed, fat_status = fatigue.check_and_enforce()
    
    click.echo(f"\nStatus: {fat_status['state']}")
    click.echo(f"Reviewed: {fat_status['reviewed_today']}/{fat_status['daily_cap']}")
    if not can_proceed:
        click.echo(f"Resume: {fat_status.get('resume_time', 'Tomorrow')}")

def extract_cv_facts(cv_text: str) -> dict:
    """Extract ALL facts from CV including personal info."""
    import re
    from datetime import datetime
    
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
    
    # Name from first lines
    lines = cv_text.split('\n')
    first_lines = '\n'.join(lines[:10])
    name_patterns = [
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*$',
        r'^([A-Z][A-Z\s]+[A-Z])\s*$',
        r'Name[:\s]+([^\n]+)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, first_lines, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if len(name) > 3 and len(name) < 50:
                facts['name'] = name.title()
                break
    
    # Email
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', cv_text)
    if email_match:
        facts['email'] = email_match.group(0)
    
    # Phone
    phone_patterns = [
        r'(\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, cv_text)
        if match:
            phone = match.group(0)
            phone = re.sub(r'\s+', ' ', phone).strip()
            if len(phone) >= 7:
                facts['phone'] = phone
                break
    
    # Experience years
    exp_patterns = [
        r'(\d+)\+?\s*years?\s+(?:of\s+)?(?:relevant\s+)?(?:professional\s+)?(?:work\s+)?experience',
        r'experience[:\s]+(\d+)\+?\s*years?',
    ]
    for pattern in exp_patterns:
        match = re.search(pattern, cv_text, re.IGNORECASE)
        if match:
            facts['years_experience'] = match.group(1)
            break

    # Degree extraction
    degree_mappings = [
        (r'\bMBA\b', 'MBA'),
        (r'\bMSc\b', 'MSc'),  # Will match MSc and M.Sc
        (r'\bMCA\b', 'MCA'),
        (r'\bMA\b', 'MA'),
        (r'\bBSc\b', 'BSc'),
        (r'\bBCA\b', 'BCA'),
        (r'\bBA\b', 'BA'),
        (r'\bPhD\b', 'PhD'),
    ]

    found_degrees = set()
    for pattern, degree_name in degree_mappings:
        if re.search(pattern, cv_text, re.IGNORECASE):
            # Normalize: remove dots, uppercase
            normalized = degree_name.replace('.', '').upper()
            if normalized not in found_degrees:
                found_degrees.add(normalized)
                facts['degrees'].append(degree_name)  # Keep original format

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
    """
    Check generated text against CV facts.
    Return list of violations.
    """
    violations = []
    
    # Check experience years
    if cv_facts['years_experience']:
        # Look for different experience claim
        exp_pattern = r'(\d+)\+?\s*years?\s+(?:of\s+)?experience'
        for match in re.finditer(exp_pattern, generated_text, re.IGNORECASE):
            claimed_years = match.group(1)
            if claimed_years != cv_facts['years_experience']:
                violations.append(
                    f"EXPERIENCE MISMATCH: Claims {claimed_years} years, "
                    f"but CV states {cv_facts['years_experience']} years"
                )
    
    # Check for invented companies
    cv_companies_lower = [c.lower() for c in cv_facts['companies']]
    # Common false positives to ignore
    common_words = ['the', 'a', 'an', 'this', 'that', 'company', 'organization', 'firm']
    
    # Look for company mentions not in CV
    potential_companies = re.findall(r'(?:at|with|for)\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\s+and|\s+where)', generated_text)
    for company in potential_companies:
        company_clean = company.strip().lower()
        if (len(company_clean) > 3 and 
            company_clean not in common_words and
            not any(company_clean in cv_c or cv_c in company_clean for cv_c in cv_companies_lower)):
            violations.append(f"POSSIBLE INVENTION: Mentions '{company}' not found in CV")
    
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
    
    # Around where JD is processed
    if hasattr(process, '_running'):
        return
    process._running = True
    click.echo("\n" + "="*70)
    click.echo("PROCESSING JOB DESCRIPTION")
    click.echo("="*70)
    
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
    # Step 7: Browser Automation with CV-extracted data
    # =====================================================================
    click.echo("\n" + "="*70)
    click.echo("BROWSER AUTOMATION")
    click.echo("="*70)
    
    # Prepare user data FROM CV
    # Safety check - ensure cv_facts is not None
    if cv_facts is None:
        cv_facts = {}
    
    if cv_facts is None:
        cv_facts = {'name': '', 'email': '', 'phone': ''}
    name_parts = cv_facts.get('name', '').split()
    user_data = {
        'first_name': name_parts[0] if name_parts else '',
        'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
        'email': cv_facts.get('email', ''),
        'phone': cv_facts.get('phone', ''),
    }
    
    click.echo(f"\nAuto-fill data from CV:")
    click.echo(f"  Name: {user_data['first_name']} {user_data['last_name']}")
    click.echo(f"  Email: {user_data['email'] or 'Not found in CV'}")
    click.echo(f"  Phone: {user_data['phone'] or 'Not found in CV'}")
    
    url = jd.get('source_url', '')
    if not url:
        click.echo("No URL provided - manual mode only")
        auto_level = 'manual'
    else:
        auto_level = click.prompt(
            "Automation level",
            type=click.Choice(['full', 'assist', 'manual']),
            default='assist'
        )
    
    if auto_level == 'full':
        from core.browser_automation import auto_fill_application
        automation = auto_fill_application(url, user_data, cover_letter, cv_result['pdf'])
        
        if automation:
            if click.confirm("Submit automatically?"):
                try:
                    # Find and click submit
                    submit = automation.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
                    submit.click()
                    click.echo("✓ Submitted!")
                except:
                    click.echo("⚠ Could not find submit button - please click manually")
            
            click.pause("Press any key to close browser...")
            automation.close()
    
    elif auto_level == 'assist':
        import webbrowser
        webbrowser.open(url)
        pyperclip.copy(cover_letter)
        click.echo(f"✓ Opened {url}")
        click.echo("✓ Cover letter copied to clipboard")
        click.echo(f"CV ready: {cv_result['pdf']}")
        click.pause("Press any key when done...")
    
    else:
        click.echo(f"URL: {url}")
        click.echo("Manual mode - copy cover letter above")
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
    '''Convert text to slug, handling None values.'''
    if not text:
        return 'unknown'
    return re.sub(r'[^\w]+', '_', text.lower()).strip('_')[:50]


if __name__ == '__main__':
    cli()