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
        # Check for None values
        if marker is None or value is None:
            return False
            
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


class QuestTabularExtractor(BaseExtractor):
    """Extractor for Quest Diagnostics tabular format."""
    
    @property
    def format_name(self) -> str:
        return "Quest Tabular"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        text_lower = text.lower()
        
        # Look for Quest-specific indicators
        quest_indicators = ['quest diagnostics', 'questdiagnostics']
        has_quest = any(indicator in text_lower for indicator in quest_indicators)
        
        # Look for tabular header pattern
        has_tabular_header = bool(re.search(r'Test Name.*?(?:In Range|Out Of Range|Reference Range)', text, re.IGNORECASE))
        
        return has_quest and has_tabular_header
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Quest tabular format."""
        # Check if text is None
        if text is None:
            return [], []
            
        all_results = []
        lines = text.split('\n')
        
        # Multiple patterns for different Quest tabular formats
        patterns = [
            # Pattern 1: TEST_NAME VALUE FLAG RANGE UNITS [LAB]
            re.compile(r'^\s*([A-Z%][A-Z\s,\(\)/-]+?)\s+([\d<>]+\.?\d*)\s+([HL])\s+([\d\-<>\.]+)\s+(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 2: TEST_NAME VALUE RANGE UNITS [LAB] (no flag)
            re.compile(r'^\s*([A-Z%][A-Z\s,\(\)/-]+?)\s+([\d<>]+\.?\d*)\s+([\d\-<>\.]+)\s+(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 3: TEST_NAME VALUE UNITS (no range)
            re.compile(r'^\s*([A-Z%][A-Z\s,\(\)/-]+?)\s+([\d<>]+\.?\d*)\s+([%a-zA-Z/]+)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 4: TEST_NAME SEE NOTE: RANGE UNITS
            re.compile(r'^\s*([A-Z%][A-Z\s,\(\)/-]+?)\s+SEE NOTE:\s+([\d\-<>\.]+)\s+(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 5: Complex test names with numbers (IGF 1, LC/MS)
            re.compile(r'^\s*([A-Z%][A-Z\s,\(\)/\d-]+?)\s+([\d<>]+\.?\d*)\s+([HL])?\s*([\d\-<>\.]*)\s*(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 6: LIPOPROTEIN (a) pattern - handles parentheses in test name
            re.compile(r'^\s*(LIPOPROTEIN \(a\))\s+([\d<>]+\.?\d*)\s+(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 7: HEMOGLOBIN A1c pattern - handles complex value format with comparison
            re.compile(r'^\s*(HEMOGLOBIN A1c)\s+([\d<>]+\.?\d*)\s+[<>]?[\d\.]*\s*(.+?)(?:\s+[A-Z]{2})?$'),
            
            # Pattern 8: Short hormone patterns like "LH 4.0 1.5-9.3 mIU/mL UL"
            re.compile(r'^\s*(LH|FSH|TSH)\s+([\d<>]+\.?\d*)\s+([\d\-<>\.]+)\s+(.+?)(?:\s+[A-Z]{2})?$'),
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip header lines and empty lines
            if not line or any(header in line.upper() for header in ['TEST NAME', 'REFERENCE RANGE', 'IN RANGE', 'OUT OF RANGE', 'LAB']):
                continue
                
            # Skip obvious non-test lines (but allow SEX HORMONE BINDING)
            if any(skip in line.upper() for skip in ['PATIENT', 'COLLECTED', 'REPORTED', 'PAGE', 'DOB']) or ('SEX' in line.upper() and 'HORMONE BINDING' not in line.upper()):
                continue
                
            # Skip Cleveland HeartLab sections (markers are repeated later)
            if any(cleveland in line.upper() for cleveland in ['CLEVELAND HEARTLAB', 'CLEVELAND HEART LAB']):
                continue
                
            # Skip reference range lines (lines that start with test name but have ONLY comparison operators as values)
            # These are reference ranges, not actual test results - be more specific
            # Only skip if the line looks like "TEST NAME <value" or "TEST NAME >value" with no other content
            if re.match(r'^\s*[A-Z][A-Z\s,\(\)/-]+?\s+[<>]\d+\s*$', line):
                continue
            
            # Handle multi-line markers (test name split across consecutive lines)
            # Check for specific patterns: "THYROID PEROXIDASE EN" + "ANTIBODIES ..."
            if line.upper() == 'THYROID PEROXIDASE EN' and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('ANTIBODIES'):
                    # Extract value from the antibodies line  
                    antibodies_match = re.match(r'ANTIBODIES\s*(\d+\.?\d*)', next_line)
                    if antibodies_match:
                        marker_name = 'THYROID PEROXIDASE ANTIBODIES'
                        value = antibodies_match.group(1)
                        if self._is_valid_tabular_extraction(marker_name, value):
                            all_results.append((marker_name, value))
                        continue
            
            # Check for "SEX HORMONE BINDING EN" + "GLOBULIN ..."
            if line.upper().strip() == 'SEX HORMONE BINDING EN' and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('GLOBULIN'):
                    # Extract value from the globulin line: "GLOBULIN 65 H 10-50 nmol/L"
                    globulin_match = re.match(r'GLOBULIN\s*(\d+\.?\d*)', next_line)
                    if globulin_match:
                        marker_name = 'SEX HORMONE BINDING GLOBULIN'
                        value = globulin_match.group(1)
                        if self._is_valid_tabular_extraction(marker_name, value):
                            all_results.append((marker_name, value))
                        continue
            
            # Skip standalone "ANTIBODIES" or "GLOBULIN" lines that are part of multi-line markers
            # Check if previous line was a multi-line marker prefix
            if i > 0:
                prev_line = lines[i - 1].strip().upper()
                if ((prev_line == 'THYROID PEROXIDASE EN' and line.startswith('ANTIBODIES')) or
                    (prev_line == 'SEX HORMONE BINDING EN' and line.startswith('GLOBULIN'))):
                    continue  # Skip this line as it was already processed as part of multi-line marker
            
            # Try each pattern until one matches
            matched = False
            for pattern in patterns:
                try:
                    match = pattern.match(line)
                    if match:
                        groups = match.groups()
                        marker_name = groups[0].strip()
                        
                        # Handle different pattern structures
                        if 'SEE NOTE:' in line:
                            # Pattern 4: special note format
                            # Skip SEE NOTE entries as they don't have extractable values
                            continue
                        elif len(groups) >= 2:
                            value = groups[1].strip() if groups[1] is not None else None
                            
                            # Check for None values
                            if value is None:
                                continue
                            
                            # Determine if group 2 is flag or range
                            flag = None
                            range_part = None
                            units_and_lab = None
                            
                            if len(groups) >= 4 and groups[2] in ['H', 'L']:
                                # Has flag
                                flag = groups[2]
                                range_part = groups[3] if len(groups) > 3 and groups[3] else None
                                units_and_lab = groups[4] if len(groups) > 4 else None
                            elif len(groups) >= 3:
                                # No flag, group 2 might be range or units
                                if groups[2] and re.match(r'^[\d\-<>\.]+$', groups[2]):
                                    range_part = groups[2]
                                    units_and_lab = groups[3] if len(groups) > 3 else None
                                else:
                                    units_and_lab = groups[2]
                            
                            if self._is_valid_tabular_extraction(marker_name, value):
                                if include_ranges and range_part:
                                    min_range, max_range = self._parse_quest_range(range_part)
                                    all_results.append((marker_name, value, min_range, max_range))
                                else:
                                    all_results.append((marker_name, value))
                                matched = True
                                break
                except Exception as e:
                    # Skip lines that cause parsing errors
                    continue
            
            # Debug: log unmatched lines (remove in production)
            if not matched and len(line) > 10 and not any(skip in line.upper() for skip in ['PATIENT', 'COLLECTED', 'REPORTED', 'PAGE', 'DOB']):
                pass  # Could log for debugging: print(f"Unmatched: {line}")
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _parse_quest_range(self, range_str: str) -> Tuple[str, str]:
        """Parse Quest-specific range formats."""
        range_str = range_str.strip()
        
        # Handle different Quest range formats
        # Format: "min-max"
        if '-' in range_str and not range_str.startswith('<') and not range_str.startswith('>'):
            parts = range_str.split('-')
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
        less_than_match = re.match(r'^<\s*([0-9]+\.?[0-9]*)', range_str)
        if less_than_match:
            return None, less_than_match.group(1)
        
        # Format: ">value" (lower limit)
        greater_than_match = re.match(r'^>\s*([0-9]+\.?[0-9]*)', range_str)
        if greater_than_match:
            return greater_than_match.group(1), None
        
        return None, None
    
    def _is_valid_tabular_extraction(self, marker: str, value: str) -> bool:
        """Validate tabular extractions."""
        # Check for None values
        if marker is None or value is None:
            return False
            
        marker = marker.strip().upper()
        
        # Skip obvious non-markers
        if any(skip in marker for skip in ['PATIENT', 'PHONE', 'CLIENT', 'REQUISITION', 
                                          'COLLECTED', 'REPORTED', 'REFERENCE', 'RANGE',
                                          'KHURANA', 'WILD HEALTH', 'LEXINGTON', 'PAGE',
                                          'FAX', 'SPECIMEN', 'COLLECTED', 'RECEIVED']):
            return False
        
        # Skip very short markers (but allow common hormones)
        if len(marker) < 3 and marker not in ['LH', 'T3', 'T4']:
            return False
        
        # Validate value is reasonable
        try:
            # Handle comparison operators in values
            clean_value = re.sub(r'^[<>]', '', value)
            float_val = float(clean_value)
            # Reject negative values and extremely high values
            if float_val < 0 or float_val > 100000:
                return False
        except ValueError:
            return False
        
        return True