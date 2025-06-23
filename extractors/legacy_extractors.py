"""
Legacy extractors for fragmented and standard formats.
"""

import re
from typing import List, Tuple, Optional
from .base_extractor import BaseExtractor


class FragmentedExtractor(BaseExtractor):
    """Extractor for fragmented lab reports where markers and values are on separate lines."""
    
    @property
    def format_name(self) -> str:
        return "Fragmented Format"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) <= 100:
            return False
        
        # Count single-word lines that are alphabetic
        single_word_lines = sum(1 for line in lines if len(line.split()) == 1 and line.isalpha())
        fragmentation_ratio = single_word_lines / len(lines)
        
        threshold = self.settings.get('extraction_settings', {}).get('fragmentation_threshold', 0.3)
        return fragmentation_ratio > threshold
    
    def extract(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract from fragmented lab reports."""
        default_results = []
        other_results = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Look ahead for values
            marker_value = self._find_fragmented_marker_value(lines, i)
            if marker_value:
                marker, value = marker_value
                if self._is_valid_extraction(marker, value):
                    self._categorize_marker(marker, value, default_results, other_results)
            
            i += 1
        
        # Add specific fragmented patterns
        specific_results = self._extract_specific_fragmented_patterns(text)
        default_results.extend(specific_results[0])
        other_results.extend(specific_results[1])
        
        return self._remove_duplicates(default_results), self._remove_duplicates(other_results)
    
    def _find_fragmented_marker_value(self, lines: List[str], start_idx: int) -> Optional[Tuple[str, str]]:
        """Find marker-value pairs in fragmented text."""
        line = lines[start_idx].strip()
        max_lookahead = self.settings['extraction_settings']['value_lookahead_lines']
        
        for offset in range(1, min(max_lookahead + 1, len(lines) - start_idx)):
            next_line = lines[start_idx + offset].strip()
            value_match = re.match(r'^([0-9]+\.?[0-9]*)', next_line)
            
            if (re.match(r'^[A-Z][A-Z\s,\(\)/-]+$', line) and 
                len(line) > self.settings['extraction_settings']['min_marker_length'] and 
                value_match):
                
                value = value_match.group(1)
                try:
                    float_value = float(value)
                    if float_value > self.settings['extraction_settings']['max_value_threshold']:
                        continue
                    
                    # Skip absolute cell counts when we want percentages
                    if self._is_percentage_marker(line) and float_value > 100:
                        continue
                        
                except (ValueError, TypeError):
                    continue
                
                marker = line.replace(',', '').strip()
                return (marker, value)
        
        return None
    
    def _extract_specific_fragmented_patterns(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract using specific patterns for severely fragmented data."""
        default_results = []
        other_results = []
        
        fragmented_patterns = [
            (r'MCV\s*\n\s*([0-9]+\.?[0-9]*)', 'MCV'),
            (r'MCH\s*\n\s*([0-9]+\.?[0-9]*)', 'MCH'),
            (r'MCHC\s*\n\s*([0-9]+\.?[0-9]*)', 'MCHC'),
            (r'RDW\s*\n\s*([0-9]+\.?[0-9]*)', 'RDW'),
            (r'MPV\s*\n\s*([0-9]+\.?[0-9]*)', 'MPV'),
            (r'UREA NITROGEN \(BUN\)\s*\n\s*([0-9]+\.?[0-9]*)', 'BUN'),
            (r'AST\s*\n\s*([0-9]+\.?[0-9]*)', 'AST'),
            (r'ALT\s*\n\s*([0-9]+\.?[0-9]*)', 'ALT'),
            (r'TSH\s*\n\s*([0-9]+\.?[0-9]*)', 'TSH'),
            (r'VITAMIN D, 25-OH, TOTAL\s*\n\s*([0-9]+\.?[0-9]*)', 'Vitamin D'),
            (r'VITAMIN B12\s*\n\s*([0-9]+\.?[0-9]*)', 'Vitamin B12'),
            (r'FOLATE, SERUM\s*\n\s*>?([0-9]+\.?[0-9]*)', 'Folate'),
            (r'FREE T4\s*\n\s*([0-9]+\.?[0-9]*)', 'Free T4'),
            (r'FREE T3\s*\n\s*([0-9]+\.?[0-9]*)', 'Free T3'),
        ]
        
        for pattern, marker_name in fragmented_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for value in matches:
                if value and re.match(r'^[0-9]+\.?[0-9]*$', value):
                    self._categorize_marker(marker_name, value, default_results, other_results)
        
        # Remove duplicates before returning
        return self._remove_duplicates(default_results), self._remove_duplicates(other_results)
    
    def _is_percentage_marker(self, marker: str) -> bool:
        """Check if marker should be a percentage value."""
        percentage_markers = ['neutrophil', 'lymphocyte', 'monocyte', 'eosinophil', 'basophil']
        return any(pm in marker.lower() for pm in percentage_markers)


class StandardExtractor(BaseExtractor):
    """Standard extractor using generic value patterns (fallback)."""
    
    @property
    def format_name(self) -> str:
        return "Standard Format"
    
    def can_extract(self, text: str) -> bool:
        """This extractor can handle any text as a fallback."""
        return True
    
    def extract(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract using standard patterns."""
        all_results = []  # Single list to preserve order
        
        # Check if this uses Analyte/Value structure (common in Quest reports)
        # But exclude Vibrant America reports which mention analyte/value but aren't that format
        has_analyte_value = 'analyte' in text.lower() and 'value' in text.lower()
        is_vibrant = 'vibrant america' in text.lower()
        
        if has_analyte_value and not is_vibrant:
            return self._extract_analyte_value_format(text)
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or self.text_processor.is_header_line(line):
                continue
            
            marker_value_pairs = self._extract_marker_value_pairs(line)
            for marker, value in marker_value_pairs:
                if self._is_valid_extraction(marker, value):
                    all_results.append((marker, value))
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _extract_analyte_value_format(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract from lab reports with Analyte/Value structure, preserving order."""
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
    
    def _extract_marker_value_pairs(self, line: str) -> List[Tuple[str, str]]:
        """Extract marker-value pairs from a line."""
        pairs = []
        
        # First try Vibrant America format: "Test Name (units) Value Reference"
        vibrant_pattern = re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/0-9\*]+?)\s+\([^)]+\)\s+([0-9]+\.?[0-9]*)\s+.*$')
        vibrant_match = vibrant_pattern.match(line)
        if vibrant_match:
            marker = vibrant_match.group(1).strip()
            value = vibrant_match.group(2).strip()
            pairs.append((marker, value))
            return pairs
        
        # Try standard patterns
        for pattern in self.pattern_matcher.value_patterns:
            matches = pattern.findall(line)
            for match in matches:
                if len(match) >= 2:
                    marker = match[0].strip()
                    value = match[1].strip()
                    if re.match(r'^[0-9]+\.?[0-9]*$', value):
                        pairs.append((marker, value))
        
        return pairs
    
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