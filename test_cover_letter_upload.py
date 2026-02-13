"""
Test cover letter upload path handling.
"""

from core.field_matcher import FieldMatcher

print("=" * 60)
print("TEST: Cover Letter Upload Path Handling")
print("=" * 60)

# Simulate cv_facts with cover letter path
cv_facts = {
    'first_name': 'Bennet',
    'last_name': 'Allryn B',
    'email': 'bennet@example.com',
    'resume_path': 'D:\\job_application_agent\\assets\\cv_versions\\cv_test.docx',
    'cover_letter_path': 'D:\\job_application_agent\\assets\\cover_letters\\cl_strabag_12345.txt',
}

# Test form labels
form_labels = [
    'Upload résumé/CV*',
    'Upload cover letter',
    'Upload Cover Letter',
    'Cover letter',
    'Anschreiben',
]

print("\nMatching cover letter upload labels:")
for label in form_labels:
    match = FieldMatcher.match_field(label, cv_facts)
    if match:
        fact_key, value = match
        print(f"  ✓ '{label}' → {fact_key}")
        print(f"      Path: {value}")
    else:
        print(f"  ⚠ '{label}' → no match")

# Test pattern matching
print("\n" + "=" * 60)
print("TEST: Pattern Coverage")
print("=" * 60)

patterns = FieldMatcher.FIELD_PATTERNS.get('cover_letter', [])
print(f"\nCover letter patterns ({len(patterns)}):")
for pattern in patterns:
    print(f"  • '{pattern}'")

print("\n" + "=" * 60)
print("✅ Test complete")
print("=" * 60)
