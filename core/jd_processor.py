import requests
import json
import re
from typing import Union, Dict
from bs4 import BeautifulSoup


class JDProcessor:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def process(self, input_data: str) -> Dict:
        if input_data.startswith(('http://', 'https://')):
            raw_text = self._scrape(input_data)
            input_type = 'url'
            source_url = input_data
        else:
            raw_text = input_data
            input_type = 'pasted'
            source_url = None
        
        structured = self._parse_with_llm(raw_text, source_url)
        structured['input_type'] = input_type
        structured['source_url'] = source_url
        structured['raw_text'] = raw_text[:3000]
        structured['human_verified'] = False
        
        return structured
    
    def _scrape(self, url: str) -> str:
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if len(text) < 200:
                raise ValueError("Extracted text too short")
            
            return text
            
        except Exception as e:
            raise ValueError(f"Scrape failed: {e}. Paste JD text manually.")
    
    def _parse_with_llm(self, text: str, source_url: str = None) -> Dict:
        from config.prompts import JD_PARSE_PROMPT
        
        truncated = text[:3000]
        prompt = JD_PARSE_PROMPT.format(text=truncated)
        
        try:
            response = self.llm.generate(prompt)
        except Exception as e:
            print(f"LLM generation failed: {e}")
            return self._fallback_parse(text, source_url)
        
        result = self._extract_json(response)
        
        if result:
            required_defaults = {
                'company_name': self._extract_company_from_url(source_url) or 'Unknown',
                'role_title': 'Unknown',
                'location': None,
                'salary_range': None,
                'must_haves': [],
                'nice_to_haves': [],
                'tools_mentioned': [],
                'responsibilities': [],
                'red_flags': []
            }
            
            for field, default in required_defaults.items():
                if field not in result or result[field] is None:
                    result[field] = default
            
            if result['company_name'] == 'Unknown':
                result['company_name'] = self._extract_company_from_text(text)
            
            if result['role_title'] == 'Unknown':
                result['role_title'] = self._extract_role_from_text(text)
            
            return result
        
        return self._fallback_parse(text, source_url)
    
    def _extract_json(self, response: str) -> Dict:
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'(\{[^{}]*"company_name"[^{}]*\})',
            r'(\{[^{}]*"role_title"[^{}]*\})',
            r'(\{.*"must_haves".*\})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1)
                try:
                    json_str = json_str.strip()
                    json_str = json_str.replace('\n', ' ')
                    json_str = re.sub(r'\s+', ' ', json_str)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _fallback_parse(self, text: str, source_url: str = None) -> Dict:
        result = {
            'company_name': self._extract_company_from_url(source_url) or self._extract_company_from_text(text) or 'Unknown',
            'role_title': self._extract_role_from_text(text) or 'Unknown',
            'location': None,
            'salary_range': None,
            'must_haves': [],
            'nice_to_haves': [],
            'tools_mentioned': [],
            'responsibilities': [],
            'red_flags': []
        }
        
        req_patterns = [
            r'(?:Requirements|Qualifications|Must.*have|You.*have)[:\s]+(.*?)(?:Nice.*have|We.*offer|Benefits|$)',
            r'(?:What.*need|What.*looking|Your.*profile)[:\s]+(.*?)(?:What.*offer|Benefits|$)',
        ]
        
        for pattern in req_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                req_text = match.group(1)
                bullets = re.split(r'[\-\*]\s*|\n\s*\n', req_text)
                for bullet in bullets:
                    bullet = bullet.strip()
                    if len(bullet) > 10 and len(bullet) < 200:
                        result['must_haves'].append(bullet)
        
        red_flag_patterns = [
            r'citizenship required',
            r'security clearance',
            r'fluent german required',
            r'native speaker',
            r'\d+\+\s*years.*experience',
        ]
        
        text_lower = text.lower()
        for pattern in red_flag_patterns:
            if re.search(pattern, text_lower):
                result['red_flags'].append(f"Detected: {pattern}")
        
        return result
    
    def _extract_company_from_url(self, url: str) -> str:
        if not url:
            return None
        
        patterns = [
            r'career\.(\w+)\.com',
            r'jobs\.(\w+)\.com',
            r'(\w+)\.jobs',
            r'www\.(\w+)\.com/careers',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                company = match.group(1)
                return company.capitalize()
        
        return None
    
    def _extract_company_from_text(self, text: str) -> str:
        patterns = [
            r'at\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s+we|\s+are|\s+is|\s*\n)',
            r'([A-Z][A-Za-z0-9\s&]+?)(?:\s+is\s+(?:a|an)\s+(?:leading|global|top))',
            r'About\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s*\n|\s*:)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:1000])
            if match:
                company = match.group(1).strip()
                if len(company) > 2 and len(company) < 50:
                    return company
        
        return None
    
    def _extract_role_from_text(self, text: str) -> str:
        patterns = [
            r'((?:Senior|Junior|Lead|Principal)?\s*(?:Project|Program|Product)\s+Manager)',
            r'((?:Senior|Junior)?\s*(?:Business|Data|IT)\s+Analyst)',
            r'((?:Senior)?\s*(?:Software|Systems|Network)\s+Engineer)',
            r'Job\s*[Tt]itle[:\s]+([^\n]+)',
            r'Position[:\s]+([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:1500], re.IGNORECASE)
            if match:
                role = match.group(1).strip()
                if len(role) > 5 and len(role) < 60:
                    return role
        
        return None
