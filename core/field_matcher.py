"""
Generic field-to-CV-fact matcher.
No hardcoded site names. Just heuristics.
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional


class FieldMatcher:
    """Universal field matching - works on ANY job site."""
    
    # Common field patterns grouped by CV fact type
    FIELD_PATTERNS = {
        'first_name': ['first name', 'vorname', 'given name', 'forename', 'first'],
        'last_name': ['last name', 'nachname', 'surname', 'family name', 'last'],
        'full_name': ['full name', 'your name', 'name'],
        'email': ['email', 'e-mail', 'mail', 'e mail'],
        'phone': ['phone', 'telephone', 'mobile', 'tel', 'telefon', 'handy', 'cell'],
        
        # ----- ADDRESS FIELDS (expanded for csod.com and others) -----
        'address_line1': [
            'address line 1', 'address1', 'street', 'straße', 'address',
            'address line', 'line 1', 'address line one', 'street address'
        ],
        'address_line2': [
            'address line 2', 'address2', 'line 2', 'address line two', 'apt', 'apartment', 'suite'
        ],
        'city': [
            'city', 'town', 'ort', 'stadt', 'city/town'
        ],
        'county': [
            'county', 'region', 'province', 'state', 'district'
        ],
        'postcode': [
            'postcode', 'zip', 'postal code', 'plz', 'zip code', 'post code'
        ],
        'country': [
            'country', 'land', 'nation'
        ],
        # ------------------------------------------------------------
        
        'start_date': [
            'earliest start date', 'start date', 'startdatum', 'available from',
            'earliest start', 'availability', 'available date'
        ],
        'consent': [
            'i agree', 'agree', 'consent', 'accept terms', 'data processing',
            'i consent', 'agree to', 'zustimmung', 'einwilligung', 'i agree*',
            'consider me for other positions', 'allow my information to be searchable',
            'keep my data for future opportunities', 'opt in', 'subscribe',
            'searchable', 'consider me', 'future opportunities'
        ],
        'salary_expectation': [
            'annual gross salary', 'salary expectation', 'gehaltsvorstellung',
            'expected salary', 'salary', 'gehalt', 'annual salary'
        ],
        'linkedin': ['linkedin', 'linkedin profile', 'linkedin url'],
        'github': ['github', 'github profile', 'github url'],
        'website': ['website', 'homepage', 'portfolio', 'personal website'],
        'resume': ['resume', 'cv', 'lebenslauf', 'upload cv', 'upload résumé', 'curriculum vitae'],
        'cover_letter': ['cover letter', 'anschreiben', 'motivation letter', 'motivational letter', 'upload cover letter'],
        # ----- SITE-SPECIFIC FIELDS (complex forms) -----
        'relocation': [
            'yes, i would like to relocate', 'no, i don´t want to relocate',
            'willing to relocate', 'relocation', 'ready to move'
        ],
        'portfolio': [
            'link to your portfolio', 'portfolio', 'portfolio link', 'your portfolio'
        ],
        'source': [
            'how did you learn about us', 'how did you hear about us',
            'where did you find this job', 'source', 'direct contact',
            'beyond now website', 'at_karriere', 'linkedin', 'employee referral'
        ],
        'travel_willingness': [
            'how high is your willingness to travel', 'willingness to travel',
            'travel willingness', 'how often can you travel', 'travel percentage'
        ],
        'industries': [
            'in which industries have you worked', 'industries worked in',
            'industries', 'work experience sectors', 'industry experience'
        ],
        'notice_period': [
            'how long is your period of notice', 'period of notice', 'notice period',
            'notice', 'how much notice', 'notice time'
        ],
        'hours_per_week': [
            'how many hours would you like to work', 'how many hours per week',
            'working hours', 'hours per week', 'hours per week preferred'
        ],
    }

    @classmethod
    def match_field(cls, label: str, cv_facts: Dict) -> Optional[Tuple[str, str]]:
        """
        Given a field label (from the page) and CV facts,
        returns (fact_key, value_to_fill) if a good match is found.
        """
        label_lower = label.lower().strip()
        
        # Remove common punctuation and special chars for better matching
        label_clean = re.sub(r'[*:•\-_]', ' ', label_lower).strip()
        
        # Special handling for Address Line 2 - only fill if we have explicit data
        if any(pattern in label_clean for pattern in ['address line 2', 'address2', 'line 2', 'address line two']):
            value = cv_facts.get('address_line2')
            if value:  # Only return if we have actual data
                return ('address_line2', str(value))
            else:
                # Return None to skip this optional field
                return None
        
        for fact_key, patterns in cls.FIELD_PATTERNS.items():
            if fact_key == 'country' and 'county' in label_clean:
                continue
            if fact_key == 'county' and 'country' in label_clean:
                continue
            # Check if any pattern is a substring or fuzzy match
            for pattern in patterns:
                # Direct substring match
                if pattern in label_clean:
                    value = cv_facts.get(fact_key)
                    if value:
                        return (fact_key, str(value))
                    # Also try with _path suffix for file fields
                    path_key = f"{fact_key}_path"
                    path_value = cv_facts.get(path_key)
                    if path_value:
                        return (path_key, str(path_value))
                
                # Fuzzy match (if not found, try similarity)
                similarity = SequenceMatcher(None, pattern, label_clean).ratio()
                if similarity > 0.75:  # threshold
                    value = cv_facts.get(fact_key)
                    if value:
                        return (fact_key, str(value))
                    # Also try with _path suffix for file fields
                    path_key = f"{fact_key}_path"
                    path_value = cv_facts.get(path_key)
                    if path_value:
                        return (path_key, str(path_value))
        
        # Special case: if label contains "upload" and CV path exists
        if 'upload' in label_lower or 'file' in label_lower or 'attach' in label_lower:
            if 'resume' in label_lower or 'cv' in label_lower or 'lebenslauf' in label_lower:
                if cv_facts.get('resume_path'):
                    return ('resume_path', cv_facts['resume_path'])
            if 'cover' in label_lower and 'letter' in label_lower:
                if cv_facts.get('cover_letter_path'):
                    return ('cover_letter_path', cv_facts['cover_letter_path'])
        
        return None

    @classmethod
    def extract_address_components(cls, address_str: str) -> Dict:
        """Parse address string into structured fields."""
        if not address_str:
            return {}
        
        components = {}
        
        # Try to extract postcode, city, country
        # Example: "9020 Klagenfurt am Wörthersee, Austria"
        parts = address_str.split(',')
        
        if len(parts) >= 2:
            # Last part is likely country
            components['country'] = parts[-1].strip()
            
            # First part likely contains postcode and city
            address_part = parts[0].strip()
            
            # Extract postcode (4-5 digits) and city
            pc_match = re.match(r'^(\d{4,5})\s+(.+)', address_part)
            if pc_match:
                components['postcode'] = pc_match.group(1)
                components['city'] = pc_match.group(2)
                components['address_line1'] = address_part
            else:
                # No postcode found, treat whole thing as city
                components['address_line1'] = address_part
                components['city'] = address_part
        else:
            # Single part address
            components['address_line1'] = address_str.strip()
        
        return components

    @classmethod
    def prepare_cv_facts(cls, raw_facts: Dict) -> Dict:
        """
        Prepare CV facts for field matching by extracting all possible fields.
        This ensures maximum field coverage on any job site.
        """
        prepared = raw_facts.copy()
        
        # Extract address components if raw address exists
        if 'address_raw' in raw_facts and 'address_line1' not in raw_facts:
            address_components = cls.extract_address_components(raw_facts['address_raw'])
            prepared.update(address_components)
        
        # Split full name into first/last if needed
        if 'name' in raw_facts and 'first_name' not in raw_facts:
            parts = raw_facts['name'].split()
            if len(parts) >= 2:
                prepared['first_name'] = parts[0]
                prepared['last_name'] = ' '.join(parts[1:])
            elif len(parts) == 1:
                prepared['first_name'] = parts[0]
                prepared['last_name'] = ''
        
        return prepared
