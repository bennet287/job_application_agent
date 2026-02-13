"""
Quick test to verify address and date field matching.
"""

from core.field_matcher import FieldMatcher
from core.action_protocol import Action

# Test 1: Verify address patterns match form labels
print("=" * 60)
print("TEST 1: Address Field Matching")
print("=" * 60)

cv_facts = {
    'address_line1': '9020 Klagenfurt am Wörthersee',
    'city': 'Klagenfurt am Wörthersee',
    'postcode': '9020',
    'country': 'Austria'
}

form_labels = [
    'Address line 1',
    'City',
    'Postcode',
    'Country',
    'County',  # should not match
]

print(f"\nCV Facts: {cv_facts}\n")
print("Form Label Matching:")
for label in form_labels:
    match = FieldMatcher.match_field(label, cv_facts)
    if match:
        fact_key, value = match
        print(f"  ✓ '{label}' → {fact_key} = '{value}'")
    else:
        print(f"  ⚠ '{label}' → no match")

# Test 2: Verify date field detection
print("\n" + "=" * 60)
print("TEST 2: Date Field Detection")
print("=" * 60)

date_labels = [
    'Earliest start date*',
    'Start date',
    'Available from',
    'Availability',
]

print("\nDate Field Detection:")
for label in date_labels:
    # Check if label contains date keywords
    is_date = any(term in label.lower() for term in ['start date', 'earliest start', 'availability', 'available from'])
    print(f"  {'✓' if is_date else '⚠'} '{label}' → {'DATE field' if is_date else 'not detected'}")

# Test 3: Verify DATE action parsing
print("\n" + "=" * 60)
print("TEST 3: DATE Action Parsing")
print("=" * 60)

date_action = Action.parse("DATE|Earliest start date|1")
if date_action:
    method, kwargs = date_action.to_executor_call()
    print(f"\nAction: DATE|Earliest start date|1")
    print(f"  Type: {date_action.type}")
    print(f"  Params: {date_action.params}")
    print(f"  Executor call: {method}({kwargs})")
else:
    print("  ❌ Failed to parse DATE action")

print("\n" + "=" * 60)
print("✅ All tests complete")
print("=" * 60)
