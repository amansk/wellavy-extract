"""
Factory for creating appropriate extractors based on format detection.
"""

from typing import Dict, Any
import logging
from .base_extractor import BaseExtractor
from .format_detector import ReportFormat
from .labcorp_extractors import LabCorpNMRExtractor, LabCorpStandardExtractor
from .quest_extractors import QuestAnalyteValueExtractor
from .cleveland_extractors import ClevelandHeartLabExtractor
from .legacy_extractors import FragmentedExtractor, StandardExtractor


class ExtractorFactory:
    """Factory class for creating format-specific extractors."""
    
    def __init__(self, pattern_matcher, validator, text_processor, settings: Dict[str, Any]):
        """Initialize factory with shared components."""
        self.pattern_matcher = pattern_matcher
        self.validator = validator
        self.text_processor = text_processor
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # Registry of extractors
        self._extractor_registry = {
            ReportFormat.LABCORP_NMR: LabCorpNMRExtractor,
            ReportFormat.LABCORP_STANDARD: LabCorpStandardExtractor,
            ReportFormat.QUEST_ANALYTE_VALUE: QuestAnalyteValueExtractor,
            ReportFormat.CLEVELAND_HEARTLAB: ClevelandHeartLabExtractor,
            ReportFormat.FRAGMENTED: FragmentedExtractor,
            ReportFormat.STANDARD: StandardExtractor,
        }
    
    def create_extractor(self, format_type: ReportFormat) -> BaseExtractor:
        """Create an extractor for the specified format.
        
        Args:
            format_type: The detected report format
            
        Returns:
            An instance of the appropriate extractor
            
        Raises:
            ValueError: If the format is not supported
        """
        if format_type not in self._extractor_registry:
            raise ValueError(f"Unsupported format: {format_type}")
        
        extractor_class = self._extractor_registry[format_type]
        
        self.logger.info(f"Creating {extractor_class.__name__} for format {format_type.value}")
        
        return extractor_class(
            self.pattern_matcher,
            self.validator, 
            self.text_processor,
            self.settings
        )
    
    def get_available_formats(self) -> list:
        """Get list of available report formats."""
        return list(self._extractor_registry.keys())
    
    def register_extractor(self, format_type: ReportFormat, extractor_class):
        """Register a new extractor for a format.
        
        Args:
            format_type: The report format this extractor handles
            extractor_class: The extractor class (must inherit from BaseExtractor)
        """
        if not issubclass(extractor_class, BaseExtractor):
            raise ValueError("Extractor must inherit from BaseExtractor")
        
        self._extractor_registry[format_type] = extractor_class
        self.logger.info(f"Registered {extractor_class.__name__} for format {format_type.value}")