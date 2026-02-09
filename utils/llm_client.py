"""
LLM Client - Unified interface for different LLM providers
Supports: Gemini, Ollama (local), OpenAI, DeepSeek
"""

import requests
from typing import Optional
from config import settings


class LLMClient:
    """
    Unified LLM client with provider abstraction.
    
    Supports:
    - Gemini (Google, free tier)
    - Ollama (local, privacy-first)
    - OpenAI (API key required)
    - DeepSeek (cloud, free tier)
    """
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        
        # Provider-specific setup
        if self.provider == 'ollama':
            self.url = settings.OLLAMA_URL
        elif self.provider == 'openai':
            self.api_key = settings.OPENAI_API_KEY
            self.url = "https://api.openai.com/v1/chat/completions "
        elif self.provider == 'deepseek':
            self.api_key = settings.DEEPSEEK_API_KEY
            self.url = settings.DEEPSEEK_URL
        elif self.provider == 'gemini':
            self.api_key = settings.GEMINI_API_KEY
            # Gemini URL structure: base URL + model + action
            self.url = f"https://generativelanguage.googleapis.com/v1beta/models/ {self.model}:generateContent"
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from prompt using configured provider.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions (provider-specific handling)
            
        Returns:
            Generated text response
            
        Raises:
            ValueError: Unknown provider or missing API key
            requests.HTTPError: API request failed
        """
        if self.provider == 'ollama':
            return self._generate_ollama(prompt, system_prompt)
        elif self.provider == 'openai':
            return self._generate_openai(prompt, system_prompt)
        elif self.provider == 'deepseek':
            return self._generate_deepseek(prompt, system_prompt)
        elif self.provider == 'gemini':
            return self._generate_gemini(prompt, system_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _generate_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Local Ollama generation."""
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': self.temperature}
        }
        
        if system_prompt:
            payload['system'] = system_prompt
        
        try:
            response = requests.post(
                self.url,
                json=payload,
                # timeout=120  # OLD: Too short for long JD processing with local LLM
                timeout=180  # NEW: 3 minutes for local 8B model processing long prompts
            )
            response.raise_for_status()
            return response.json()['response']
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "Cannot connect to Ollama. Is 'ollama serve' running?\n"
                "Start with: ollama serve"
            )
    
    def _generate_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """OpenAI API generation."""
        if not self.api_key:
            raise ValueError("OpenAI API key not set in config/settings.py")
        
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        response = requests.post(
            self.url,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': self.model,
                'messages': messages,
                'temperature': self.temperature
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    
    def _generate_deepseek(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """DeepSeek API generation."""
        if not self.api_key:
            raise ValueError(
                "DeepSeek API key not set. Get one at https://platform.deepseek.com/ "
            )
        
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        response = requests.post(
            self.url,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': self.model,
                'messages': messages,
                'temperature': self.temperature,
                'max_tokens': 2000
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    
    def _generate_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Google Gemini API generation.
        
        Gemini API structure:
        - Contents array with parts
        - System instructions supported in Gemini 1.5+
        - API key passed as query parameter
        """
        if not self.api_key:
            raise ValueError(
                "Gemini API key not set. Get one at https://aistudio.google.com/app/apikey "
            )
        
        # Combine system prompt and user prompt for Gemini
        # (Gemini 1.5 supports systemInstruction, but combining is more universal)
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Build request payload
        payload = {
            'contents': [{
                'parts': [{'text': full_prompt}]
            }],
            'generationConfig': {
                'temperature': self.temperature,
                'topK': 40,
                'topP': 0.95,
                'maxOutputTokens': 8192
            }
        }
        
        try:
            # API key is passed as query parameter
            response = requests.post(
                f"{self.url}?key={self.api_key}",
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            # Parse Gemini response structure
            result = response.json()
            
            # Extract text from nested structure
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        return parts[0]['text']
            
            # If we get here, the response structure was unexpected
            raise ValueError(f"Unexpected Gemini response structure: {result}")
            
        except requests.exceptions.HTTPError as e:
            # Enhanced error reporting for Gemini
            error_detail = ""
            try:
                error_detail = e.response.json()
            except:
                error_detail = e.response.text
            
            raise requests.exceptions.HTTPError(
                f"Gemini API error ({e.response.status_code}): {error_detail}\n"
                f"URL: {self.url}\n"
                f"Model: {self.model}"
            )
    
    def test_connection(self) -> dict:
        """
        Test LLM provider connection.
        
        Returns:
            Dict with status, provider, model, and response/error
        """
        test_prompt = "Respond with exactly: 'Connection successful'"
        
        try:
            response = self.generate(test_prompt)
            return {
                'status': 'success',
                'provider': self.provider,
                'model': self.model,
                'response': response.strip()
            }
        except Exception as e:
            return {
                'status': 'failed',
                'provider': self.provider,
                'model': self.model,
                'error': str(e)
            }


# Convenience function for getting a client instance
def get_client() -> LLMClient:
    """Factory function to get configured LLM client."""
    return LLMClient()


# Quick test if run directly
if __name__ == '__main__':
    print(f"Testing {settings.LLM_PROVIDER} with model {settings.LLM_MODEL}...")
    
    client = get_client()
    result = client.test_connection()
    
    if result['status'] == 'success':
        print(f"✓ Connection successful!")
        print(f"  Provider: {result['provider']}")
        print(f"  Model: {result['model']}")
        print(f"  Response: {result['response']}")
    else:
        print(f"✗ Connection failed!")
        print(f"  Provider: {result['provider']}")
        print(f"  Model: {result['model']}")
        print(f"  Error: {result['error']}")