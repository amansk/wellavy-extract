"""
Format detection for different lab report types.
"""

import re
from typing import Dict, List
from enum import Enum
import logging


class ReportFormat(Enum):
    """Enumeration of supported report formats."""
    LABCORP_NMR = "labcorp_nmr"
    LABCORP_STANDARD = "labcorp_standard"
    LABCORP_ANALYTE_VALUE = "labcorp_analyte_value"
    QUEST_ANALYTE_VALUE = "quest_analyte_value"
    QUEST_TABULAR = "quest_tabular"
    CLEVELAND_HEARTLAB = "cleveland_heartlab"
    BOSTON_HEART = "boston_heart"
    ELATION_LABCORP = "elation_labcorp"
    ELATION_QUEST = "elation_quest"
    FUNCTION_HEALTH = "function_health"
    FRAGMENTED = "fragmented"
    STANDARD = "standard"


class FormatDetector:
    """Detects the format of lab reports for appropriate extraction strategy."""
    
    def __init__(self, settings: Dict):
        """Initialize format detector with settings."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._compile_detection_patterns()
    
    def _compile_detection_patterns(self):
        """Compile regex patterns for format detection."""
        # LabCorp patterns
        self.labcorp_nmr_pattern = re.compile(r'LDL-P\s+A,\s*01\s+[0-9]+', re.IGNORECASE)
        self.labcorp_standard_pattern = re.compile(r'A,\s*01\s+[0-9]+\.?[0-9]*\s+(?:High|Low)?', re.IGNORECASE)
        
        # Quest patterns
        self.quest_analyte_pattern = re.compile(r'Analyte\s*\n\s*Value', re.IGNORECASE)
        self.quest_tabular_pattern = re.compile(r'Test Name.*?(?:In Range|Out Of Range|Reference Range)', re.IGNORECASE)
        
        # Cleveland HeartLab patterns
        self.cleveland_pattern = re.compile(r'cleveland heartlab', re.IGNORECASE)
        self.fatty_acids_pattern = re.compile(r'omegacheck|fatty acids', re.IGNORECASE)
        
        # Boston Heart patterns
        self.boston_heart_pattern = re.compile(r'boston heart', re.IGNORECASE)
        self.framingham_pattern = re.compile(r'200 crossing blvd.*framingham', re.IGNORECASE)
        
        # Elation patterns
        self.elation_header_pattern = re.compile(r'Test Name\s+Value\s+Reference Range\s+Loc', re.IGNORECASE)
        self.elation_labcorp_pattern = re.compile(r'^[A-Za-z][A-Za-z\s\-,\(\)®™/]+\s+\d+\.?\d*\s+.*\s+01\s*$', re.MULTILINE)
        
        # Function Health patterns
        self.function_health_pattern = re.compile(r'function dashboard', re.IGNORECASE)
        self.function_health_url_pattern = re.compile(r'my\.functionhealth\.com', re.IGNORECASE)
    
    def detect_format(self, text: str) -> ReportFormat:
        """Detect the format of the lab report.
        
        Args:
            text: The extracted text from the PDF
            
        Returns:
            ReportFormat enum indicating the detected format
        """
        text_lower = text.lower()
        
        # Check for Elation formats first (more specific)
        if self._is_elation_labcorp(text):
            self.logger.info("Detected Elation LabCorp format")
            return ReportFormat.ELATION_LABCORP
        
        if self._is_elation_quest(text):
            self.logger.info("Detected Elation Quest format")
            return ReportFormat.ELATION_QUEST
        
        # Check for LabCorp formats (most specific to least specific)
        if self._is_labcorp_nmr(text):
            self.logger.info("Detected LabCorp NMR LipoProfile format")
            return ReportFormat.LABCORP_NMR
        
        if self._is_labcorp_standard(text):
            self.logger.info("Detected LabCorp standard format")
            return ReportFormat.LABCORP_STANDARD
        
        # Check for Quest formats (most specific first)
        if self._is_quest_tabular(text):
            self.logger.info("Detected Quest tabular format")
            return ReportFormat.QUEST_TABULAR
        
        if self._is_quest_analyte_value(text):
            self.logger.info("Detected Quest Analyte/Value format")
            return ReportFormat.QUEST_ANALYTE_VALUE
        
        # Check for Cleveland HeartLab
        if self._is_cleveland_heartlab(text):
            self.logger.info("Detected Cleveland HeartLab format")
            return ReportFormat.CLEVELAND_HEARTLAB
        
        # Check for Boston Heart
        if self._is_boston_heart(text):
            self.logger.info("Detected Boston Heart Diagnostics format")
            return ReportFormat.BOSTON_HEART
        
        # Check for Function Health
        if self._is_function_health(text):
            self.logger.info("Detected Function Health Dashboard format")
            return ReportFormat.FUNCTION_HEALTH
        
        # Check for fragmented format
        if self._is_fragmented(text):
            self.logger.info("Detected fragmented format")
            return ReportFormat.FRAGMENTED
        
        # No fallback - return None to indicate unsupported format
        self.logger.warning("No supported format detected")
        return None
    
    def _is_labcorp_nmr(self, text: str) -> bool:
        """Check if text matches LabCorp NMR LipoProfile format."""
        # Look for specific NMR markers with LabCorp format
        nmr_indicators = [
            'LDL-P A, 01',
            'HDL-P (Total) A, 01', 
            'Small LDL-P A, 01',
            'LDL Size A, 01',
            'NMR LipoProfile'
        ]
        
        return any(indicator in text for indicator in nmr_indicators)
    
    def _is_labcorp_standard(self, text: str) -> bool:
        """Check if text matches LabCorp standard format."""
        # Look for LabCorp lab codes but not NMR specific
        labcorp_indicators = ['A, 01', 'A,01']
        has_labcorp_codes = any(indicator in text for indicator in labcorp_indicators)
        
        # Make sure it's not NMR format
        is_nmr = self._is_labcorp_nmr(text)
        
        return has_labcorp_codes and not is_nmr
    
    def _is_quest_analyte_value(self, text: str) -> bool:
        """Check if text matches Quest Analyte/Value format."""
        text_lower = text.lower()
        
        # Look for Analyte/Value structure
        has_analyte_value = 'analyte' in text_lower and 'value' in text_lower
        
        # Look for Quest-specific indicators (be more specific)
        quest_indicators = ['quest diagnostics', 'questdiagnostics']
        has_quest = any(indicator in text_lower for indicator in quest_indicators)
        
        # Exclude Vibrant America reports which may mention Quest but aren't Quest reports
        is_vibrant = 'vibrant america' in text_lower
        
        return has_analyte_value and has_quest and not is_vibrant and self.quest_analyte_pattern.search(text)
    
    def _is_quest_tabular(self, text: str) -> bool:
        """Check if text matches Quest tabular format."""
        text_lower = text.lower()
        
        # Look for Quest-specific indicators
        quest_indicators = ['quest diagnostics', 'questdiagnostics']
        has_quest = any(indicator in text_lower for indicator in quest_indicators)
        
        # Look for tabular header pattern
        has_tabular_header = bool(self.quest_tabular_pattern.search(text))
        
        # Look for typical Quest tabular data pattern (test name followed by value and flag)
        tabular_data_pattern = re.compile(r'^\s*[A-Z][A-Z\s,\(\)/-]+?\s+[0-9<>]+\.?[0-9]*\s+[HL]?\s+[0-9\-<>]', re.MULTILINE)
        has_tabular_data = bool(tabular_data_pattern.search(text))
        
        return has_quest and has_tabular_header and has_tabular_data
    
    def _is_cleveland_heartlab(self, text: str) -> bool:
        """Check if text matches Cleveland HeartLab format."""
        text_lower = text.lower()
        
        has_cleveland = 'cleveland heartlab' in text_lower
        has_fatty_acids = any(term in text_lower for term in ['omegacheck', 'fatty acids'])
        has_cardiometabolic = 'cardiometabolic report' in text_lower
        
        # Comprehensive data check
        comprehensive_markers = ['white blood cell', 'hemoglobin', 'glucose', 'creatinine', 'cholesterol']
        has_comprehensive_data = any(marker in text_lower for marker in comprehensive_markers)
        
        return (has_cleveland and has_fatty_acids and 
                (has_cardiometabolic or not has_comprehensive_data))
    
    def _is_boston_heart(self, text: str) -> bool:
        """Check if text matches Boston Heart Diagnostics format."""
        text_lower = text.lower()
        
        # Look for Boston Heart specific indicators
        boston_heart_indicators = [
            'boston heart',
            '200 crossing blvd',
            'framingham, ma',
            'ernst j. schaefer',
            'clia# 22d2100622',
            'nysdoh: 9021'
        ]
        
        # Proprietary test indicators
        proprietary_tests = [
            'boston heart hdl map',
            'boston heart cholesterol balance',
            'boston heart fatty acid balance',
            'hdl map®',
            'cholesterol balance®',
            'fatty acid balance™'
        ]
        
        has_boston_heart = any(indicator in text_lower for indicator in boston_heart_indicators)
        has_proprietary = any(test in text_lower for test in proprietary_tests)
        
        # Look for three-tier risk categorization (unique to Boston Heart)
        has_risk_tiers = ('optimal' in text_lower and 
                         'borderline' in text_lower and 
                         'increased risk' in text_lower)
        
        return has_boston_heart or has_proprietary or has_risk_tiers
    
    def _is_elation_labcorp(self, text: str) -> bool:
        """Check if text matches Elation-formatted LabCorp report."""
        # Look for Elation header format
        has_elation_header = bool(self.elation_header_pattern.search(text))
        
        # Look for simplified LabCorp format with location codes at end
        has_elation_labcorp_format = bool(self.elation_labcorp_pattern.search(text))
        
        # Look for LabCorp indicators
        has_labcorp = any(code in text for code in [' 01', ' 02', ' 03', ' 04'])
        
        # Must have Elation formatting AND LabCorp codes
        return (has_elation_header or has_elation_labcorp_format) and has_labcorp
    
    def _is_elation_quest(self, text: str) -> bool:
        """Check if text matches Elation-formatted Quest report."""
        # Placeholder for future implementation
        # Will need to identify Quest + Elation specific formatting
        return False
    
    def _is_function_health(self, text: str) -> bool:
        """Check if text matches Function Health Dashboard format."""
        # Look for Function Health specific indicators
        has_function_dashboard = bool(self.function_health_pattern.search(text))
        has_function_url = bool(self.function_health_url_pattern.search(text))
        
        # Look for status indicators (handle both normal and spaced text)
        has_status_indicators = (('In Range' in text and 'Out of Range' in text) or 
                               ('I n  R a n g e' in text and 'O u t  o f  R a n g e' in text))
        
        # Look for biomarker count pattern (handle both normal and spaced text)
        has_biomarker_pattern = (bool(re.search(r'\d+Biomarkers', text)) or
                               bool(re.search(r'\d+\s*B\s*i\s*o\s*m\s*a\s*r\s*k\s*e\s*r\s*s', text)))
        
        # Must have Function Health identifiers
        return (has_function_dashboard or has_function_url) and (has_status_indicators or has_biomarker_pattern)
    
    def _is_fragmented(self, text: str) -> bool:
        """Check if text appears to be fragmented."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) <= 100:
            return False
        
        # Count single-word lines that are alphabetic
        single_word_lines = sum(1 for line in lines if len(line.split()) == 1 and line.isalpha())
        fragmentation_ratio = single_word_lines / len(lines)
        
        threshold = self.settings.get('extraction_settings', {}).get('fragmentation_threshold', 0.3)
        return fragmentation_ratio > threshold
    
    def get_format_characteristics(self, format_type: ReportFormat) -> Dict[str, any]:
        """Get characteristics of a specific format for debugging."""
        characteristics = {
            ReportFormat.LABCORP_NMR: {
                "description": "LabCorp NMR LipoProfile with A,01 codes and specialized lipid markers",
                "key_indicators": ["LDL-P A, 01", "HDL-P A, 01", "NMR LipoProfile"],
                "typical_pattern": "Marker A, 01 Value [High/Low] PrevValue Date Units Range"
            },
            ReportFormat.LABCORP_STANDARD: {
                "description": "Standard LabCorp format with A,01 codes",
                "key_indicators": ["A, 01", "LabCorp"],
                "typical_pattern": "Marker A, 01 Value [High/Low] Units Range"
            },
            ReportFormat.QUEST_ANALYTE_VALUE: {
                "description": "Quest Diagnostics Analyte/Value format",
                "key_indicators": ["Analyte", "Value", "Quest"],
                "typical_pattern": "Analyte header followed by Value header, then marker-value pairs"
            },
            ReportFormat.QUEST_TABULAR: {
                "description": "Quest Diagnostics tabular format with Test Name, Range, and Lab columns",
                "key_indicators": ["Test Name", "In Range", "Out Of Range", "Reference Range", "Quest"],
                "typical_pattern": "Test Name Value Flag Range Units Lab"
            },
            ReportFormat.CLEVELAND_HEARTLAB: {
                "description": "Cleveland HeartLab fatty acid analysis",
                "key_indicators": ["Cleveland HeartLab", "OmegaCheck", "fatty acids"],
                "typical_pattern": "Marker Value Range % by wt"
            },
            ReportFormat.BOSTON_HEART: {
                "description": "Boston Heart Diagnostics with three-tier risk categorization",
                "key_indicators": ["Boston Heart", "Framingham MA", "Ernst J. Schaefer", "HDL Map®"],
                "typical_pattern": "Marker Optimal Borderline IncreasedRisk Units Value"
            },
            ReportFormat.ELATION_LABCORP: {
                "description": "LabCorp report printed through Elation EMR with simplified format",
                "key_indicators": ["Test Name Value Reference Range Loc", "location codes at end"],
                "typical_pattern": "Marker Value Range Units LocationCode"
            },
            ReportFormat.ELATION_QUEST: {
                "description": "Quest report printed through Elation EMR (future support)",
                "key_indicators": ["Elation formatting", "Quest markers"],
                "typical_pattern": "TBD - Future implementation"
            },
            ReportFormat.FUNCTION_HEALTH: {
                "description": "Function Health Dashboard export with two-line biomarker format",
                "key_indicators": ["Function Dashboard", "my.functionhealth.com", "In Range Out of Range"],
                "typical_pattern": "Biomarker Name\\nStatus Value Unit"
            },
            ReportFormat.FRAGMENTED: {
                "description": "Fragmented report with markers and values on separate lines",
                "key_indicators": ["High ratio of single-word lines"],
                "typical_pattern": "Marker on one line, value on subsequent line"
            },
            ReportFormat.STANDARD: {
                "description": "Generic format using standard value extraction patterns",
                "key_indicators": ["Fallback format"],
                "typical_pattern": "Various patterns attempted"
            }
        }
        
        return characteristics.get(format_type, {"description": "Unknown format"})