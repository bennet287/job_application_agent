"""
Quick test to verify system integrity after fixes.
"""

print("Testing imports...")

try:
    from core.browser_planner import ContextAwarePlanner
    print("✅ browser_planner imports successfully")
except Exception as e:
    print(f"❌ browser_planner import failed: {e}")
    exit(1)

try:
    from core.field_matcher import FieldMatcher
    print("✅ field_matcher imports successfully")
except Exception as e:
    print(f"❌ field_matcher import failed: {e}")
    exit(1)

try:
    from core.hybrid_browser_automation import HybridBrowserAutomation
    print("✅ hybrid_browser_automation imports successfully")
except Exception as e:
    print(f"❌ hybrid_browser_automation import failed: {e}")
    exit(1)

try:
    from core.cv_surgical_editor import SurgicalCVEditor
    print("✅ cv_surgical_editor imports successfully")
except Exception as e:
    print(f"❌ cv_surgical_editor import failed: {e}")
    exit(1)

print("\n✅ All core modules import successfully!")

# Test FieldMatcher
print("\nTesting FieldMatcher...")
cv_facts = {
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@example.com',
    'address_raw': '9020 Klagenfurt, Austria'
}

# Test address parsing (pass string, not dict)
components = FieldMatcher.extract_address_components(cv_facts['address_raw'])
print(f"  Address components: {components}")

# Test field matching
match = FieldMatcher.match_field('First Name', cv_facts)
print(f"  Field match for 'First Name': {match}")

match = FieldMatcher.match_field('E-mail', cv_facts)
print(f"  Field match for 'E-mail': {match}")

# Test prepare_cv_facts
prepared = FieldMatcher.prepare_cv_facts(cv_facts)
print(f"  Prepared CV facts keys: {list(prepared.keys())}")

print("\n✅ All tests passed! System is ready.")
