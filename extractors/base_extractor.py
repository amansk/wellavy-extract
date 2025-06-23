"""
Base extractor interface for blood test report extraction.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import logging


class BaseExtractor(ABC):
    """Abstract base class for blood test report extractors."""
    
    def __init__(self, pattern_matcher, validator, text_processor, settings: Dict[str, Any]):
        """Initialize the extractor with shared components."""
        self.pattern_matcher = pattern_matcher
        self.validator = validator
        self.text_processor = text_processor
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the given text format."""
        pass
    
    @abstractmethod
    def extract(self, text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract blood test data from text.
        
        Returns:
            Tuple of (default_markers, other_markers) where each is a list of (marker, value) tuples
        """
        pass
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the name of the format this extractor handles."""
        pass
    
    def _is_valid_extraction(self, marker: str, value: str) -> bool:
        """Validate if extraction is valid using shared validation logic."""
        if (len(marker.strip()) < self.settings['extraction_settings']['min_marker_length'] or
            self.text_processor.is_excluded_marker(marker) or
            self.text_processor.is_non_lab_keyword(marker)):
            return False
        
        return self.validator.validate_value(marker, value)
    
    def _categorize_marker(self, marker: str, value: str, default_results: List, other_results: List):
        """Categorize marker into default or other results using shared logic."""
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