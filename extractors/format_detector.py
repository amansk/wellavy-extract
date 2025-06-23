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
    CLEVELAND_HEARTLAB = "cleveland_heartlab"
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
        
        # Cleveland HeartLab patterns
        self.cleveland_pattern = re.compile(r'cleveland heartlab', re.IGNORECASE)
        self.fatty_acids_pattern = re.compile(r'omegacheck|fatty acids', re.IGNORECASE)
    
    def detect_format(self, text: str) -> ReportFormat:
        """Detect the format of the lab report.
        
        Args:
            text: The extracted text from the PDF
            
        Returns:
            ReportFormat enum indicating the detected format
        """
        text_lower = text.lower()
        
        # Check for LabCorp formats first (most specific to least specific)
        if self._is_labcorp_nmr(text):
            self.logger.info("Detected LabCorp NMR LipoProfile format")
            return ReportFormat.LABCORP_NMR
        
        if self._is_labcorp_standard(text):
            self.logger.info("Detected LabCorp standard format")
            return ReportFormat.LABCORP_STANDARD
        
        # Check for Quest Analyte/Value format
        if self._is_quest_analyte_value(text):
            self.logger.info("Detected Quest Analyte/Value format")
            return ReportFormat.QUEST_ANALYTE_VALUE
        
        # Check for Cleveland HeartLab
        if self._is_cleveland_heartlab(text):
            self.logger.info("Detected Cleveland HeartLab format")
            return ReportFormat.CLEVELAND_HEARTLAB
        
        # Check for fragmented format
        if self._is_fragmented(text):
            self.logger.info("Detected fragmented format")
            return ReportFormat.FRAGMENTED
        
        # Default to standard format
        self.logger.info("Using standard format (fallback)")
        return ReportFormat.STANDARD
    
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
            ReportFormat.CLEVELAND_HEARTLAB: {
                "description": "Cleveland HeartLab fatty acid analysis",
                "key_indicators": ["Cleveland HeartLab", "OmegaCheck", "fatty acids"],
                "typical_pattern": "Marker Value Range % by wt"
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