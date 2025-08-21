#!/usr/bin/env python3
"""
Wellavy-specific AI extractor with intelligent marker mapping.
This extractor is designed to work with Wellavy's blood marker database.
"""

import os
import json
import base64
import logging
from typing import Dict, List, Optional
from pathlib import Path
import click

# Try importing AI libraries
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WellavyAIExtractor:
    """AI-powered blood test extractor with database marker mapping."""
    
    def __init__(self, service: str = "claude", database_markers: Optional[List[Dict]] = None):
        """
        Initialize the Wellavy AI extractor.
        
        Args:
            service: AI service to use ('claude' or 'openai')
            database_markers: List of database markers for mapping
                             Each marker should have 'id' and 'name' keys
        """
        self.service = service.lower()
        self.database_markers = database_markers or []
        self.client = self._init_client()
        
    def _init_client(self):
        """Initialize the appropriate AI client based on service selection."""
        if self.service == "claude":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            return anthropic.Anthropic(api_key=api_key)
            
        elif self.service in ["openai", "gpt4o", "gpt-4o"]:
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed. Run: pip install openai")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            return OpenAI(api_key=api_key)
            
        else:
            raise ValueError(f"Unsupported service: {self.service}. Use 'claude' or 'openai'")
    
    def encode_pdf_to_base64(self, pdf_path: str) -> str:
        """Encode PDF file to base64 string."""
        with open(pdf_path, 'rb') as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')
    
    def create_extraction_prompt_with_mapping(self) -> str:
        """Create a detailed prompt for AI extraction with marker mapping."""
        
        # If we have database markers, include mapping instructions
        if self.database_markers:
            # Create a formatted list of available markers
            marker_list = "\n".join([f"- {m['name']} (ID: {m['id']})" 
                                    for m in self.database_markers])
            
            return f"""Extract all blood test results from the provided lab report PDF and map them to our database markers.

AVAILABLE DATABASE MARKERS:
{marker_list}

TASK:
1. Extract every blood test marker from the PDF
2. For each marker, capture the exact name as it appears in the PDF
3. Extract the numeric value (remove units)
4. Extract reference ranges if available
5. Map each marker to the most appropriate database marker from the list above
6. Assign a confidence score (0.0-1.0) for each mapping

MAPPING RULES:
- Match intelligently, ignoring minor variations in punctuation, spacing, and word order
- Common mappings to remember:
  * "Cholesterol Total" or "Total Cholesterol" → "Cholesterol, Total"
  * "White Blood Cell Count" or "WBC Count" → "WBC"
  * "Red Blood Cell Count" or "RBC Count" → "RBC"
  * "Hemoglobin A1c" or "HbA1c" or "Glycated Hemoglobin" → Match to HbA1c if in database
  * "Testosterone Total" or "Total Testosterone" → "Testosterone, Total"
  * "Testosterone Free" or "Free Testosterone" → "Testosterone, Free"
  * "Carbon Dioxide" or "CO2" → "CO2 (Bicarbonate)"
  * "C-Reactive Protein" or "CRP" → Match to CRP/hs-CRP variant in database
  * "Vitamin D 25-OH Total" or "25-Hydroxyvitamin D" → "Vitamin D"
  * "T4 Free" or "Free T4" or "Thyroxine Free" → Match to Free T4 if in database
  * "T3 Free" or "Free T3" or "Triiodothyronine Free" → Match to Free T3 if in database
  * "Sex Hormone Binding Globulin" or "SHBG" → Match to SHBG if in database
  * "Alkaline Phosphatase" or "ALP" → Match to ALP if in database
  * "Urea Nitrogen" or "BUN" or "Blood Urea Nitrogen" → Match to BUN if in database
  * "Protein Total" or "Total Protein" → Match to Total Protein if in database
  * "Bilirubin Total" or "Total Bilirubin" → Match to appropriate bilirubin marker

- If no good match exists (confidence < 0.5), set mapped_marker_name and mapped_marker_id to null
- Percentage markers (like "Neutrophils %") should map to percentage variants if they exist
- Absolute counts should map to absolute variants (like "Absolute Neutrophils")

OUTPUT FORMAT (JSON):
{{
    "success": true,
    "test_date": "MM/DD/YYYY or null if not found",
    "lab_name": "detected lab name or null",
    "results": [
        {{
            "original_marker": "exact name from PDF",
            "value": "numeric value as string",
            "unit": "unit if found or null",
            "min_range": "minimum reference value or null",
            "max_range": "maximum reference value or null",
            "mapped_marker_name": "exact database marker name or null",
            "mapped_marker_id": "database marker UUID or null",
            "confidence": 0.95
        }}
    ]
}}

IMPORTANT:
- Include ALL markers found in the PDF, even if they don't map to database markers
- Preserve exact marker names from the PDF in "original_marker"
- Return numeric values as strings to preserve precision
- Set confidence to 0.0 for unmapped markers
- Extract test date in MM/DD/YYYY format if found
"""
        else:
            # Fallback to simple extraction without mapping
            return """Extract all blood test results from the provided lab report PDF.

For each marker found, extract:
1. The marker name exactly as it appears
2. The numeric value (as string to preserve precision)
3. The unit if available
4. The reference range if available

OUTPUT FORMAT (JSON):
{
    "success": true,
    "test_date": "MM/DD/YYYY or null if not found",
    "lab_name": "detected lab name or null",
    "results": [
        {
            "original_marker": "exact marker name",
            "value": "numeric value as string",
            "unit": "unit or null",
            "min_range": "minimum reference or null",
            "max_range": "maximum reference or null"
        }
    ]
}

Extract ALL markers found in the report, preserving exact names and values."""
    
    def extract_with_claude(self, pdf_base64: str) -> Dict:
        """Extract data using Claude with marker mapping."""
        prompt = self.create_extraction_prompt_with_mapping()
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            }
                        ]
                    }
                ]
            )
            
            # Parse the response
            response_text = message.content[0].text
            
            # Try to extract JSON from the response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            return json.loads(json_str)
                
        except Exception as e:
            logger.error(f"Error with Claude extraction: {e}")
            raise
    
    def extract_with_openai(self, pdf_base64: str) -> Dict:
        """Extract data using OpenAI with marker mapping."""
        prompt = self.create_extraction_prompt_with_mapping()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a medical data extraction assistant. Always respond with valid JSON."},
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:application/pdf;base64,{pdf_base64}"
                                }
                            }
                        ]
                    }
                ]
            )
            
            return json.loads(response.choices[0].message.content)
                
        except Exception as e:
            logger.error(f"Error with OpenAI extraction: {e}")
            raise
    
    def extract(self, pdf_path: str) -> Dict:
        """
        Extract blood test data from PDF with optional marker mapping.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with extraction results including mapped markers
        """
        # Encode PDF as base64
        pdf_base64 = self.encode_pdf_to_base64(pdf_path)
        
        # Extract using appropriate service
        if self.service == "claude":
            results = self.extract_with_claude(pdf_base64)
        else:  # openai
            results = self.extract_with_openai(pdf_base64)
        
        # Add metadata
        results['extraction_service'] = self.service
        results['markers_mapped'] = len(self.database_markers) > 0
        
        # Calculate mapping statistics
        if self.database_markers and 'results' in results:
            mapped_count = sum(1 for r in results['results'] 
                             if r.get('mapped_marker_id') is not None)
            unmapped_count = len(results['results']) - mapped_count
            
            results['mapping_stats'] = {
                'total_extracted': len(results['results']),
                'successfully_mapped': mapped_count,
                'unmapped': unmapped_count,
                'mapping_rate': mapped_count / len(results['results']) if results['results'] else 0
            }
        
        return results


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--service', '-s', type=click.Choice(['claude', 'openai']), 
              default='claude', help='AI service to use')
@click.option('--markers-file', '-m', type=click.Path(exists=True),
              help='JSON file containing database markers for mapping')
@click.option('--output', '-o', type=click.Path(),
              help='Output JSON file path')
def main(pdf_path: str, service: str, markers_file: Optional[str], output: Optional[str]):
    """Extract blood test results with intelligent marker mapping."""
    
    # Load database markers if provided
    database_markers = []
    if markers_file:
        with open(markers_file, 'r') as f:
            database_markers = json.load(f)
        logger.info(f"Loaded {len(database_markers)} database markers for mapping")
    
    # Initialize extractor
    extractor = WellavyAIExtractor(service=service, database_markers=database_markers)
    
    logger.info(f"Processing {pdf_path} with {service}...")
    
    # Extract data
    results = extractor.extract(pdf_path)
    
    # Output results
    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output}")
    else:
        print(json.dumps(results, indent=2))
    
    # Print summary
    if 'mapping_stats' in results:
        stats = results['mapping_stats']
        logger.info(f"Extraction complete: {stats['total_extracted']} markers found")
        logger.info(f"Mapped: {stats['successfully_mapped']}, Unmapped: {stats['unmapped']}")


if __name__ == "__main__":
    main()