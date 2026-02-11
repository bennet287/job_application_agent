"""
LLM Client for text-based tasks only.
Uses Ollama for local processing (privacy, cost).
"""

import requests
from typing import Optional
from config import settings


class LLMClient:
    """
    Unified LLM interface for TEXT tasks only.
    
    This client is used for:
    - CV analysis
    - Cover letter generation
    - Job description parsing
    - Match scoring
    
    NOT for browser automation (see AIBrowserAutomation for that).
    """
    
    def __init__(self):
        self.provider = settings.LLM_TEXT_PROVIDER
        self.model = settings.LLM_TEXT_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        
        # Provider-specific setup
        if self.provider == 'ollama':
            self.url = settings.OLLAMA_URL
        elif self.provider == 'openai':
            self.api_key = settings.OPENAI_API_KEY
            self.url = "https://api.openai.com/v1/chat/completions"
        elif self.provider == 'deepseek':
            self.api_key = settings.DEEPSEEK_API_KEY
            self.url = settings.DEEPSEEK_URL
        elif self.provider == 'gemini':
            self.api_key = settings.GEMINI_API_KEY
            self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        else:
            raise ValueError(f"Unknown text provider: {self.provider}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from prompt using configured provider.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            
        Returns:
            Generated text response
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
                timeout=180
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
            raise ValueError("OpenAI API key not set")
        
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
            raise ValueError("DeepSeek API key not set")
        
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
        """Google Gemini API generation."""
        if not self.api_key:
            raise ValueError("Gemini API key not set")
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
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
        
        response = requests.post(
            f"{self.url}?key={self.api_key}",
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                parts = candidate['content']['parts']
                if len(parts) > 0 and 'text' in parts[0]:
                    return parts[0]['text']
        
        raise ValueError(f"Unexpected Gemini response structure: {result}")
    
    def test_connection(self) -> dict:
        """Test LLM provider connection."""
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


def get_client() -> LLMClient:
    """Factory function to get configured LLM client."""
    return LLMClient()


if __name__ == '__main__':
    print(f"Testing {settings.LLM_TEXT_PROVIDER} with model {settings.LLM_TEXT_MODEL}...")
    
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