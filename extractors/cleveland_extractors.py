"""
Cleveland HeartLab-specific extractors.
"""

import re
from typing import List, Tuple, Optional
from .base_extractor import BaseExtractor


class ClevelandHeartLabExtractor(BaseExtractor):
    """Extractor for Cleveland HeartLab fatty acid analysis reports."""
    
    @property
    def format_name(self) -> str:
        return "Cleveland HeartLab"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        text_lower = text.lower()
        
        has_cleveland = 'cleveland heartlab' in text_lower
        has_fatty_acids = any(term in text_lower for term in ['omegacheck', 'fatty acids'])
        has_cardiometabolic = 'cardiometabolic report' in text_lower
        
        # Comprehensive data check
        comprehensive_markers = ['white blood cell', 'hemoglobin', 'glucose', 'creatinine', 'cholesterol']
        has_comprehensive_data = any(marker in text_lower for marker in comprehensive_markers)
        
        return (has_cleveland and has_fatty_acids and 
                (has_cardiometabolic or not has_comprehensive_data))
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Cleveland HeartLab format."""
        default_results = []
        other_results = []
        lines = text.split('\n')
        
        # First, handle fragmented OmegaCheck
        omegacheck_result = self._extract_fragmented_omegacheck(lines)
        if omegacheck_result:
            marker, value = omegacheck_result
            if self._is_valid_extraction(marker, value):
                self._categorize_marker(marker, value, default_results, other_results)
        
        in_data_section = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if 'FATTY ACIDS' in line:
                in_data_section = True
                continue
            
            if any(word in line.lower() for word in ['medical information', 'comment report', 'footnotes']):
                in_data_section = False
                continue
            
            if in_data_section:
                marker_value = self._extract_cleveland_marker_value(line)
                if marker_value:
                    marker, value = marker_value
                    if self._is_valid_extraction(marker, value):
                        self._categorize_marker(marker, value, default_results, other_results)
        
        return self._remove_duplicates(default_results), self._remove_duplicates(other_results)
    
    def _extract_fragmented_omegacheck(self, lines: List[str]) -> Optional[Tuple[str, str]]:
        """Extract fragmented OmegaCheck marker that spans multiple lines."""
        for i, line in enumerate(lines):
            if 'OmegaCheck' in line and i + 2 < len(lines):
                # Look for value 2 lines ahead (skipping description line)
                value_line = lines[i + 2].strip()
                value_match = re.match(r'^([0-9]+\.?[0-9]*)', value_line)
                if value_match and '% by wt' in value_line:
                    return ('OmegaCheck', value_match.group(1))
        return None
    
    def _extract_cleveland_marker_value(self, line: str) -> Optional[Tuple[str, str]]:
        """Extract marker-value from Cleveland HeartLab format."""
        patterns = [
            # Specific pattern for Arachidonic Acid/EPA Ratio (no % by wt suffix)
            r'^(Arachidonic Acid/EPA Ratio)\s+([0-9]+\.?[0-9]*)\s+[0-9\.\-]+$',
            # Standard patterns with % by wt
            r'^([A-Za-z][A-Za-z\s\(\)®+:]+?)\s+([0-9]+\.?[0-9]*)\s+[≥<>0-9\.\-\s%]+\s+%\s+by\s+wt',
            r'^([A-Za-z][A-Za-z\s/\-]+Ratio)\s+([0-9]+\.?[0-9]*)\s+[0-9\.\-]+$',
            r'^(Omega-6/Omega-3 Ratio)\s+([0-9]+\.?[0-9]*)\s+[0-9\.\-]+$',
            r'^([A-Za-z][A-Za-z\s\-0-9]+total)\s+([0-9]+\.?[0-9]*)\s+%\s+by\s+wt',
            r'^([A-Z]{2,4})\s+([0-9]+\.?[0-9]*)\s+[0-9\.\-]+\s+%\s+by\s+wt',
            r'^([A-Za-z][A-Za-z\s]+Acid)\s+([0-9]+\.?[0-9]*)\s+[0-9\.\-]+\s+%\s+by\s+wt',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                marker = self._normalize_cleveland_marker(match.group(1).strip())
                value = match.group(2).strip()
                return (marker, value)
        
        return None
    
    def _normalize_cleveland_marker(self, marker_name: str) -> str:
        """Normalize Cleveland HeartLab marker names."""
        cleveland_mappings = {
            'OmegaCheck': 'Omega3 Total',  # Map OmegaCheck to same as Omega-3 total
            'Omega-3 total': 'Omega3 Total',
            'Omega-6 total': 'Omega 6 Total',
            'Omega-6/Omega-3 Ratio': 'Omega-6/Omega-3 Ratio',
            'Arachidonic Acid/EPA Ratio': 'Arachidonic Acid/EPA Ratio',
            'EPA': 'EPA',
            'DPA': 'DPA',
            'DHA': 'DHA',
            'Arachidonic Acid': 'Arachidonic Acid',
            'Linoleic Acid': 'Linoleic Acid'
        }
        
        for key, value in cleveland_mappings.items():
            if key in marker_name:
                return value
        
        return marker_name