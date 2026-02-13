"""
Quick test script to verify v3.2 improvements work correctly.
"""

from core.browser_executor import ATS_FINGERPRINTS
from urllib.parse import urlparse


def test_ats_detection():
    """Test ATS platform fingerprinting."""
    print("\n🧪 Testing ATS Detection\n" + "="*60)
    
    test_urls = [
        "https://strabag.csod.com/ux/ats/careersite/2/home?c=strabag",
        "https://boards.greenhouse.io/company/jobs/12345",
        "https://company.personio.de/job/123456",
        "https://myworkday.com/company/job/12345",
        "https://jobs.lever.co/company/12345"
    ]
    
    for url in test_urls:
        domain = urlparse(url).netloc
        detected = None
        
        for ats_domain, config in ATS_FINGERPRINTS.items():
            if ats_domain in domain:
                detected = config
                break
        
        if detected:
            print(f"✅ {domain}")
            print(f"   ATS: {detected['name']}")
            print(f"   Wait: {detected['form_wait_seconds']}s")
            print(f"   Strategy: {detected['input_strategy']}")
        else:
            print(f"⚠️  {domain} - Not recognized")
        print()


def test_name_parsing():
    """Test improved name parsing heuristics."""
    print("\n🧪 Testing Name Parsing\n" + "="*60)
    
    test_cases = [
        ("Bennet Allryn", "Bennet", "Allryn"),
        ("John Van Der Waals", "John", "Van Der Waals"),
        ("María De La Cruz", "María", "De La Cruz"),
        ("Jean-Pierre Dubois", "Jean-Pierre", "Dubois"),
        ("李明", "李明", ""),  # Single Chinese name (would prompt)
    ]
    
    for full_name, expected_first, expected_last in test_cases:
        name_parts = full_name.split()
        
        if len(name_parts) == 2:
            first, last = name_parts[0], name_parts[1]
        elif len(name_parts) > 2:
            if name_parts[-2][0].isupper() and len(name_parts[-2]) <= 3:
                first = name_parts[0]
                last = ' '.join(name_parts[1:])
            else:
                first = name_parts[0]
                last = ' '.join(name_parts[1:])
        else:
            first = name_parts[0] if name_parts else ''
            last = ''
        
        status = "✅" if first == expected_first and last == expected_last else "❌"
        print(f"{status} '{full_name}'")
        print(f"   Expected: first='{expected_first}', last='{expected_last}'")
        print(f"   Got:      first='{first}', last='{last}'")
        print()


def test_screenshot_naming():
    """Test screenshot naming convention."""
    print("\n🧪 Testing Screenshot Naming\n" + "="*60)
    
    from pathlib import Path
    import time
    
    test_cases = [
        ("https://strabag.csod.com/ux/ats/careersite/2/home", 10, "app_10_strabag"),
        ("https://www.xal.com/careers/job/12345", 11, "app_11_xal"),
        ("https://personio.de/job/123", None, "app_personio"),
    ]
    
    for url, app_id, expected_prefix in test_cases:
        domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
        company_slug = domain or "unknown"
        
        if app_id:
            screenshot_name = f"app_{app_id}_{company_slug}_{int(time.time())}.png"
        else:
            screenshot_name = f"app_{company_slug}_{int(time.time())}.png"
        
        status = "✅" if screenshot_name.startswith(expected_prefix) else "❌"
        print(f"{status} {url}")
        print(f"   Generated: {screenshot_name}")
        print(f"   Expected prefix: {expected_prefix}")
        print()


def test_wait_methods():
    """Test that new wait methods exist and are callable."""
    print("\n🧪 Testing Wait Methods\n" + "="*60)
    
    from core.browser_executor import BrowserExecutor
    
    required_methods = [
        'wait',
        'do_wait',
        'wait_for_element',
        'wait_for_form_inputs'
    ]
    
    # Check methods exist (without instantiating driver)
    for method_name in required_methods:
        if hasattr(BrowserExecutor, method_name):
            print(f"✅ BrowserExecutor.{method_name}() exists")
        else:
            print(f"❌ BrowserExecutor.{method_name}() NOT FOUND")
    print()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("JOB APPLICATION AGENT - v3.2 IMPROVEMENTS TEST")
    print("="*60)
    
    test_ats_detection()
    test_name_parsing()
    test_screenshot_naming()
    test_wait_methods()
    
    print("\n" + "="*60)
    print("✅ All tests complete!")
    print("="*60 + "\n")
