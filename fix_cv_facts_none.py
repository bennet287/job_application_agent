# fix_cv_facts_none.py

with open('cli/commands.py', 'r') as f:
    content = f.read()

# Find where cv_facts is used and add safety check
old_code = '''    # Prepare user data FROM CV
    name_parts = cv_facts.get('name', '').split()
    user_data = {
        'first_name': name_parts[0] if name_parts else '',
        'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
        'email': cv_facts.get('email', ''),
        'phone': cv_facts.get('phone', ''),
    }'''

new_code = '''    # Prepare user data FROM CV
    # Safety check - ensure cv_facts is not None
    if cv_facts is None:
        cv_facts = {}
    
    name_parts = cv_facts.get('name', '').split()
    user_data = {
        'first_name': name_parts[0] if name_parts else '',
        'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
        'email': cv_facts.get('email', ''),
        'phone': cv_facts.get('phone', ''),
    }'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('cli/commands.py', 'w') as f:
        f.write(content)
    print("✓ Fixed cv_facts None check")
else:
    # Try to find and fix any cv_facts.get usage
    if "name_parts = cv_facts.get('name', '').split()" in content:
        content = content.replace(
            "name_parts = cv_facts.get('name', '').split()",
            "name_parts = cv_facts.get('name', '').split() if cv_facts else [].split()"
        )
        content = content.replace(
            "name_parts = cv_facts.get('name', '').split() if cv_facts else [].split()",
            "name_parts = cv_facts.get('name', '').split() if cv_facts else []"
        )
        with open('cli/commands.py', 'w') as f:
            f.write(content)
        print("✓ Fixed cv_facts usage")
    else:
        print("Could not find exact pattern - checking file manually needed")