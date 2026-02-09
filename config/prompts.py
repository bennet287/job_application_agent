PROMPT_VERSION = "2025.01.15-cv-centric"

JD_PARSE_PROMPT = """Extract structured job description data from the following text.
Return valid JSON only, no markdown formatting, no extra text.

Text:
{text}

Required JSON structure:
{{"company_name": "string or null", "role_title": "string or null", "location": "string or null", "salary_range": "string or null", "must_haves": ["list of required qualifications"], "nice_to_haves": ["list of preferred qualifications"], "tools_mentioned": ["specific tools/technologies"], "responsibilities": ["key job duties"], "red_flags": ["citizenship, clearance, language requirements, unrealistic expectations"]}}

Rules:
- Extract company name from header/footer if present
- Extract role title from job heading
- Be precise. If information is missing, use null or empty array.
- Distinguish true requirements from preferences.
- Flag visa, citizenship, mandatory certifications in red_flags.
- Return ONLY the JSON object, no other text."""

MATCH_SCORE_PROMPT = """Evaluate fit between candidate and job. Return ONLY valid JSON.

Candidate Profile:
{cv_summary}

Job Requirements:
Must-haves: {must_haves}
Nice-to-haves: {nice_to_haves}
Tools: {tools}

Scoring criteria (1-10 scale):
- 8-10: Strong match, most requirements met
- 6-7: Partial match, some gaps but learnable  
- 4-5: Significant gaps, stretch application
- 1-3: Poor fit, major unlearnable gaps

Return JSON only:
{{"score": 7, "confidence": "high", "methodology_fit": "strong", "domain_fit": "partial", "experience_gap": "manageable", "unlearnable_gaps": [], "leverage_points": ["specific strength 1", "specific strength 2"], "recommendation": "apply", "negotiation_leverage": ["relevant point 1", "relevant point 2"]}}

Be honest and critical. Use integer for score field."""

CV_BULLET_REWRITE_PROMPT = """Suggest MAX {max_changes} bullet rewrites for this CV to match the job.

Job Keywords: {keywords}
Must-haves: {must_haves}

Current CV Bullets:
{bullets}

Rules:
1. Only rephrase existing bullets, never invent new experience
2. Incorporate 1-2 job keywords naturally per bullet
3. Preserve ALL numbers and metrics exactly
4. Maintain similar length and tone
5. Return only bullets that need changing

Return JSON array:
[{{"original": "exact text from CV", "new": "rewritten text", "reason": "why this change helps"}}]"""
