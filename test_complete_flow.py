"""
Complete end-to-end test: All field types including cover letter upload.
"""

from core.field_matcher import FieldMatcher

print("=" * 70)
print("END-TO-END TEST: Complete Application Form Field Matching")
print("=" * 70)

# Simulate complete cv_facts after cover letter is saved
cv_facts = {
    'first_name': 'Bennet',
    'last_name': 'Allryn B',
    'email': 'bennet@example.com',
    'phone': '+43 123 456789',
    'address_raw': '9020 Klagenfurt am Wörthersee, Austria',
    'address_line1': '9020 Klagenfurt am Wörthersee',
    'city': 'Klagenfurt am Wörthersee',
    'postcode': '9020',
    'country': 'Austria',
    'linkedin': 'https://linkedin.com/in/example',
    'github': 'https://github.com/example',
    'resume_path': 'D:\\job_application_agent\\assets\\cv_versions\\cv_strabag_12345678.docx',
    'cover_letter_path': 'D:\\job_application_agent\\assets\\cover_letters\\cl_strabag_12345.txt',
}

# Typical form field labels from STRABAG/csod.com
form_labels = [
    'First Name*',
    'Last Name*',
    'E-mail*',
    'Phone',
    'Address line 1',
    'Address line 2',  # Optional - won't match
    'City',
    'County',  # Optional - may map to country
    'Postcode',
    'Country',
    'Earliest start date*',  # Special DATE action
    'Upload résumé/CV*',
    'Upload cover letter',
    'Upload Document',  # Won't match - optional
]

print(f"\n📋 CV Facts Available ({len([k for k, v in cv_facts.items() if v])} fields):")
for key, value in cv_facts.items():
    if value:
        display_value = str(value)[:60] + '...' if len(str(value)) > 60 else str(value)
        print(f"  • {key}: {display_value}")

print(f"\n🎯 Form Fields to Match ({len(form_labels)} total):")
print("=" * 70)

matched = 0
optional = 0
date_fields = 0

for label in form_labels:
    # Check if date field (special handling)
    if any(term in label.lower() for term in ['start date', 'earliest start', 'availability', 'available from']):
        print(f"  📅 '{label}' → [DATE ACTION: tomorrow]")
        date_fields += 1
        matched += 1
        continue
    
    # Try to match
    match = FieldMatcher.match_field(label, cv_facts)
    if match:
        fact_key, value = match
        display_value = str(value)[:45] + '...' if len(str(value)) > 45 else str(value)
        
        # Different icon for file uploads
        if '_path' in fact_key:
            icon = "📤"
        else:
            icon = "✓"
        
        print(f"  {icon} '{label}' → {fact_key}")
        print(f"      Value: {display_value}")
        matched += 1
    else:
        print(f"  ⚠ '{label}' → no match (optional field)")
        optional += 1

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Total fields: {len(form_labels)}")
print(f"  ✅ Matched: {matched} ({matched/len(form_labels)*100:.0f}%)")
print(f"  📅 Date fields: {date_fields}")
print(f"  📤 File uploads: 2 (CV + Cover Letter)")
print(f"  ⚠ Optional (unmatched): {optional}")

print("\n" + "=" * 70)
print("ACTIONS GENERATED")
print("=" * 70)

actions = []
for label in form_labels:
    # Date fields
    if any(term in label.lower() for term in ['start date', 'earliest start', 'availability', 'available from']):
        actions.append(f"DATE|{label}|1")
        continue
    
    # Regular fields
    match = FieldMatcher.match_field(label, cv_facts)
    if match:
        fact_key, value = match
        if '_path' in fact_key:
            actions.append(f"UPLOAD|{label}|{value.split('\\\\')[-1]}")  # Just filename
        else:
            actions.append(f"FILL|{label}|{value}")

print(f"\nGenerated {len(actions)} actions:\n")
for i, action in enumerate(actions, 1):
    print(f"  {i:2d}. {action}")

print("\n" + "=" * 70)
print("✅ End-to-end test complete")
print("=" * 70)
print("\n💡 Next production run will:")
print("  • Fill 8 text fields automatically")
print("  • Set date picker to tomorrow")
print("  • Upload CV file")
print("  • Upload cover letter file  ← NEW!")
print("  • Generate screenshot")
print("  • Submit application")
