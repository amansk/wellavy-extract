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
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Quest Analyte/Value format, preserving order."""
        all_results = []  # Single list to preserve order
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for "Analyte" followed by "Value" pattern
            if (('Analyte' in line and line.strip().endswith('Analyte')) and 
                i + 1 < len(lines) and lines[i + 1].strip() == 'Value'):
                
                # Found an Analyte/Value section, process it
                i += 2  # Skip "Analyte" and "Value" lines
                
                # Extract markers from this section
                while i < len(lines):
                    marker_line = lines[i].strip()
                    
                    # Stop at next Analyte section
                    if marker_line == 'Analyte':
                        break
                        
                    # Skip empty lines
                    if not marker_line:
                        i += 1
                        continue
                    
                    # Skip reference range lines and unit lines
                    if (marker_line == 'Reference Range:' or 
                        marker_line.lower() in ['thousand/ul', 'million/ul', 'g/dl', 'mg/dl', 'ng/ml', 
                                               '%', 'fl', 'pg', 'cells/ul', 'u/l', 'mg/l', 'mmol/l']):
                        i += 1
                        continue
                        
                    # Skip other header/info lines
                    if any(keyword in marker_line.lower() for keyword in 
                           ['page', 'patient', 'collected', 'reported', 'requisition', 
                            'client', 'phone', 'fax', 'specimen']):
                        i += 1
                        continue
                    
                    # Check if we have a test name and value pattern
                    if i + 1 < len(lines):
                        value_line = lines[i + 1].strip()
                        
                        # Look for numeric value
                        value_match = re.match(r'^([0-9<>]+\.?[0-9]*)', value_line)
                        if value_match:
                            marker_name = marker_line
                            value = value_match.group(1)
                            
                            if include_ranges:
                                # Look ahead for range information
                                range_info = self._find_range_info(lines, i + 2)
                                min_range, max_range = range_info if range_info else (None, None)
                                
                                if self._is_valid_analyte_extraction(marker_name, value):
                                    all_results.append((marker_name, value, min_range, max_range))
                            else:
                                if self._is_valid_analyte_extraction(marker_name, value):
                                    all_results.append((marker_name, value))
                            
                            i += 2  # Skip marker and value lines
                        else:
                            i += 1
                    else:
                        i += 1
            else:
                i += 1
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _find_range_info(self, lines: List[str], start_idx: int) -> Tuple[str, str]:
        """Look ahead to find range information after a test value."""
        # Expected pattern after value:
        # Reference Range:
        # [empty line or space]
        # range_value (like "3.8-10.8")
        # [empty line or space]  
        # units (like "Thousand/uL")
        
        max_lookahead = 10
        for offset in range(max_lookahead):
            if start_idx + offset >= len(lines):
                break
                
            line = lines[start_idx + offset].strip()
            
            # Look for range values (numbers with dash, or comparison operators)
            if re.match(r'^[0-9\.\-<>=\s]+$', line) and len(line) > 1:
                return self._parse_quest_range(line)
        
        return None, None
    
    def _extract_quest_line_with_range(self, line: str, include_ranges: bool) -> Tuple:
        """Extract from Quest line with Reference Range."""
        # Pattern: "TEST_NAME VALUE [FLAG] Reference Range: RANGE_VALUE UNITS"
        parts = line.split('Reference Range:')
        if len(parts) != 2:
            return None
            
        left_part = parts[0].strip()
        range_part = parts[1].strip()
        
        # Extract test name, value, and optional flag from left part
        # Pattern: test name (words) + value (number) + optional flag (H/L)
        match = re.match(r'^(.+?)\s+([\d<>]+\.?\d*)\s*([HL])?$', left_part)
        if not match:
            return None
            
        marker_name = match.group(1).strip()
        value = match.group(2).strip()
        flag = match.group(3) if match.group(3) else None
        
        if include_ranges:
            # Parse the range part
            min_range, max_range = self._parse_quest_range(range_part)
            return (marker_name, value, min_range, max_range)
        else:
            return (marker_name, value)
    
    def _extract_quest_line_without_range(self, line: str, include_ranges: bool) -> Tuple:
        """Extract from Quest line without Reference Range (like percentages)."""
        # Pattern: "TEST_NAME VALUE [FLAG] UNITS" 
        # Example: "NEUTROPHILS 59.2 %"
        match = re.match(r'^([A-Z][A-Z\s,\(\)/]+?)\s+([\d<>]+\.?\d*)\s*([HL])?\s*(.*)$', line)
        if not match:
            return None
            
        marker_name = match.group(1).strip()
        value = match.group(2).strip()
        flag = match.group(3) if match.group(3) else None
        units = match.group(4).strip()
        
        # Only extract if it looks like a valid test (has reasonable units)
        valid_units = ['%', 'g/dL', 'mg/dL', 'ng/mL', 'pg/mL', 'uL', 'fL', 'pg']
        if not any(unit in units for unit in valid_units):
            return None
            
        if include_ranges:
            return (marker_name, value, None, None)
        else:
            return (marker_name, value)
    
    def _parse_quest_range(self, range_str: str) -> Tuple[str, str]:
        """Parse Quest-specific range formats."""
        import re
        
        range_str = range_str.strip()
        
        # Remove units (everything after the numbers)
        # Extract just the numeric/comparison part
        range_match = re.match(r'^([0-9\.\-<>=\s]+)', range_str)
        if not range_match:
            return None, None
            
        range_part = range_match.group(1).strip()
        
        # Handle different Quest range formats
        # Format: "min-max"
        if '-' in range_part and not range_part.startswith('<') and not range_part.startswith('>'):
            parts = range_part.split('-')
            if len(parts) == 2:
                try:
                    min_val = parts[0].strip()
                    max_val = parts[1].strip()
                    float(min_val)  # Validate numeric
                    float(max_val)
                    return min_val, max_val
                except ValueError:
                    pass
        
        # Format: "<value" (upper limit)
        less_than_match = re.match(r'^<\s*([0-9]+\.?[0-9]*)', range_part)
        if less_than_match:
            return None, less_than_match.group(1)
        
        # Format: ">value" (lower limit)
        greater_than_match = re.match(r'^>\s*([0-9]+\.?[0-9]*)', range_part)
        if greater_than_match:
            return greater_than_match.group(1), None
        
        return None, None
    
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