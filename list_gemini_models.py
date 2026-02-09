"""
List available Gemini models for your API key
This helps identify the correct model names to use
"""

import requests
from config import settings

def list_gemini_models():
    """List all available Gemini models."""
    
    print("=" * 70)
    print("CHECKING AVAILABLE GEMINI MODELS")
    print("=" * 70)
    print()
    
    if not settings.GEMINI_API_KEY:
        print("✗ Error: GEMINI_API_KEY not set")
        return
    
    print(f"API Key: {settings.GEMINI_API_KEY[:20]}...")
    print()
    print("Fetching available models...")
    print()
    
    try:
        # List models endpoint
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        
        response = requests.get(
            f"{url}?key={settings.GEMINI_API_KEY}",
            timeout=10
        )
        response.raise_for_status()
        
        models = response.json()
        
        if 'models' in models:
            print(f"✓ Found {len(models['models'])} models")
            print()
            print("-" * 70)
            
            # Filter for models that support generateContent
            generate_models = []
            
            for model in models['models']:
                name = model.get('name', 'Unknown')
                display_name = model.get('displayName', 'Unknown')
                supported_methods = model.get('supportedGenerationMethods', [])
                
                # Check if this model supports generateContent
                if 'generateContent' in supported_methods:
                    generate_models.append({
                        'name': name,
                        'display_name': display_name,
                        'supported_methods': supported_methods
                    })
            
            print(f"Models supporting 'generateContent' ({len(generate_models)}):")
            print()
            
            for i, model in enumerate(generate_models, 1):
                # Extract just the model identifier from full name
                model_id = model['name'].replace('models/', '')
                
                print(f"{i}. {model['display_name']}")
                print(f"   Model ID: {model_id}")
                print(f"   Full name: {model['name']}")
                print(f"   Methods: {', '.join(model['supported_methods'])}")
                print()
            
            print("-" * 70)
            print()
            print("RECOMMENDED MODELS FOR YOUR PROJECT:")
            print()
            
            # Find the best options
            recommended = []
            for model in generate_models:
                model_id = model['name'].replace('models/', '')
                display = model['display_name']
                
                if 'flash' in model_id.lower():
                    recommended.append(f"  • {model_id}  (Fast, efficient - good for job apps)")
                elif 'pro' in model_id.lower() and '1.5' in model_id:
                    recommended.append(f"  • {model_id}  (More capable, slower)")
            
            for rec in recommended:
                print(rec)
            
            print()
            print("UPDATE YOUR config/settings.py:")
            print()
            print("  LLM_MODEL = 'gemini-1.5-flash'  # or whichever model you prefer")
            print()
            
        else:
            print("✗ Unexpected response format")
            print(models)
    
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {e}")
        try:
            print(f"Response: {e.response.json()}")
        except:
            print(f"Response: {e.response.text}")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    list_gemini_models()
