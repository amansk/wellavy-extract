"""
Elation EMR-specific extractors for lab reports printed through Elation.
Handles simplified formats from various labs when printed via Elation.
"""

import re
from typing import List, Tuple
from .base_extractor import BaseExtractor


class ElationLabCorpExtractor(BaseExtractor):
    """Extractor for LabCorp reports printed through Elation EMR."""
    
    @property
    def format_name(self) -> str:
        return "Elation LabCorp"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        # Look for Elation-specific formatting indicators
        elation_indicators = [
            # Elation prints with specific format: marker value range units location
            re.compile(r'^[A-Za-z][A-Za-z\s\-,\(\)®™/]+\s+\d+\.?\d*\s+.*\s+01\s*$', re.MULTILINE),
            # Look for typical Elation header patterns
            'Test Name Value Reference Range Loc',
            'Elation Health',
        ]
        
        # Must have LabCorp indicators AND Elation format
        has_labcorp = ('01' in text or 'LabCorp' in text.upper())
        has_elation_format = any(
            pattern.search(text) if hasattr(pattern, 'search') else pattern in text 
            for pattern in elation_indicators
        )
        
        return has_labcorp and has_elation_format
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Elation-formatted LabCorp reports."""
        all_results = []
        lines = text.split('\n')
        
        if include_ranges:
            # Patterns that capture ranges
            patterns = [
                # Elation format with range: "LDL-P 499 < 1000 nmol/L 01"
                # Pattern captures: marker, value, range, location code
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+([<>≤≥]?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s+[a-zA-Z/%]+\s+01\s*$'),
                
                # Alternative format: "HDL-C 66 > 39 mg/dL 01"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+([<>≤≥]\s*\d+(?:\.\d+)?)\s+[a-zA-Z/%]+\s+01\s*$'),
                
                # Format with range as "low - high": "Triglycerides 85 0 - 149 mg/dL 01"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\s+[a-zA-Z/%]+\s+01\s*$'),
            ]
        else:
            # Patterns without range capture
            patterns = [
                # Basic Elation LabCorp format: "Marker Value [Range] Units LocationCode"
                # "LDL-P 499 < 1000 nmol/L 01"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+.*\s+01\s*$'),
                
                # Format with units before location code
                # "LP-IR Score 32 <=45 01"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+[<>≤≥=\d\s\-]+\s+01\s*$'),
                
                # Handle cases where text runs together: "LP-IR Score 32 <=45 01Patient"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+.*01(?:\D|$)'),
                
                # Handle cases with no space before 01: "LP-IR Score 32 <=4501"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+[<>≤≥=]+\d+01'),
            ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip header and non-data lines, but make exception for lab results that
            # got concatenated with patient info by PyPDF2 (e.g., "LP-IR Score 32 <=45 01Patient Name: ...")
            if self.text_processor.is_header_line(line):
                # Check if this might be a lab result concatenated with patient info
                # Look for pattern: marker + value + range/units + location code + patient info
                potential_lab_result = re.match(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+.*01(?:Patient|Doctor|Provider)', line)
                if not potential_lab_result:
                    continue
                # If it looks like a concatenated lab result, continue processing
            
            # Skip common Elation header patterns, but make exception for lab results
            # concatenated with patient info
            skip_patterns = [
                'test name', 'value', 'reference range', 'loc',
                'patient name', 'date of birth', 'provider',
                'elation health', 'page', 'of', 'san mateo',
                'address', 'phone', 'fax', 'ca 9'
            ]
            
            line_matches_skip = any(pattern in line.lower() for pattern in skip_patterns)
            if line_matches_skip:
                # Check if this might be a lab result concatenated with patient info
                potential_lab_result = re.match(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(\d+\.?\d*)\s+.*01(?:Patient|Doctor|Provider)', line)
                if not potential_lab_result:
                    continue
                # If it looks like a concatenated lab result, continue processing
            
            # Try each pattern
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    marker_name = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Clean marker name
                    marker_name = re.sub(r'[,]+$', '', marker_name).strip()
                    
                    # Validate extraction
                    if self._is_valid_elation_extraction(marker_name, value):
                        if include_ranges and len(match.groups()) >= 3:
                            range_str = match.group(3).strip()
                            min_range, max_range = self._parse_range(range_str)
                            all_results.append((marker_name, value, min_range, max_range))
                        else:
                            all_results.append((marker_name, value))
                    break
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _is_valid_elation_extraction(self, marker: str, value: str) -> bool:
        """Validate Elation extractions."""
        marker = marker.strip()
        
        # Skip obvious non-markers
        skip_patterns = [
            r'\bpatient\b', r'\bphone\b', r'\bclient\b', r'\bdob\b', 
            r'\btest\b(?!osterone)', r'\bpage\b', r'\belation\b',
            r'\bprovider\b', r'\blocation\b', r'\baddress\b'
        ]
        
        if any(re.search(pattern, marker.lower()) for pattern in skip_patterns):
            return False
        
        # Skip very short markers
        if len(marker) < 3:
            return False
        
        # Skip markers that are mostly numbers
        if re.match(r'^[\d\.\-\s]+$', marker):
            return False
        
        # Validate value format
        if not re.match(r'^[<>]?[\d\.\-]+$', value):
            return False
        
        return True


class ElationQuestExtractor(BaseExtractor):
    """Extractor for Quest reports printed through Elation EMR (future implementation)."""
    
    @property
    def format_name(self) -> str:
        return "Elation Quest"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        # Placeholder for future Quest-via-Elation detection
        # Will need to identify Quest markers + Elation formatting
        return False
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Elation-formatted Quest reports."""
        # Placeholder for future implementation
        # Will handle Quest reports printed through Elation EMR
        return [], []