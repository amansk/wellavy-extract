"""
Function Health-specific extractor for Function Health Dashboard reports.
"""

import re
from typing import List, Tuple
from .base_extractor import BaseExtractor


class FunctionHealthExtractor(BaseExtractor):
    """Extractor for Function Health Dashboard reports."""
    
    @property
    def format_name(self) -> str:
        return "Function Health Dashboard"
    
    def can_extract(self, text: str) -> bool:
        """Check if this extractor can handle the text."""
        function_health_indicators = [
            'Function Dashboard',
            'my.functionhealth.com',
            'In Range Out of Range Improving',
            'Biomarkers'
        ]
        return any(indicator in text for indicator in function_health_indicators)
    
    def extract(self, text: str, include_ranges: bool = False) -> Tuple[List[Tuple], List[Tuple]]:
        """Extract from Function Health Dashboard format using two-line parsing."""
        all_results = []
        lines = text.split('\n')
        
        # Function Health uses a two-line format:
        # Line 1: Biomarker Name
        # Line 2: Status Value Unit
        
        i = 0
        while i < len(lines) - 1:
            current_line = lines[i].strip()
            next_line = lines[i + 1].strip()
            
            if not current_line or not next_line:
                i += 1
                continue
            
            # Skip header/footer and navigation lines
            if self._should_skip_line(current_line):
                i += 1
                continue
            
            # Check for concatenated biomarker lines (multiple NEW markers in one line)
            concatenated_results = self._extract_concatenated_biomarkers(current_line, include_ranges)
            if concatenated_results:
                all_results.extend(concatenated_results)
                i += 1
                continue
            
            # Check for three-line NEW marker pattern:
            # Line 1: Biomarker Name
            # Line 2: "NEW"
            # Line 3: Status + Value + Unit
            if (next_line == "NEW" and i + 2 < len(lines)):
                third_line = lines[i + 2].strip()
                status_match = self._parse_status_line(third_line)
                if status_match:
                    marker_name = self._clean_marker_name(current_line)
                    status, value, unit = status_match
                    
                    # Validate this looks like a real biomarker
                    if self._is_valid_function_health_extraction(marker_name, value):
                        if include_ranges:
                            min_range, max_range = self._infer_range_from_status(status, value)
                            all_results.append((marker_name, value, min_range, max_range))
                        else:
                            all_results.append((marker_name, value))
                    
                    # Skip the next two lines since we processed them
                    i += 3
                    continue
            
            # Check if next line matches a status pattern (standard two-line format)
            status_match = self._parse_status_line(next_line)
            if status_match:
                marker_name = self._clean_marker_name(current_line)
                status, value, unit = status_match
                
                # Validate this looks like a real biomarker
                if self._is_valid_function_health_extraction(marker_name, value):
                    if include_ranges:
                        # Function Health doesn't provide reference ranges, 
                        # but we can infer from status
                        min_range, max_range = self._infer_range_from_status(status, value)
                        all_results.append((marker_name, value, min_range, max_range))
                    else:
                        all_results.append((marker_name, value))
                
                # Skip the next line since we processed it
                i += 2
            else:
                i += 1
        
        # Remove duplicates while preserving order
        return self._remove_duplicates_preserve_order(all_results), []
    
    def _should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped."""
        skip_patterns = [
            # Header patterns
            r'^\d+/\d+/\d+.*pm.*function dashboard',
            r'^your health.*function dashboard',
            r'^https://my\.functionhealth\.com',
            r'^\d+biomarkers',
            r'^in range out of range improving',
            r'^\d+\s+\d+\s+\d+$',  # Status counts
            
            # Navigation and category headers
            r'^autoimmunity$', r'^biological age$', r'^blood$', r'^electrolytes$',
            r'^environmental toxins$', r'^heart$', r'^immune regulation$', r'^kidney$',
            r'^liver$', r'^male health$', r'^metabolic$', r'^nutrients$', r'^pancreas$',
            r'^stress & aging$', r'^thyroid$', r'^urine$',
            
            # Page elements
            r'^page \d+ of \d+$',
            r'^\d+/\d+/\d+.*\d+:\d+\s+[ap]m$',
            
            # Very short lines that are likely not biomarkers
            r'^.{1,2}$',
        ]
        
        return any(re.search(pattern, line.lower()) for pattern in skip_patterns)
    
    def _extract_concatenated_biomarkers(self, line: str, include_ranges: bool = False) -> List[Tuple]:
        """Extract biomarkers from concatenated lines with multiple NEW markers."""
        # Look for pattern: NEWBiomarkerNameInRangeValueUnit repeated multiple times
        # Example: "NEWNEWNEWNEWNEWNEWNEWIron Binding CapacityIn Range312mcg/dL (calc)MagnesiumIn Range4.7mg/dLOmega 3 Total / OmegaCheckIn Range5.6% by wt"
        
        if 'NEW' not in line or 'In Range' not in line:
            return []
        
        results = []
        
        # Split on "NEW" and process each segment
        segments = line.split('NEW')
        
        for segment in segments:
            if not segment.strip():
                continue
            
            # Look for pattern: BiomarkerName + InRange/AboveRange/BelowRange + Value + Unit
            # Try different patterns to capture biomarker name, status, and value
            patterns = [
                # Pattern 1: Name + In Range + numeric value + unit
                r'^([A-Za-z][A-Za-z\s,\(\)\/-]+?)(In Range|Above Range|Below Range)([\d<>\.]+)\s*([a-zA-Z/%\(\)]+.*?)(?=[A-Z][a-z].*?(?:In Range|Above Range|Below Range)|$)',
                
                # Pattern 2: Name + In Range + numeric value (no unit)  
                r'^([A-Za-z][A-Za-z\s,\(\)\/-]+?)(In Range|Above Range|Below Range)([\d<>\.]+)(?=[A-Z][a-z].*?(?:In Range|Above Range|Below Range)|$)',
                
                # Pattern 3: Name + In Range + value with spaces + unit
                r'^([A-Za-z][A-Za-z\s,\(\)\/-]+?)(In Range|Above Range|Below Range)([\d<>\.\s]+)\s*([a-zA-Z/%\(\)]+.*?)(?=[A-Z][a-z].*?(?:In Range|Above Range|Below Range)|$)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, segment)
                for match in matches:
                    marker_name = match.group(1).strip()
                    status = match.group(2)
                    value = match.group(3).strip()
                    unit = match.group(4).strip() if len(match.groups()) > 3 else ""
                    
                    # Clean up the marker name
                    marker_name = self._clean_marker_name(marker_name)
                    
                    # Clean up the value (remove extra spaces)
                    value = re.sub(r'\s+', '', value)
                    
                    # Validate the extraction
                    if self._is_valid_function_health_extraction(marker_name, value):
                        if include_ranges:
                            min_range, max_range = self._infer_range_from_status(status, value)
                            results.append((marker_name, value, min_range, max_range))
                        else:
                            results.append((marker_name, value))
                break  # Found a match, move to next segment
        
        return results
    
    def _parse_status_line(self, line: str) -> Tuple[str, str, str]:
        """Parse status line to extract status, value, and unit."""
        # First try patterns for normal text
        # Pattern 1: Numeric with unit - "In Range 14.3 g/dL"
        match = re.match(r'^(In Range|Above Range|Below Range|Younger)\s+(-?\d+\.?\d*)\s+(.+)$', line)
        if match:
            return match.group(1), match.group(2), match.group(3)
        
        # Pattern 2: Percentage - "In Range 43.9 %"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+(\d+\.?\d*)\s*%$', line)
        if match:
            return match.group(1), match.group(2), "%"
        
        # Pattern 3: Less than values - "In Range <10 IU/mL"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+(<\d+\.?\d*)\s+(.+)$', line)
        if match:
            return match.group(1), match.group(2), match.group(3)
        
        # Pattern 3a: Numeric value without unit - "In Range 7.6"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+(\d+\.?\d*)$', line)
        if match:
            return match.group(1), match.group(2), ""
        
        # Pattern 4: Qualitative results - "In Range Negative"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+(Negative|Positive|Normal|Abnormal)$', line)
        if match:
            return match.group(1), match.group(2), ""
        
        # Pattern 5: Special values like blood type - "In Range O"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+([A-Z]+)$', line)
        if match:
            return match.group(1), match.group(2), ""
        
        # Pattern 6: Color values - "In Range Yellow"
        match = re.match(r'^(In Range|Above Range|Below Range)\s+(Yellow|Clear|Red|Brown|Orange)$', line)
        if match:
            return match.group(1), match.group(2), ""
        
        # Now try patterns for spaced text (e.g., "I n  R a n g e 1 4 . 3 g/dL")
        # Pattern 7: Spaced numeric with unit - "I n  R a n g e 1 4 . 3 g/dL"
        match = re.match(r'^(I n\s+R a n g e|A b o v e\s+R a n g e|B e l o w\s+R a n g e|Y o u n g e r)\s+([\d\s\.]+)\s+(.+)$', line)
        if match:
            status = match.group(1).replace(' ', '')  # "InRange"
            # Convert status back to normal format
            status_map = {'InRange': 'In Range', 'AboveRange': 'Above Range', 'BelowRange': 'Below Range', 'Younger': 'Younger'}
            status = status_map.get(status, status)
            value = match.group(2).replace(' ', '')  # "14.3"
            unit = match.group(3)
            return status, value, unit
        
        # Pattern 8: Spaced qualitative - "I n  R a n g e N e g a t i v e"
        match = re.match(r'^(I n\s+R a n g e|A b o v e\s+R a n g e|B e l o w\s+R a n g e)\s+(N e g a t i v e|P o s i t i v e)$', line)
        if match:
            status = match.group(1).replace(' ', '')
            status_map = {'InRange': 'In Range', 'AboveRange': 'Above Range', 'BelowRange': 'Below Range'}
            status = status_map.get(status, status)
            value = match.group(2).replace(' ', '')  # "Negative"
            return status, value, ""
        
        return None
    
    def _clean_marker_name(self, marker_name: str) -> str:
        """Clean and standardize marker names."""
        # Remove common prefixes/suffixes that aren't part of the marker name
        marker_name = marker_name.strip()
        
        # Handle spaced text - remove extra spaces between characters
        # e.g., "H e m o g l o b i n" -> "Hemoglobin"
        if re.match(r'^[A-Z]\s+[a-z]', marker_name):
            marker_name = re.sub(r'\s+', '', marker_name)
        
        # Handle special cases
        replacements = {
            'HDL-c': 'HDL-C',
            'LDL-c': 'LDL-C',
            'TSH (Thyroid Stimulating Hormone)': 'TSH',
            'T4 (Thyroxine), Free': 'Free T4',
            'T3 (Triiodothyronine), Free': 'Free T3',
            # Add spaced versions
            'Hemoglobin': 'Hemoglobin',
            'MeanCorpuscularVolume(MCV)': 'Mean Corpuscular Volume (MCV)',
            'TotalCholesterol': 'Total Cholesterol',
            'LDL-Cholesterol': 'LDL-Cholesterol',
            'TestosteroneTotal': 'Testosterone, Total',
        }
        
        return replacements.get(marker_name, marker_name)
    
    def _is_valid_function_health_extraction(self, marker: str, value: str) -> bool:
        """Validate Function Health extractions."""
        marker = marker.strip()
        value = value.strip()
        
        # Skip very short or empty markers
        if len(marker) < 2:
            return False
        
        # Skip if marker looks like a page element
        if re.match(r'^\d+$', marker):  # Just numbers
            return False
        
        if re.match(r'^page \d+', marker.lower()):
            return False
        
        # Skip if value is empty (unless it's a qualitative result)
        if not value:
            return False
        
        # Allow qualitative values
        qualitative_values = ['negative', 'positive', 'normal', 'abnormal', 'yellow', 'clear', 'o', 'a', 'b', 'ab']
        if value.lower() in qualitative_values:
            return True
        
        # For numeric values, basic validation
        if not re.match(r'^[<>]?\d+\.?\d*$', value.replace('<', '').replace('>', '')):
            # Allow special cases like blood types
            if value.upper() in ['O', 'A', 'B', 'AB']:
                return True
            return False
        
        return True
    
    def _infer_range_from_status(self, status: str, value: str) -> Tuple[str, str]:
        """Infer reference ranges from Function Health status indicators."""
        # Function Health doesn't provide explicit ranges, but we can make basic inferences
        # This is a simplified approach - could be enhanced with actual range data
        
        if status == "In Range":
            return "", ""  # Normal, no specific range to infer
        elif status == "Above Range":
            return "", value  # Value is above normal, so it's the minimum of "high"
        elif status == "Below Range":
            return value, ""  # Value is below normal, so it's the maximum of "low"
        else:
            return "", ""
    
    def _extract_date_from_header(self, text: str) -> str:
        """Extract date from Function Health header."""
        # Look for date pattern like "6/16/25, 4:07 PM"
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2}),?\s+\d{1,2}:\d{2}\s+[AP]M', text)
        if date_match:
            date_str = date_match.group(1)
            # Convert to standard format (assuming 2025 for 25)
            month, day, year = date_str.split('/')
            full_year = f"20{year}" if int(year) < 50 else f"19{year}"
            return f"{full_year}-{month.zfill(2)}-{day.zfill(2)}"
        return ""