"""
LabCorp-specific extractors for different LabCorp report formats.
"""

import re
from typing import List, Tuple
from .base_extractor import BaseExtractor


class LabCorpNMRExtractor(BaseExtractor):
    """Extractor for LabCorp NMR LipoProfile reports."""
    
    @property
    def format_name(self) -> str:
        return "LabCorp NMR LipoProfile"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        nmr_indicators = [
            'LDL-P A, 01',
            'HDL-P (Total) A, 01', 
            'Small LDL-P A, 01',
            'LDL Size A, 01',
            'NMR LipoProfile'
        ]
        return any(indicator in text for indicator in nmr_indicators)
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from LabCorp NMR LipoProfile format."""
        all_results = []
        lines = text.split('\n')
        
        if include_ranges:
            # Patterns that capture ranges
            patterns = [
                # Pattern with range at end: "WBC 02 6.2 7.0 10/24/2024 x10E3/uL 3.4-10.8"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+02\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+[0-9]*\.?[0-9]*\s+[0-9/]+\s+[a-zA-Z/0-9%E]+\s+([0-9\.\-<>=\s]+)$'),
                # Pattern with A,01 code and range: "LDL-P A, 01 1258 High 961 02/27/2025 nmol/L <1000"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A,\s*01\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+[0-9]*\.?[0-9]*\s+[0-9/]+\s+[a-zA-Z/0-9%]+\s+([0-9\.\-<>=\s]+)$'),
                # Simpler pattern with range: "Glucose 02 101 High 95 02/27/2025 mg/dL 70-99"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+(?:02|0[1-4]|[AB],\s*0[1-4])\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+.*\s+([0-9\.\-<>=\s]+)$'),
            ]
        else:
            # Original patterns without range capture
            patterns = [
                # Pattern 1: CBC/CMP format with 02 code - standard format
                # "WBC 02 6.2 7.0 10/24/2024 x10E3/uL 3.4-10.8"
                re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+02\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+[0-9]*\.?[0-9]*\s+[0-9/]+\s+[a-zA-Z/0-9%E]+\s+.*$'),
            
            # Pattern 2: CBC/CMP format with special values like >2000
            # "Vitamin B12 02 1082 >2000 02/27/2025 pg/mL 232-1245"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+02\s+([0-9]+\.?[0-9]*)\s+[><]?[0-9]*\.?[0-9]*\s+[0-9/]+\s+[a-zA-Z/0-9%\.]+\s+.*$'),
            
            # Pattern 3: CBC/CMP format simpler (for lines without previous values)
            # "Glucose 02 101 High 95 02/27/2025 mg/dL 70-99"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+02\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+.*$'),
            
            # Pattern 4: More flexible 02 format for vitamins and special tests
            # "Hemoglobin A1c 02 5.4 5.5 02/27/2025 % 4.8-5.6"
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/]+)\s+02\s+([0-9]+\.?[0-9]*)\s+.*$'),
            
            # Pattern 5: NMR format with A,01 code
            # "LDL-P A, 01 1258 High 961 02/27/2025 nmol/L <1000"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A,\s*01\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+.*$'),
            
            # Pattern 11: Comprehensive LabCorp format with A marker
            # "LDL-P A 1246 High nmol/L <1000 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+[a-zA-Z/0-9%]+\s+[0-9\.\-<>=\s]+\s+01\s*$'),
            
            # Pattern 12: Comprehensive LabCorp format without A marker
            # "HDL-C 40 mg/dL >39 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+([0-9]+\.?[0-9]*)\s+[a-zA-Z/0-9%]+\s+[0-9\.\-<>=\s]+\s+01\s*$'),
            
            # Pattern 13: Format with decimal values
            # "HDL-P (Total) A 25.8 Low umol/L >=30.5 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A\s+([0-9]*\.?[0-9]+)\s*(?:High|Low)?\s+[a-zA-Z/0-9%]+\s+[0-9\.\-<>=\s]+\s+01\s*$'),
            
            # Pattern 14: Format with special characters in value
            # "LP-IR Score A 55 High <=45 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+[<>=]+[0-9]+\s+01\s*$'),
            
            # Pattern 15: Format with just marker name and value ending with any lab code
            # "Triglycerides A 160 High mg/dL 0-149 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+A\s+([0-9]+\.?[0-9]*)\s+.*0[1-4]\s*$'),
            
            # Pattern 16: Format without A marker, just value and any lab code
            # "Large VLDL-P 4.7 High nmol/L <=2.7 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+([0-9]+\.?[0-9]*)\s+.*0[1-4]\s*$'),
            
            # Pattern 17: Format with colon or calc in name (no A marker)
            # "LDL-C (NIH Calc) 103 High mg/dL 0-99 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+(?:Calc|Score|Total))\s+([0-9]+\.?[0-9]*)\s+.*0[1-4]\s*$'),
            
            # Pattern 18: Format with parentheses in name (no A marker)
            # "LDL-C (NIH Calc) 103 High mg/dL 0-99 01"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+\([^)]+\))\s+([0-9]+\.?[0-9]*)\s+.*0[1-4]\s*$'),
            
            # Pattern 19: Format with missing units pattern
            # "Vitamin D, 25-Hydroxy 63.0 ng/mL 30.0-100.0 02"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+([0-9]+\.?[0-9]*)\s+[a-zA-Z/0-9%]+\s+[0-9\.\-<>=\s]+\s+0[1-4]\s*$'),
            
            # Pattern 20: Format with special ranges
            # "Measles Antibodies, IgG 14.1 Low AU/mL Immune >16.4 02"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+([0-9]+\.?[0-9]*)\s+(?:High|Low)?\s+[a-zA-Z/0-9%]+\s+.*0[1-4]\s*$'),
            
            # Pattern 21: Format with numbers in marker name
            # "Vitamin D, 25-Hydroxy 63.0 ng/mL 30.0-100.0 02"
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/]+)\s+([0-9]+\.?[0-9]*)\s+[a-zA-Z/0-9%]+\s+[0-9\.\-<>=\s]+\s+0[1-4]\s*$'),
            
            # Pattern 22: Format for A1c and similar
            # "Hemoglobin A1c 5.5 % 4.8-5.6 02"
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/]+c)\s+([0-9]+\.?[0-9]*)\s+.*0[1-4]\s*$'),
            
            # Pattern 24: Handle "Not Estab." ranges (specific first)
            # "Neutrophils 35 % Not Estab. 02"
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/\.]+?)\s+([0-9]+\.?[0-9]*)\s+%\s+Not\s+Estab\.\s+0[1-4]\s*$'),
            
            # Pattern 25: Handle values with "Low" flag without units showing
            # "Dihydrotestosterone 11 Low ng/dL 03"
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/\.]+?)\s+([0-9]+\.?[0-9]*)\s+Low\s+[a-zA-Z/0-9%]+\s+0[1-4]\s*$'),
            
            # Pattern 23: Very broad pattern for any remaining markers (LAST)
            # Catches anything with letters, spaces, number, and lab code
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™/\.]+?)\s+([0-9]+\.?[0-9]*)\s+.*\s+0[1-4]\s*$'),
            
            # Pattern 6: Special tests with other codes (A,03, B,01, etc.)
            # "p-tau217 A, 03 0.12 pg/mL 0.00-0.18"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/0-9]+)\s+[AB],\s*0[1-4]\s+([0-9]+\.?[0-9]*)\s+.*$'),
            
            # Pattern 7: Handle values with < or > symbols
            # "LP-IR Score A, 01 <25 <25 02/27/2025 <=45"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+[AB],\s*0[1-4]\s+[<>]([0-9]+\.?[0-9]*)\s+.*$'),
            
            # Pattern 8: Alternative format without letter prefix
            # "LDL-C (NIH Calc) 01 113 High 111 02/27/2025 mg/dL 0-99"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)®™/]+)\s+0[1-4]\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s+.*$'),
            
            # Pattern 9: Lines without codes but clear lab format
            # "eGFR 113 105 02/27/2025 mL/min/1.73 >59"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+)\s+([0-9]+\.?[0-9]*)\s+[0-9]*\.?[0-9]*\s+[0-9/]+\s+[a-zA-Z/0-9%\.]+\s+.*$'),
            
            # Pattern 10: Simple lab format
            # "BUN/Creatinine Ratio 22 20 02/27/2025 9-23"
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+)\s+([0-9]+\.?[0-9]*)\s+[0-9]*\.?[0-9]*\s+[0-9/]+\s+[0-9\-]+$'),
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # For LabCorp lines, skip header check if it matches our patterns
            # This prevents valid lab results from being filtered out
            labcorp_indicators = [
                'A, 01', 'A, 02', 'A, 03', 'A, 04',
                'B, 01', 'B, 02', 'B, 03', 'B, 04',
                ' 01 ', ' 02 ', ' 03 ', ' 04 ',
                ' A ', ' B ',  # Add patterns for lines like "LDL-P A 1246..."
                ' 01', ' 02', ' 03', ' 04'  # Also match lines ending with lab codes
            ]
            is_labcorp_line = (any(indicator in line for indicator in labcorp_indicators) or
                              (any(flag in line for flag in ['High', 'Low']) and 
                               any(date_pattern in line for date_pattern in ['/2024', '/2025'])))
                
            if not is_labcorp_line and self.text_processor.is_header_line(line):
                continue
            
            # Try each pattern
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    marker_name = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Clean marker name - only remove trailing commas, keep parentheses and A designations
                    marker_name = re.sub(r'[,]+$', '', marker_name).strip()
                    # Don't remove 'A' from the end as it's an important LabCorp designation
                    
                    # Validate extraction
                    if self._is_valid_nmr_extraction(marker_name, value):
                        if include_ranges and len(match.groups()) >= 3:
                            # Extract range if available
                            range_str = match.group(3).strip() if match.group(3) else ""
                            min_range, max_range = self._parse_range(range_str)
                            all_results.append((marker_name, value, min_range, max_range))
                        else:
                            all_results.append((marker_name, value))
                    break  # Stop trying patterns once we find a match
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _is_valid_nmr_extraction(self, marker: str, value: str) -> bool:
        """Validate NMR extractions."""
        marker = marker.strip()
        
        # Very minimal validation - just skip obvious non-markers
        skip_patterns = [
            r'\bpatient\b', r'\bphone\b', r'\bclient\b', r'\bdob\b', r'\bpage\b', 
            r'\bcomment\b', r'\bguideline\b', r'\bfor inquiries\b'
        ]
        
        if any(re.search(pattern, marker.lower()) for pattern in skip_patterns):
            return False
        
        # Skip very short markers
        if len(marker) < 2:
            return False
        
        # Validate value is reasonable
        try:
            float_val = float(value)
            if float_val < 0 or float_val > 100000:
                return False
        except ValueError:
            return False
        
        return True


class LabCorpStandardExtractor(BaseExtractor):
    """Extractor for standard LabCorp reports (non-NMR)."""
    
    @property
    def format_name(self) -> str:
        return "LabCorp Standard"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        # Look for LabCorp lab codes but not NMR specific
        labcorp_indicators = ['A, 01', 'A,01']
        has_labcorp_codes = any(indicator in text for indicator in labcorp_indicators)
        
        # Make sure it's not NMR format
        nmr_indicators = ['LDL-P A, 01', 'NMR LipoProfile']
        is_nmr = any(indicator in text for indicator in nmr_indicators)
        
        return has_labcorp_codes and not is_nmr
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from standard LabCorp format."""
        all_results = []
        lines = text.split('\n')
        
        # Standard LabCorp patterns
        patterns = [
            # Pattern 1: [Test Name] [Lab Code with comma] [Value] [Flag?] [Units] [Reference Range]
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+?)\s+(A,\s*01|A,01)\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s*(?:[a-zA-Z/0-9%]+)?\s*(?:[0-9\.\-<>=\s]+)?$'),
            
            # Pattern 2: [Test Name with special chars] [Simple Code] [Value] [Flag?] [Units] [Reference Range]  
            re.compile(r'^([A-Za-z][A-Za-z0-9\s\-,\(\)®™TM/]+?)\s+(02|03|04|01)\s+([0-9]+\.?[0-9]*)\s*(?:High|Low)?\s*(?:[a-zA-Z/0-9%\.\(\)><=]+)?\s*(?:[0-9\.\-<>=\s]+)?$'),
            
            # Pattern 3: [Test Name] [Simple Code] [Value] [Units] "Not Estab." (CBC percentages)
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+?)\s+(02|03|04|01)\s+([0-9]+\.?[0-9]*)\s+%\s+Not\s+Estab\.$'),
            
            # Pattern 4: [Test Name] [>< Value] (values with > < symbols)
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+?)\s+[><]([0-9]+\.?[0-9]*)(?:\s+[a-zA-Z/0-9%\.\(\)]+)?(?:\s+[0-9\.\-<>=\s]+)?$'),
            
            # Pattern 5: [Test Name] [Value] [Units] [Reference Range] (no lab code)
            re.compile(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+?)\s+([0-9]+\.?[0-9]*)\s+(?:[a-zA-Z/0-9%\.\(\)]+)\s+(?:[0-9\.\-<>=\s]+)$'),
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Try each pattern
            for pattern_idx, pattern in enumerate(patterns):
                match = pattern.match(line)
                if match:
                    marker_name = match.group(1).strip()
                    # Value is in different groups depending on pattern
                    if pattern_idx < 3:  # Patterns 0,1,2 have lab codes - value in group 3
                        value = match.group(3).strip()
                    else:  # Patterns 3,4 - value in group 2
                        value = match.group(2).strip()
                    
                    # Clean marker name
                    marker_name = re.sub(r'[,\(\)]+$', '', marker_name).strip()
                    
                    # Validate extraction
                    if self._is_valid_labcorp_extraction(marker_name, value):
                        all_results.append((marker_name, value))
                    break  # Stop trying patterns once we find a match
                    
            # Handle multi-line cases
            self._handle_multiline_cases(lines, i, all_results)
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _handle_multiline_cases(self, lines: List[str], i: int, all_results: List):
        """Handle special multi-line LabCorp cases."""
        line = lines[i].strip()
        
        # Handle cases like "Hemoglobin A1c 02 Please Note: 02" followed by "5.4"
        multiline_match = re.match(r'^([A-Za-z][A-Za-z\s\-,\(\)/]+?)\s+(02|03|04|01)\s+(?:Please Note:\s+\d+|Not Estab\.)$', line)
        if multiline_match and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            value_match = re.match(r'^([0-9]+\.?[0-9]*)(?:\s+.*)?$', next_line)
            if value_match:
                marker_name = multiline_match.group(1).strip()
                value = value_match.group(1).strip()
                # Clean marker name
                marker_name = re.sub(r'[,\(\)]+$', '', marker_name).strip()
                # Validate extraction
                if self._is_valid_labcorp_extraction(marker_name, value):
                    all_results.append((marker_name, value))
        
        # Handle split marker names like "TMAO (Trimethylamine" + "N-oxide) A, 01 <3.3 uM <6.2"
        if line == 'TMAO (Trimethylamine' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            tmao_match = re.match(r'^N-oxide\)\s+A,\s*01\s+<([0-9]+\.?[0-9]*)', next_line)
            if tmao_match:
                value = tmao_match.group(1)
                if self._is_valid_labcorp_extraction('TMAO', value):
                    all_results.append(('TMAO (Trimethylamine N-oxide)', value))
        
        # Handle "Sex Horm Binding Glob," + "Serum 02 15.1 Low nmol/L 16.5-55.9"
        if line == 'Sex Horm Binding Glob,' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            shbg_match = re.match(r'^Serum\s+02\s+([0-9]+\.?[0-9]*)', next_line)
            if shbg_match:
                value = shbg_match.group(1)
                if self._is_valid_labcorp_extraction('Sex Horm Binding Glob', value):
                    all_results.append(('Sex Hormone Binding Globulin, Serum', value))
    
    def _is_valid_labcorp_extraction(self, marker: str, value: str) -> bool:
        """Validate LabCorp extractions."""
        marker = marker.strip()
        
        # Skip obvious non-markers (use word boundaries to avoid false matches)
        skip_patterns = [
            r'\bpatient\b', r'\bphone\b', r'\bclient\b', r'\bdob\b', r'\btest\b(?!osterone)', r'\bpage\b', r'\bbranch\b',
            r'\bnejm\b', r'\bpdf\b', r'\bcomment\b', r'\blipids\b', r'\bborderline\b', r'\bguideline\b',
            r'\bfor inquiries\b', r'\bmarginal\b', r'\bprediabetes\b', r'\blow\b', r'\bhigh\b', r'\bmoderate\b',
            r'\breduced risk\b', r'\bincreased risk\b', r'\bvery high\b', r'\bhigh risk\b', r'\bmoderate risk\b',
            r'\boptimal\b', r'\babove optimal\b', r'^serum$'
        ]
        
        if any(re.search(pattern, marker.lower()) for pattern in skip_patterns):
            return False
        
        # Skip very short markers
        if len(marker) < 3:
            return False
        
        # Validate value is reasonable
        try:
            float_val = float(value)
            if float_val < 0 or float_val > 100000:
                return False
        except ValueError:
            return False
        
        return True