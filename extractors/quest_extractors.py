"""
Quest Diagnostics-specific extractors.
"""

import re
from typing import List, Tuple
from .base_extractor import BaseExtractor


class QuestAnalyteValueExtractor(BaseExtractor):
    """Extractor for Quest Diagnostics Analyte/Value format."""
    
    @property
    def format_name(self) -> str:
        return "Quest Analyte/Value"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        text_lower = text.lower()
        
        # Look for Analyte/Value structure
        has_analyte_value = 'analyte' in text_lower and 'value' in text_lower
        
        # Look for Quest-specific indicators
        quest_indicators = ['quest', 'quest diagnostics']
        has_quest = any(indicator in text_lower for indicator in quest_indicators)
        
        return has_analyte_value and has_quest
    
    def extract(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract from Quest Analyte/Value format, preserving order."""
        all_results = []  # Single list to preserve order
        lines = text.split('\n')
        
        analyte_sections_found = 0
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for "Analyte" followed by "Value" pattern (more flexible)
            if (('Analyte' in line and line.strip().endswith('Analyte')) and 
                i + 1 < len(lines) and lines[i + 1].strip() == 'Value'):
                
                analyte_sections_found += 1
                
                # Found an Analyte/Value section, process it
                i += 2  # Skip "Analyte" and "Value" lines
                section_markers = 0
                
                # Extract markers from this section
                while i < len(lines):
                    marker_line = lines[i].strip()
                    
                    # Stop only at next Analyte section (not on empty lines)
                    if marker_line == 'Analyte':
                        break
                        
                    # Skip empty lines
                    if not marker_line:
                        i += 1
                        continue
                    
                    # Skip reference range lines but don't break
                    if 'Reference Range:' in marker_line:
                        i += 1
                        continue
                        
                    # Skip unit lines and other info lines but don't break  
                    if any(keyword in marker_line.lower() for keyword in 
                           ['page', 'patient', 'collected', 'reported', 'requisition', 
                            'khurana', 'client', 'phone', 'fax']):
                        i += 1
                        continue
                        
                    # Skip unit-only lines (but not marker names that contain units)
                    if marker_line.lower() in ['million/ul', 'thousand/ul', 'g/dl', 'mg/dl', 'ng/ml', 
                                              '%', 'fl', 'pg', 'cells/ul', 'u/l', 'mg/l', 'mmol/l']:
                        i += 1
                        continue
                    
                    # Check if next line has a value
                    if i + 1 < len(lines):
                        value_line = lines[i + 1].strip()
                        
                        # Extract numeric value (ignore H/L flags and other annotations)
                        value_match = re.match(r'^([0-9]+\.?[0-9]*)', value_line)
                        if value_match:
                            marker_name = marker_line
                            value = value_match.group(1)
                            
                            # Validate extraction
                            if self._is_valid_analyte_extraction(marker_name, value):
                                all_results.append((marker_name, value))
                                section_markers += 1
                            
                            i += 2  # Skip marker and value lines
                        else:
                            i += 1
                    else:
                        i += 1
            else:
                i += 1
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _is_valid_analyte_extraction(self, marker: str, value: str) -> bool:
        """Validate analyte extractions."""
        marker = marker.strip().upper()
        
        # Skip obvious non-markers and page numbers
        if any(skip in marker for skip in ['PATIENT', 'PHONE', 'CLIENT', 'REQUISITION', 
                                          'COLLECTED', 'REPORTED', 'REFERENCE', 'RANGE',
                                          'KHURANA', 'WILD HEALTH', 'LEXINGTON', 'PAGE',
                                          'FAX', 'SPECIMEN', 'COLLECTED', 'RECEIVED']):
            return False
        
        # Skip page numbers like "2 / 10", "5 / 10"
        if re.match(r'^\d+\s*/\s*\d+$', marker):
            return False
        
        # Skip very short markers
        if len(marker) < 3:
            return False
        
        # Validate value is reasonable
        try:
            float_val = float(value)
            # Reject negative values and extremely high values
            if float_val < 0 or float_val > 100000:
                return False
        except ValueError:
            return False
        
        return True