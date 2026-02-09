# final_fix.py

# Read current match_scorer
with open('core/match_scorer.py', 'r') as f:
    content = f.read()

# Simple fix: replace the leverage_points line
old_line = '"leverage_points": [f"{exp} years experience", "Relevant degrees"],'
new_line = '"leverage_points": [f"{cv_facts.get(\'years_experience\', \'unknown\')} years experience", "Relevant degrees"],'

content = content.replace(old_line, new_line)

with open('core/match_scorer.py', 'w') as f:
    f.write(content)

print("✓ Fixed match_scorer.py")

# Also fix cli/commands.py to ensure cv_facts is passed
with open('cli/commands.py', 'r') as f:
    content = f.read()

# Make sure scorer is called with cv_facts
if 'result = scorer.evaluate(jd, force_effort)' in content:
    content = content.replace(
        'result = scorer.evaluate(jd, force_effort)',
        'result = scorer.evaluate(jd, cv_facts, force_effort)'
    )
    with open('cli/commands.py', 'w') as f:
        f.write(content)
    print("✓ Fixed cli/commands.py")
else:
    print("✓ cli/commands.py already correct")

print("\nRun: python main.py process \"URL\"")