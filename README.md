I'll create a comprehensive README.md file for your project and help you add it to git.

## Create README.md

Save this as `README.md` in your project root:

```markdown
# Job Application Agent v2.1

> **CV is the Bible. User is God.**  
> An automated job application system that extracts facts from your CV and generates tailored applications with human oversight at every step.

---

## 🎯 Philosophy

- **CV = Source of Truth**: All personal info, experience, and achievements extracted directly from your CV
- **No Hallucination**: Cover letters use only CV facts, validated before display
- **Human Control**: User confirms/edits at every step (JD facts, score, CV changes, cover letter)
- **Audit Trail**: All decisions logged with rationale

---

## ✨ Features

| Component | Status | Description |
|-----------|--------|-------------|
| **CV Parser** | ✅ Working | Extracts name, email, phone, degrees, experience, achievements from `master_cv.docx` |
| **JD Processor** | ✅ Working | Scrapes job URLs, extracts company, role, requirements using LLM |
| **Match Scorer** | ✅ Working | Scores fit 1-10 based on CV facts vs job requirements |
| **Cover Letter Generator** | ✅ Working | Generates 3 variants (full/compress/truncate) with CV facts only |
| **CV Tailoring** | ⚠️ Basic | Returns master CV (full surgical editing disabled for stability) |
| **Browser Automation** | ⚠️ Partial | Opens browser, pre-fills data where possible |
| **Database Logging** | ✅ Working | Logs all applications to SQLite with full audit trail |

---

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Setup
```bash
# Initialize database and permissions
python main.py setup

# Place your CV
cp your_cv.docx assets/master_cv.docx
```

### Run
```bash
# Process a job URL
python main.py process "https://example.com/job-posting"

# Or paste JD text
python main.py process "pasted:Job title... Requirements..."
```

---

## 📋 Workflow

1. **Load CV** → Extract facts (name, email, phone, exp, degrees, achievements)
2. **Scrape JD** → Parse requirements, company, role
3. **User Verification** → Confirm/edit extracted JD facts
4. **Score Match** → Rate fit 1-10 (CV vs JD requirements)
5. **User Approval** → Confirm score and proceed
6. **Generate Cover Letter** → Create variants using CV facts only
7. **User Selection** → Choose/edit final cover letter
8. **Browser Automation** → Open application form, pre-fill data
9. **Manual Submit** → User reviews and clicks submit
10. **Log Application** → Record to database with full rationale

---

## 🏗️ Architecture

```
job_application_agent/
├── config/
│   ├── settings.py          # API keys, paths, operational limits
│   └── prompts.py           # Versioned LLM prompts (escaped JSON)
├── core/
│   ├── jd_processor.py      # URL scraping + JD parsing with fallback
│   ├── match_scorer.py      # Experience/degree-based scoring
│   ├── cover_letter.py      # CV-fact-based generation with validation
│   ├── cv_surgical_editor.py # CV versioning and basic tailoring
│   └── form_filler.py       # Browser automation prep
├── cli/
│   └── commands.py          # Interactive workflow with user gates
├── utils/
│   ├── llm_client.py        # Ollama/OpenAI/Gemini/DeepSeek support
│   └── permissions.py       # File permission enforcement
├── assets/
│   ├── master_cv.docx       # YOUR CV - source of truth (600 permissions)
│   ├── cv_versions/         # Git-tracked tailored CVs
│   ├── cover_letters/       # Generated cover letters
│   └── decisions/           # Immutable rationale logs
└── applications.db          # SQLite database (600 permissions)
```

---

## ⚙️ Configuration

Edit `config/settings.py`:

```python
# LLM Provider (choose one)
LLM_PROVIDER = 'ollama'  # or 'gemini', 'openai', 'deepseek'
LLM_MODEL = 'llama3.1:8b'

# Operational Limits
DAILY_APPLICATION_CAP = 5
MIN_HOURS_BETWEEN_APPS = 0  # Set to 0.5 for production
```

---

## 🛡️ Safety Features

- **Fatigue Monitor**: Daily cap + time spacing between applications
- **Permission Enforcement**: Sensitive files (CV, DB) at 600, directories at 700
- **Git Versioning**: Every CV change committed to `cv-history` branch
- **Immutable Logs**: Decision rationales cannot be altered after creation
- **Validation**: Cover letters checked against CV facts before display

---

## 📝 Example Output

```
======================================================================
LOADING CV (SOURCE OF TRUTH)
======================================================================
✓ CV loaded: 6086 characters

CV FACTS EXTRACTED:
  • Name: Bennet Allryn B
  • Email: bennetallryn287@gmail.com
  • Phone: +4366499459995
  • Experience: 2 years
  • Degrees: MBA, MSc
  • Key achievements: 3 with metrics

======================================================================
PROCESSING JOB DESCRIPTION
======================================================================

Extracted:
  Company: XAL
  Role: Junior Project Manager (m/w/d)
  Must-haves: 6 requirements

[c=confirm, e=edit, s=skip]: c

Score: 6/10
Confidence: medium
Effort: standard

Proceed? [y/N]: y
...
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| `SyntaxError` in prompts | JSON braces must be escaped: `{{` and `}}` |
| Ollama timeout | Increase timeout in `llm_client.py` or reduce JD text |
| "No changes needed" for CV | Surgical editing disabled; using master CV |
| Browser doesn't fill | Automation partial; manual fill required |

---

## 📊 Database Schema

```sql
applications (
    id INTEGER PRIMARY KEY,
    company_name TEXT,
    role_title TEXT,
    match_score INTEGER,
    cv_file_path TEXT,
    cover_letter_length INTEGER,
    llm_model TEXT,
    date_processed TIMESTAMP,
    process_latency_seconds INTEGER
)
```

---

## 🤝 Contributing

This is a personal automation tool. Modify for your workflow:

- Adjust prompts in `config/prompts.py`
- Change scoring weights in `core/match_scorer.py`
- Add new LLM providers in `utils/llm_client.py`

---

## 📜 License

Private use only. Do not use for spam or automated abuse of job platforms.

---

## 🙏 Acknowledgments

Built with:
- [Click](https://click.palletsprojects.com/) for CLI
- [python-docx](https://python-docx.readthedocs.io/) for CV processing
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for web scraping
- [Ollama](https://ollama.com/) for local LLM inference
