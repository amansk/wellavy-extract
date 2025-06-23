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
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract blood test data from text.
        
        Args:
            text: The text to extract from
            include_ranges: Whether to include reference ranges in the output
            
        Returns:
            Tuple of (default_markers, other_markers) where each is a list of tuples:
            - Without ranges: (marker, value)
            - With ranges: (marker, value, min_range, max_range)
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
    
    def _categorize_marker(self, marker: str, value: str, default_results: List, other_results: List, 
                          min_range: str = None, max_range: str = None):
        """Categorize marker into default or other results using shared logic."""
        default_name = self.pattern_matcher.match_default_marker(marker)
        if default_name:
            if min_range is not None or max_range is not None:
                default_results.append((default_name, value, min_range, max_range))
            else:
                default_results.append((default_name, value))
            return
        
        other_name = self.pattern_matcher.match_other_marker(marker)
        if other_name:
            if min_range is not None or max_range is not None:
                other_results.append((other_name, value, min_range, max_range))
            else:
                other_results.append((other_name, value))
        else:
            # Clean and add to other
            cleaned_name = self.text_processor.clean_marker_name(marker)
            if len(cleaned_name) > 2:
                if min_range is not None or max_range is not None:
                    other_results.append((cleaned_name, value, min_range, max_range))
                else:
                    other_results.append((cleaned_name, value))
    
    def _remove_duplicates_preserve_order(self, results: List[Tuple]) -> List[Tuple]:
        """Remove duplicate marker-value pairs while preserving order."""
        seen = set()
        unique_results = []
        for result in results:
            # Handle both 2-tuple and 4-tuple formats
            if len(result) >= 2:
                marker, value = result[0], result[1]
                key = (marker.lower(), value)
                if key not in seen:
                    seen.add(key)
                    unique_results.append(result)
        return unique_results
    
    def _remove_duplicates(self, results: List[Tuple]) -> List[Tuple]:
        """Remove duplicate marker-value pairs."""
        seen = set()
        unique_results = []
        for result in results:
            # Handle both 2-tuple and 4-tuple formats
            if len(result) >= 2:
                marker, value = result[0], result[1]
                key = (marker.lower(), value)
                if key not in seen:
                    seen.add(key)
                    unique_results.append(result)
        return unique_results
    
    def _parse_range(self, range_str: str) -> Tuple[str, str]:
        """Parse a range string into min and max values.
        
        Args:
            range_str: The range string to parse (e.g., "10-50", "<100", ">40")
            
        Returns:
            Tuple of (min_range, max_range) where either can be None for unbounded ranges
        """
        import re
        
        if not range_str:
            return None, None
        
        range_str = range_str.strip()
        
        # Handle different range formats
        # Format: "10-50" or "10 - 50"
        if '-' in range_str and not range_str.startswith('-'):
            parts = range_str.split('-')
            if len(parts) == 2:
                try:
                    min_val = parts[0].strip()
                    max_val = parts[1].strip()
                    # Validate they're numeric
                    float(min_val)
                    float(max_val)
                    return min_val, max_val
                except ValueError:
                    pass
        
        # Format: "10~50" (tilde separator)
        if '~' in range_str:
            parts = range_str.split('~')
            if len(parts) == 2:
                try:
                    min_val = parts[0].strip()
                    max_val = parts[1].strip()
                    float(min_val)
                    float(max_val)
                    return min_val, max_val
                except ValueError:
                    pass
        
        # Format: "<100" or "≤100"
        less_than_match = re.match(r'^[<≤]\s*([0-9]+\.?[0-9]*)', range_str)
        if less_than_match:
            return None, less_than_match.group(1)
        
        # Format: ">40" or "≥40"
        greater_than_match = re.match(r'^[>≥]\s*([0-9]+\.?[0-9]*)', range_str)
        if greater_than_match:
            return greater_than_match.group(1), None
        
        # Format: "<=100"
        less_equal_match = re.match(r'^<=\s*([0-9]+\.?[0-9]*)', range_str)
        if less_equal_match:
            return None, less_equal_match.group(1)
        
        # Format: ">=40"
        greater_equal_match = re.match(r'^>=\s*([0-9]+\.?[0-9]*)', range_str)
        if greater_equal_match:
            return greater_equal_match.group(1), None
        
        return None, None