"""
Test to verify user_data now includes address fields.
"""

# Simulate what commands.py does
cv_facts = {
    'name': 'Bennet Allryn B',
    'email': 'bennet@example.com',
    'phone': '+43 123 456789',
    'address_raw': '9020 Klagenfurt am Wörthersee, Austria',
    'address_line1': '9020 Klagenfurt am Wörthersee',
    'city': 'Klagenfurt am Wörthersee',
    'postcode': '9020',
    'country': 'Austria',
    'linkedin': 'https://linkedin.com/in/example',
    'github': 'https://github.com/example',
}

# Extract name parts
name = cv_facts.get('name', '')
name_parts = name.split()
first_name = name_parts[0] if name_parts else ''
last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

# Build user_data (as commands.py does now)
user_data = {
    'first_name': first_name,
    'last_name': last_name,
    'email': cv_facts.get('email', ''),
    'phone': cv_facts.get('phone', ''),
    'address_raw': cv_facts.get('address_raw', ''),
    'address_line1': cv_facts.get('address_line1', ''),
    'city': cv_facts.get('city', ''),
    'postcode': cv_facts.get('postcode', ''),
    'country': cv_facts.get('country', ''),
    'linkedin': cv_facts.get('linkedin', ''),
    'github': cv_facts.get('github', ''),
    'website': cv_facts.get('website', ''),
}

print("=" * 60)
print("TEST: user_data Population")
print("=" * 60)
print("\nuser_data contents:")
for key, value in user_data.items():
    if value:
        print(f"  ✓ {key}: {value}")
    else:
        print(f"  ⚠ {key}: (empty)")

# Now simulate what hybrid_browser_automation does
from core.field_matcher import FieldMatcher

cv_facts_raw = {
    'first_name': user_data.get('first_name'),
    'last_name': user_data.get('last_name'),
    'email': user_data.get('email'),
    'phone': user_data.get('phone'),
    'address_raw': user_data.get('address_raw'),
    'address_line1': user_data.get('address_line1'),
    'city': user_data.get('city'),
    'postcode': user_data.get('postcode'),
    'country': user_data.get('country'),
    'linkedin': user_data.get('linkedin'),
    'github': user_data.get('github'),
    'website': user_data.get('website'),
    'resume_path': 'cv_test.docx'
}

cv_facts_prepared = FieldMatcher.prepare_cv_facts(cv_facts_raw)

print("\n" + "=" * 60)
print("TEST: Prepared CV Facts")
print("=" * 60)
print("\nPrepared cv_facts contents:")
for key, value in cv_facts_prepared.items():
    if value:
        print(f"  ✓ {key}: {value}")

# Test field matching
print("\n" + "=" * 60)
print("TEST: Field Matching")
print("=" * 60)

form_labels = [
    'First Name*',
    'Last Name*',
    'E-mail*',
    'Phone',
    'Address line 1',
    'City',
    'Postcode',
    'Country',
]

print("\nMatching form labels to CV facts:")
for label in form_labels:
    match = FieldMatcher.match_field(label, cv_facts_prepared)
    if match:
        fact_key, value = match
        print(f"  ✓ '{label}' → {fact_key} = '{value}'")
    else:
        print(f"  ❌ '{label}' → no match")

print("\n" + "=" * 60)
print("✅ Test complete")
print("=" * 60)
