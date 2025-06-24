"""
Boston Heart-specific extractors for Boston Heart Diagnostics reports.
"""

import re
from typing import List, Tuple, Dict
from .base_extractor import BaseExtractor


class BostonHeartExtractor(BaseExtractor):
    """Extractor for Boston Heart Diagnostics reports."""
    
    @property
    def format_name(self) -> str:
        return "Boston Heart Diagnostics"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        boston_heart_indicators = [
            'Boston Heart',
            '200 Crossing Blvd. Framingham, MA',
            'Ernst J. Schaefer, MD',
            'Boston Heart HDL Map',
            'Boston Heart Cholesterol Balance',
            'Boston Heart Fatty Acid Balance',
            'CLIA# 22D2100622'
        ]
        return any(indicator in text for indicator in boston_heart_indicators)
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Boston Heart Diagnostics format using two-pass strategy."""
        if include_ranges:
            return self._extract_with_ranges(text)
        else:
            return self._extract_values_only(text)
    
    def _extract_with_ranges(self, text: str) -> Tuple[List[Tuple], List[Tuple]]:
        """Two-pass extraction: clean summary for values, range pages for optimal ranges."""
        
        # Pass 1: Extract marker-value pairs from clean summary sections
        marker_values = self._extract_summary_values(text)
        
        # Pass 2: Extract optimal ranges from range definition sections
        optimal_ranges = self._extract_optimal_ranges(text)
        
        # Pass 3: Match markers to their optimal ranges
        all_results = []
        for marker, value in marker_values:
            # Find matching range for this marker
            min_range, max_range = self._find_optimal_range(marker, optimal_ranges)
            all_results.append((marker, value, min_range, max_range))
        
        return all_results, []
    
    def _extract_values_only(self, text: str) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract marker-value pairs without ranges."""
        all_results = []
        lines = text.split('\n')
        
        patterns = [
            # Pattern 1: Three-column risk format - extract just marker and value
            # "Total Cholesterol <200 200-240 >240 mg/dL 139"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+(?:[<>]?[\d\.]+(?:\s*-\s*[\d\.]+)?)\s+(?:[<>]?[\d\.]+(?:\s*-\s*[\d\.]+)?)\s+(?:[<>]?[\d\.]+(?:\s*-\s*[\d\.]+)?)\s+[a-zA-Z/%]+\s+([\d\.<>]+\.?\d*)\s*$'),
                
                # Pattern 2: Markers with superscript/subscript characters and digits
                # "Glucose² 72", "HbA1c 5.4", "CO₂ 29", "CoQ10¹ 0.94"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉]+?)\s+([\d\.<>]+\.?\d*)\s*$'),
                
                # Pattern 3: Complex multi-word markers ending in "Index"
                # "Omega-3 Fatty Acid Index 5.58", "Omega-6 Fatty Acid Index 37.2"
                re.compile(r'^([A-Za-z\d\-\s/]+\s+(?:Fatty\s+Acid\s+)?Index)\s+([\d\.<>]+\.?\d*)\s*$'),
                
                # Pattern 4: Ratio markers with slashes
                # "Omega-3/Omega-6 Ratio 0.17", "EPA/AA Ratio 0.22"
                re.compile(r'^([A-Za-z\d\-\s]+/[A-Za-z\d\-\s]+\s+Ratio)\s+([\d\.<>]+\.?\d*)\s*$'),
                
                # Pattern 5: Simple marker-value pairs from summary sections
                # "Total Cholesterol 139"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+([\d\.<>]+\.?\d*)\s*$'),
                
                # Pattern 6: Marker-value with units
                # "hs-CRP 1.1 mg/L"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+([\d\.<>]+\.?\d*)\s+[a-zA-Z/%]+\s*$'),
                
                # Pattern 7: Percentage values
                # "Omega-3 Index 5.2%"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+([\d\.]+)%\s*$'),
                
                # Pattern 8: Complex Boston Heart markers with special characters and units
                # "Lp(a) 12.5 mg/dL"
                re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+([\d\.<>]+\.?\d*)\s+[a-zA-Z/%\(\)]+\s*$'),
            ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip header lines and interpretive text
            if self.text_processor.is_header_line(line):
                continue
            
            # Skip Boston Heart specific non-data lines
            skip_patterns = [
                r'boston heart', r'crossing blvd', r'framingham', r'ma 01702',
                r'ernst j\. schaefer', r'lab director', r'clia#', r'nysdoh',
                r'optimal', r'borderline', r'increased risk', r'reference',
                r'interpretation', r'treatment', r'recommendation', r'page \d+',
                r'patient:', r'provider:', r'collected:', r'reported:',
                r'hdl map', r'cholesterol balance', r'fatty acid balance',
                r'genetic test', r'lipid panel', r'chemistry panel'
            ]
            
            if any(re.search(pattern, line.lower()) for pattern in skip_patterns):
                continue
                
            # Try each pattern
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    marker_name = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Clean marker name - remove trailing commas and extra spaces
                    marker_name = re.sub(r'[,]+$', '', marker_name).strip()
                    
                    # Validate extraction
                    if self._is_valid_boston_heart_extraction(marker_name, value):
                        all_results.append((marker_name, value))
                    break  # Stop trying patterns once we find a match
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _is_valid_boston_heart_extraction(self, marker: str, value: str) -> bool:
        """Validate Boston Heart extractions."""
        marker = marker.strip()
        
        # Skip obvious non-markers
        skip_patterns = [
            r'\bpatient\b', r'\bphone\b', r'\bclient\b', r'\bdob\b', r'\btest\b(?!osterone)', 
            r'\bpage\b', r'\bbranch\b', r'\bpdf\b', r'\bcomment\b', r'\binterpretation\b',
            r'\boptimal\b', r'\bborderline\b', r'\bincreased\b', r'\brisk\b', r'\breference\b',
            r'\btreatment\b', r'\brecommendation\b', r'\bguideline\b', r'\bfor inquiries\b',
            r'\bmarginal\b', r'\blow\b', r'\bhigh\b', r'\bmoderate\b', r'\bcategory\b',
            r'\bprovider\b', r'\bcollected\b', r'\breported\b', r'\bboston\b', r'\bheart\b',
            r'\bdiagnostics\b', r'\blab\b', r'\bdirector\b', r'\bclia\b', r'\bnysdoh\b'
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
        
        # Skip values that seem too large (likely page numbers or dates)
        try:
            numeric_value = float(re.sub(r'[<>]', '', value))
            if numeric_value > 50000:  # Reasonable upper bound for lab values
                return False
        except ValueError:
            return False
        
        return True
    
    def _parse_boston_heart_ranges(self, range_str: str) -> Tuple[str, str]:
        """Parse Boston Heart three-tier range system (simplified)."""
        if not range_str:
            return "", ""
        
        # For now, implement basic range parsing
        # This could be enhanced to handle the three-tier system more sophisticatedly
        return self._parse_range(range_str)
    
    def _extract_summary_values(self, text: str) -> List[Tuple[str, str]]:
        """Extract marker-value pairs from clean summary sections (pages 5-6)."""
        results = []
        lines = text.split('\n')
        
        # Patterns for clean summary format
        summary_patterns = [
            # Clean marker-value pairs: "Total Cholesterol 139"
            re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉α-ωΑ-Ω]+?)\s+([\d\.<>]+\.?\d*)\s*$'),
            # Ratio formats: "EPA/AA Ratio 0.22"
            re.compile(r'^([A-Za-z\d\-\s]+/[A-Za-z\d\-\s]+\s+Ratio)\s+([\d\.<>]+\.?\d*)\s*$'),
            # Index formats: "Omega-3 Fatty Acid Index 5.58"
            re.compile(r'^([A-Za-z\d\-\s/]+\s+(?:Fatty\s+Acid\s+)?Index)\s+([\d\.<>]+\.?\d*)\s*$'),
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try each summary pattern
            for pattern in summary_patterns:
                match = pattern.match(line)
                if match:
                    marker_name = match.group(1).strip()
                    value = match.group(2).strip()
                    
                    # Clean marker name
                    marker_name = re.sub(r'[,]+$', '', marker_name).strip()
                    
                    # Validate extraction
                    if self._is_valid_boston_heart_extraction(marker_name, value):
                        results.append((marker_name, value))
                    break
        
        return results
    
    def _extract_optimal_ranges(self, text: str) -> Dict[str, Tuple[str, str]]:
        """Extract optimal ranges from range definition sections."""
        ranges = {}
        lines = text.split('\n')
        
        # Look for range patterns (optimal is typically the first value)
        range_patterns = [
            # Standard format: "<200 200-240 >240 mg/dL" (optimal: <200)
            re.compile(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s*\n?.*?([<>]?[\d\.]+)(?:\s+[\d\.\-]+)*\s+[a-zA-Z/%]*\s*$', re.MULTILINE),
            # Direct optimal extraction: "<200" as optimal range
            re.compile(r'^([<>]?[\d\.]+(?:\s*-\s*[\d\.]+)?)\s+.*$'),
        ]
        
        i = 0
        current_marker = None
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Check if this line is a marker name (from previous extraction)
            marker_match = re.match(r'^([A-Za-z][A-Za-z\d\s\-\(\)®™/¹²³⁰⁴⁵⁶⁷⁸⁹]+?)\s+[\d\.<>]+', line)
            if marker_match:
                current_marker = marker_match.group(1).strip()
                i += 1
                continue
            
            # Check if this line contains range information
            if current_marker and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Look for optimal range pattern in next line
                optimal_match = re.match(r'^([<>]?[\d\.]+(?:\s*-\s*[\d\.]+)?)', next_line)
                if optimal_match:
                    optimal_range = optimal_match.group(1)
                    min_range, max_range = self._parse_optimal_range(optimal_range)
                    ranges[current_marker] = (min_range, max_range)
                    current_marker = None
            
            i += 1
        
        return ranges
    
    def _parse_optimal_range(self, optimal_str: str) -> Tuple[str, str]:
        """Parse optimal range string into min/max values."""
        if not optimal_str:
            return "", ""
        
        optimal_str = optimal_str.strip()
        
        # Handle different optimal range formats
        if optimal_str.startswith('<'):
            # "<200" means max value is 200, no min
            max_val = optimal_str[1:]
            return "", max_val
        elif optimal_str.startswith('>'):
            # ">50" means min value is 50, no max
            min_val = optimal_str[1:]
            return min_val, ""
        elif '-' in optimal_str and not optimal_str.startswith('-'):
            # "70-99" means range from 70 to 99
            parts = optimal_str.split('-')
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
        
        return "", ""
    
    def _find_optimal_range(self, marker: str, ranges_dict: Dict[str, Tuple[str, str]]) -> Tuple[str, str]:
        """Find optimal range for a marker using fuzzy matching."""
        # Direct match first
        if marker in ranges_dict:
            return ranges_dict[marker]
        
        # Fuzzy matching for name variations
        marker_lower = marker.lower()
        for range_marker, range_values in ranges_dict.items():
            range_marker_lower = range_marker.lower()
            
            # Check if markers are similar (handle variations like "HDL-C" vs "HDL")
            if (marker_lower in range_marker_lower or 
                range_marker_lower in marker_lower or
                self._markers_similar(marker_lower, range_marker_lower)):
                return range_values
        
        # No matching range found
        return "", ""
    
    def _markers_similar(self, marker1: str, marker2: str) -> bool:
        """Check if two marker names are similar enough to be the same marker."""
        # Remove common suffixes/prefixes and compare
        clean1 = re.sub(r'[\s\-\(\)®™¹²³⁰⁴⁵⁶⁷⁸⁹]', '', marker1.lower())
        clean2 = re.sub(r'[\s\-\(\)®™¹²³⁰⁴⁵⁶⁷⁸⁹]', '', marker2.lower())
        
        # Check if one is contained in the other (after cleaning)
        return clean1 in clean2 or clean2 in clean1