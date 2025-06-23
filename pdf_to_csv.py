#!/usr/bin/env python3
"""
Blood Test PDF to CSV Extractor
Extracts blood test markers and values from lab report PDFs and outputs to CSV format.
"""

import re
import csv
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

import click
from PyPDF2 import PdfReader
from dateutil import parser as date_parser

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


class ConfigLoader:
    """Load and manage configuration files."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(__file__).parent / config_dir
        self._markers = None
        self._settings = None
    
    def load_markers(self) -> Dict[str, Any]:
        """Load marker definitions from JSON."""
        if self._markers is None:
            try:
                with open(self.config_dir / "markers.json", 'r') as f:
                    self._markers = json.load(f)
            except FileNotFoundError:
                logging.error(f"Markers config file not found: {self.config_dir / 'markers.json'}")
                raise
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in markers config: {e}")
                raise
        return self._markers
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON."""
        if self._settings is None:
            try:
                with open(self.config_dir / "settings.json", 'r') as f:
                    self._settings = json.load(f)
            except FileNotFoundError:
                logging.error(f"Settings config file not found: {self.config_dir / 'settings.json'}")
                raise
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in settings config: {e}")
                raise
        return self._settings
    


class ValueValidator:
    """Validate extracted blood test values."""
    
    def __init__(self, markers_config: Dict[str, Any]):
        self.markers_config = markers_config
        self._build_validation_map()
    
    def _build_validation_map(self):
        """Build a mapping of marker names to validation ranges."""
        self.validation_map = {}
        
        # Process default markers
        for category, markers in self.markers_config['default_markers'].items():
            for pattern, config in markers.items():
                name = config['name']
                self.validation_map[name.lower()] = {
                    'min': config['min'],
                    'max': config['max'],
                    'units': config['units']
                }
        
        # Process other markers
        for pattern, config in self.markers_config['other_markers'].items():
            name = config['name']
            self.validation_map[name.lower()] = {
                'min': config['min'],
                'max': config['max'],
                'units': config['units']
            }
    
    def validate_value(self, marker_name: str, value: str) -> bool:
        """Validate if a value is reasonable for the given marker."""
        try:
            float_value = float(value)
            validation_info = self.validation_map.get(marker_name.lower())
            
            if validation_info:
                return validation_info['min'] <= float_value <= validation_info['max']
            else:
                # For unknown markers, reject extreme values
                return 0.001 <= float_value <= 10000
                
        except (ValueError, TypeError):
            return False
    
    def get_expected_range(self, marker_name: str) -> Optional[Tuple[float, float, str]]:
        """Get expected range and units for a marker."""
        validation_info = self.validation_map.get(marker_name.lower())
        if validation_info:
            return validation_info['min'], validation_info['max'], validation_info['units']
        return None


class PatternMatcher:
    """Compile and manage regex patterns for efficient matching."""
    
    def __init__(self, markers_config: Dict[str, Any], settings: Dict[str, Any]):
        self.markers_config = markers_config
        self.settings = settings
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for better performance."""
        # Compile marker patterns
        self.default_patterns = {}
        self.other_patterns = {}
        
        # Default markers
        for category, markers in self.markers_config['default_markers'].items():
            for pattern, config in markers.items():
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
                self.default_patterns[compiled_pattern] = config['name']
        
        # Other markers
        for pattern, config in self.markers_config['other_markers'].items():
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self.other_patterns[compiled_pattern] = config['name']
        
        # Date patterns
        self.date_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.settings['date_patterns']
        ]
        
        # Value extraction patterns
        self.value_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.settings['value_patterns']
        ]
    
    def match_default_marker(self, text: str) -> Optional[str]:
        """Check if text matches any default marker pattern."""
        for pattern, name in self.default_patterns.items():
            if pattern.search(text):
                return name
        return None
    
    def match_other_marker(self, text: str) -> Optional[str]:
        """Check if text matches any other marker pattern."""
        for pattern, name in self.other_patterns.items():
            if pattern.search(text):
                return name
        return None


class TextProcessor:
    """Process and clean text from PDFs."""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.exclusion_lists = settings['exclusion_lists']
    
    def is_header_line(self, line: str) -> bool:
        """Check if line is a header or patient info."""
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in self.exclusion_lists['header_keywords'])
    
    def is_excluded_marker(self, marker_name: str) -> bool:
        """Check if marker contains excluded words."""
        marker_lower = marker_name.lower()
        return any(word in marker_lower for word in self.exclusion_lists['exclude_words'])
    
    def is_non_lab_keyword(self, marker_name: str) -> bool:
        """Check if marker contains non-lab keywords."""
        marker_lower = marker_name.lower()
        return any(word in marker_lower for word in self.exclusion_lists['non_lab_keywords'])
    
    def clean_marker_name(self, raw_name: str) -> str:
        """Clean and normalize marker names."""
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-/()]', '', raw_name.strip())
        cleaned = ' '.join(cleaned.split())  # Remove extra spaces
        return ' '.join(word.capitalize() for word in cleaned.split())
    
    def detect_fragmentation(self, text: str) -> bool:
        """Detect if text appears to be fragmented."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) <= 100:
            return False
        
        single_word_lines = sum(1 for line in lines if len(line.split()) == 1 and line.isalpha())
        return single_word_lines / len(lines) > self.settings['extraction_settings']['fragmentation_threshold']


class DateExtractor:
    """Extract dates from PDF text."""
    
    def __init__(self, pattern_matcher: PatternMatcher):
        self.pattern_matcher = pattern_matcher
    
    def extract_date(self, text: str) -> str:
        """Extract date from PDF text content."""
        for pattern in self.pattern_matcher.date_patterns:
            matches = pattern.findall(text)
            if matches:
                try:
                    parsed_date = date_parser.parse(matches[0])
                    return parsed_date.strftime('%Y-%m-%d')
                except Exception as e:
                    logging.debug(f"Failed to parse date '{matches[0]}': {e}")
                    continue
        
        # If no date found, use current date
        logging.warning("No date found in PDF, using current date")
        return datetime.now().strftime('%Y-%m-%d')


class LabReportExtractor:
    """Main extractor for different types of lab reports."""
    
    def __init__(self, pattern_matcher: PatternMatcher, validator: ValueValidator, 
                 text_processor: TextProcessor, settings: Dict[str, Any]):
        self.pattern_matcher = pattern_matcher
        self.validator = validator
        self.text_processor = text_processor
        self.settings = settings
    
    def extract_standard_format(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract from standard lab report format."""
        all_results = []  # Single list to preserve order
        
        # Check if this uses Analyte/Value structure (common in Quest reports)
        if 'analyte' in text.lower() and 'value' in text.lower():
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
    
    def extract_fragmented_format(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
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
    
    def extract_cleveland_heartlab_format(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
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
    
    def _remove_duplicates_preserve_order(self, results: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Remove duplicate marker-value pairs while preserving order."""
        seen = set()
        unique_results = []
        for marker, value in results:
            key = (marker.lower(), value)
            if key not in seen:
                seen.add(key)
                unique_results.append((marker, value))
        return unique_results
    
    def _extract_marker_value_pairs(self, line: str) -> List[Tuple[str, str]]:
        """Extract marker-value pairs from a line."""
        pairs = []
        
        for pattern in self.pattern_matcher.value_patterns:
            matches = pattern.findall(line)
            for match in matches:
                if len(match) >= 2:
                    marker = match[0].strip()
                    value = match[1].strip()
                    if re.match(r'^[0-9]+\.?[0-9]*$', value):
                        pairs.append((marker, value))
        
        return pairs
    
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
    
    def extract_labcorp_format(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract from LabCorp format with lab codes and structured results."""
        all_results = []  # Single list to preserve order
        lines = text.split('\n')
        
        # LabCorp patterns: Multiple formats to handle variations
        labcorp_patterns = [
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
            for pattern_idx, pattern in enumerate(labcorp_patterns):
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
                    
            # Handle multi-line cases like "Hemoglobin A1c 02 Please Note: 02" followed by "5.4"
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
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
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
    
    def _extract_fragmented_omegacheck(self, lines: List[str]) -> Optional[Tuple[str, str]]:
        """Extract fragmented OmegaCheck marker that spans multiple lines."""
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for OmegaCheck pattern
            if 'OmegaCheck' in line and i + 2 < len(lines):
                # Skip the descriptor line and get the value
                value_line = lines[i + 2].strip()
                value_match = re.match(r'^([0-9]+\.?[0-9]*)', value_line)
                if value_match:
                    return ('Omega3 Total', value_match.group(1))
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
    
    def _is_percentage_marker(self, marker: str) -> bool:
        """Check if marker should be a percentage value."""
        percentage_markers = ['neutrophil', 'lymphocyte', 'monocyte', 'eosinophil', 'basophil']
        return any(pm in marker.lower() for pm in percentage_markers)
    
    def _is_valid_extraction(self, marker: str, value: str) -> bool:
        """Validate if extraction is valid."""
        if (len(marker.strip()) < self.settings['extraction_settings']['min_marker_length'] or
            self.text_processor.is_excluded_marker(marker) or
            self.text_processor.is_non_lab_keyword(marker)):
            return False
        
        return self.validator.validate_value(marker, value)
    
    def _categorize_marker(self, marker: str, value: str, default_results: List, other_results: List):
        """Categorize marker into default or other results."""
        default_name = self.pattern_matcher.match_default_marker(marker)
        if default_name:
            default_results.append((default_name, value))
            return
        
        other_name = self.pattern_matcher.match_other_marker(marker)
        if other_name:
            other_results.append((other_name, value))
        else:
            # Clean and add to other
            cleaned_name = self.text_processor.clean_marker_name(marker)
            if len(cleaned_name) > 2:
                other_results.append((cleaned_name, value))
    
    def _remove_duplicates(self, results: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Remove duplicate marker-value pairs."""
        seen = set()
        unique_results = []
        for marker, value in results:
            key = (marker.lower(), value)
            if key not in seen:
                seen.add(key)
                unique_results.append((marker, value))
        return unique_results


class BloodTestExtractor:
    """Main class for extracting blood test information from PDF lab reports."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_loader = ConfigLoader(config_dir)
        self._setup_logging()
        self._initialize_components()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        try:
            settings = self.config_loader.load_settings()
            log_config = settings.get('logging', {})
            
            logging.basicConfig(
                level=getattr(logging, log_config.get('level', 'INFO')),
                format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            # Fallback to basic logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"Failed to setup logging from config: {e}")
    
    def _initialize_components(self):
        """Initialize all component classes."""
        try:
            markers_config = self.config_loader.load_markers()
            self.settings = self.config_loader.load_settings()
            
            self.validator = ValueValidator(markers_config)
            self.pattern_matcher = PatternMatcher(markers_config, self.settings)
            self.text_processor = TextProcessor(self.settings)
            self.date_extractor = DateExtractor(self.pattern_matcher)
            self.lab_extractor = LabReportExtractor(
                self.pattern_matcher, self.validator, self.text_processor, self.settings
            )
            
            self.logger.info("BloodTestExtractor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file with fallback to pdfplumber."""
        try:
            # First try PyPDF2
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            # Check if extraction was successful (has meaningful content)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            # Also check for comprehensive lab markers to detect if LabCorp content is missing
            has_lab_markers = any(marker in text.lower() for marker in 
                                ['white blood cell', 'hemoglobin', 'glucose', 'creatinine', 'cholesterol'])
            # For combination reports, we need both Cleveland and comprehensive data
            has_cleveland = 'cleveland heartlab' in text.lower()
            
            if len(lines) > 50 and (not has_cleveland or has_lab_markers):  # Restored threshold
                self.logger.info(f"Successfully extracted text from PDF using PyPDF2: {pdf_path}")
                return text
            else:
                self.logger.warning(f"PyPDF2 extraction yielded limited content ({len(lines)} lines), trying pdfplumber fallback")
                
        except Exception as e:
            self.logger.warning(f"PyPDF2 extraction failed: {str(e)}, trying pdfplumber fallback")
        
        # Fallback to pdfplumber if available
        if HAS_PDFPLUMBER:
            try:
                text = ""
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                
                self.logger.info(f"Successfully extracted text from PDF using pdfplumber: {pdf_path}")
                return text
                
            except Exception as e:
                error_msg = f"Both PyPDF2 and pdfplumber failed to read PDF {pdf_path}: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        else:
            error_msg = f"PyPDF2 extraction failed and pdfplumber not available for PDF {pdf_path}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def extract_blood_test_data(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract blood test markers and values from text using new architecture.
        
        Args:
            text: The extracted text from the PDF
            include_ranges: Whether to include reference ranges in the output
            
        Returns:
            Tuple of (default_data, other_data) where data items are tuples of:
            - Without ranges: (marker, value)
            - With ranges: (marker, value, min_range, max_range)
        """
        try:
            # Import here to avoid circular imports
            from extractors.format_detector import FormatDetector
            from extractors.extractor_factory import ExtractorFactory
            
            # Create format detector and determine format
            format_detector = FormatDetector(self.settings)
            detected_format = format_detector.detect_format(text)
            
            self.logger.info(f"Detected format: {detected_format.value}")
            
            # Create appropriate extractor
            extractor_factory = ExtractorFactory(
                self.pattern_matcher, 
                self.validator, 
                self.text_processor, 
                self.settings
            )
            
            extractor = extractor_factory.create_extractor(detected_format)
            
            # Extract data using format-specific extractor
            return extractor.extract(text, include_ranges)
                
        except Exception as e:
            self.logger.error(f"Error during blood test data extraction: {e}")
            raise
    
    def process_pdf(self, pdf_path: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple], str]:
        """Process PDF and extract blood test data with date.
        
        Args:
            pdf_path: Path to the PDF file
            include_ranges: Whether to include reference ranges in the output
            
        Returns:
            Tuple of (default_data, other_data, date) where data items are tuples of:
            - Without ranges: (marker, value)
            - With ranges: (marker, value, min_range, max_range)
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.logger.info(f"Processing PDF: {pdf_path}")
        
        # Extract text from PDF
        text = self.extract_text_from_pdf(pdf_path)
        
        # Extract date
        date = self.date_extractor.extract_date(text)
        self.logger.info(f"Extracted date: {date}")
        
        # Extract blood test data
        default_data, other_data = self.extract_blood_test_data(text, include_ranges)
        
        self.logger.info(f"Extracted {len(default_data)} default markers and {len(other_data)} other markers")
        
        return default_data, other_data, date


def generate_csv_content(default_data: List[Tuple], other_data: List[Tuple], date: str, include_ranges: bool = False) -> str:
    """
    Generate CSV content as a string from extracted blood test data.
    
    Args:
        default_data: List of tuples for default markers
        other_data: List of tuples for other markers
        date: Date string for the report
        include_ranges: Whether ranges are included in the data
        
    Returns:
        CSV content as a string
    """
    import io
    
    # Combine all data into single CSV (preserving order from default_data)
    all_data = default_data + other_data
    
    if not all_data:
        return ""
    
    # Create CSV content in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    if include_ranges:
        # Format: Marker, MinRange, MaxRange, Date
        writer.writerow(['Marker', 'MinRange', 'MaxRange', date])
        for item in all_data:
            if len(item) == 4:  # (marker, value, min_range, max_range)
                marker, value, min_range, max_range = item
                writer.writerow([marker, min_range or '', max_range or '', value])
            else:
                # Fallback if no ranges provided
                marker, value = item
                writer.writerow([marker, '', '', value])
    else:
        # Original format: Marker, Date
        writer.writerow(['Marker', date])
        for item in all_data:
            if len(item) >= 2:
                marker, value = item[:2]  # Take only first two elements
                writer.writerow([marker, value])
    
    return output.getvalue()


def save_csv_to_file(csv_content: str, output_path: Path) -> None:
    """
    Save CSV content to a file.
    
    Args:
        csv_content: The CSV content as a string
        output_path: Path where to save the CSV file
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        csvfile.write(csv_content)


@click.command()
@click.argument('pdf_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output CSV file path (default: same name as PDF with .csv extension)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--include-ranges', '-r', is_flag=True, help='Include reference ranges (MinRange, MaxRange) in output')
@click.option('--config-dir', default='config', help='Configuration directory path')
def main(pdf_file: str, output: Optional[str], verbose: bool, include_ranges: bool, config_dir: str):
    """
    Extract blood test information from lab report PDFs and convert to CSV.
    
    Creates two CSV files:
    1. Main CSV with default markers (CMP, CBC, hormones, lipids, etc.)
    2. Other CSV with additional markers found
    
    PDF_FILE: Path to the PDF lab report file
    """
    try:
        # Setup logging level based on verbose flag
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        extractor = BloodTestExtractor(config_dir)
        
        if verbose:
            click.echo(f"Processing PDF: {pdf_file}")
        
        # Process the PDF
        default_data, other_data, date = extractor.process_pdf(pdf_file, include_ranges)
        
        if not default_data and not other_data:
            click.echo("Warning: No blood test data found in the PDF", err=True)
            return
        
        # Determine output file paths
        pdf_path = Path(pdf_file)
        if not output:
            main_output = pdf_path.with_suffix('.csv')
            other_output = pdf_path.with_name(f"{pdf_path.stem}_other.csv")
        else:
            output_path = Path(output)
            main_output = output_path
            other_output = output_path.with_name(f"{output_path.stem}_other{output_path.suffix}")
        
        # Generate CSV content using the reusable function
        csv_content = generate_csv_content(default_data, other_data, date, include_ranges)
        
        if csv_content:
            save_csv_to_file(csv_content, main_output)
            
            click.echo(f"CSV file created: {main_output}")
            if verbose:
                all_data = default_data + other_data
                click.echo(f"Total markers extracted: {len(all_data)}")
                for marker, value in all_data:
                    click.echo(f"  {marker}: {value}")
        
        if verbose:
            click.echo(f"Date extracted: {date}")
            click.echo(f"Total markers found: {len(default_data) + len(other_data)}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()