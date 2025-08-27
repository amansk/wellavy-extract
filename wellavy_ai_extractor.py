#!/usr/bin/env python3
"""
Wellavy AI Extractor with intelligent marker mapping for blood test PDFs.
Based on the working unified_ai_extractor with added database marker mapping.
"""

import os
import sys
import json
import base64
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import click
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Import AI service clients
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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WellavyAIExtractor:
    """Wellavy extractor with intelligent database marker mapping."""
    
    def __init__(self, service: str = "claude", database_markers: Optional[List[Dict]] = None):
        self.service = service.lower()
        self.database_markers = database_markers or []
        self.client = self._initialize_client()
        
    def _initialize_client(self):
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
    
    def create_extraction_prompt(self) -> str:
        """Create a detailed prompt for AI extraction with optional marker mapping."""
        
        # If we have database markers, create mapping prompt
        if self.database_markers:
            # Use all database markers for comprehensive mapping
            marker_list = "\n".join([f"- {m['name']} (ID: {m['id']})" 
                                    for m in self.database_markers])
            
            return f"""Extract ALL blood test results from the PDF. Map to database markers where possible.

Available database markers for mapping:
{marker_list}

INSTRUCTIONS:
1. Extract ALL test results from the PDF
2. For each result, try to match it to a database marker above
3. If matched: use the database marker name and ID
4. If NOT matched: use the PDF marker name in Title Case (e.g., "Vitamin D Total") and set ID to null
5. Return ONLY valid JSON, no markdown, no explanations

For each test result, provide:
{{
    "marker": "database name if matched, otherwise PDF name in Title Case",
    "marker_id": "database ID if matched, otherwise null",
    "value": "numeric value",
    "min_range": "min reference or null",
    "max_range": "max reference or null"
}}

Return this exact JSON structure:
{{
    "success": true,
    "test_date": "YYYY-MM-DD or null",
    "results": [array of ALL test results]
}}

Example results:
- Matched: {{"marker": "Glucose", "marker_id": "be9a1341-7ce3-4e18-b3d8-4147d5bb6366", "value": "95", ...}}
- Unmatched: {{"marker": "Vitamin D Total", "marker_id": null, "value": "32", ...}}

CRITICAL: Return ONLY the JSON object. No text before or after."""
        
        else:
            # Original prompt without mapping
            return """Extract all blood test results from the provided lab report PDF. 

For each marker found, extract:
1. The marker name (standardize common variations)
2. The value (numeric result)
3. The reference range (if available)

Format the output as JSON with this structure:
{
    "results": [
        {
            "marker": "marker name",
            "value": "numeric value",
            "min_range": "minimum reference value or null",
            "max_range": "maximum reference value or null"
        }
    ],
    "test_date": "date of test if found, or null"
}

Important guidelines:
- Standardize marker names (e.g., "Glucose, Fasting" → "Glucose")
- Include ALL markers found in the report
- For ranges like "10-50", set min_range="10" and max_range="50"
- For ranges like "<100", set min_range=null and max_range="100"
- For ranges like ">40", set min_range="40" and max_range=null
- Extract numeric values only (remove units)
- If no range is provided, set both min_range and max_range to null
"""
    
    def extract_with_claude(self, pdf_base64: str) -> Dict:
        """Extract data using Claude."""
        prompt = self.create_extraction_prompt()
        
        # Log prompt summary
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.info(f"Number of database markers: {len(self.database_markers)}")
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,  # Increased to handle larger responses
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
                                "type": "document",
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
            
            # Extract JSON from response
            content = response.content[0].text
            
            # Log response summary
            logger.info(f"Claude response length: {len(content)} characters")
            
            # Find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                
                # Try to parse, with better error handling
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    
                    # Try to clean common issues
                    # Remove trailing commas
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    # Fix missing commas between objects
                    json_str = re.sub(r'}\s*{', '},{', json_str)
                    # Remove any null bytes or special characters
                    json_str = json_str.replace('\x00', '').replace('\r', '')
                    
                    try:
                        return json.loads(json_str)
                    except Exception as parse_error:
                        logger.error(f"Failed to parse JSON response: {parse_error}")
                        raise
            else:
                logger.error("No JSON found in Claude response")
                return {"results": [], "test_date": None}
                
        except Exception as e:
            logger.error(f"Error with Claude extraction: {e}")
            raise
    
    def extract_with_openai(self, pdf_base64: str) -> Dict:
        """Extract data using OpenAI GPT-4o."""
        prompt = self.create_extraction_prompt()
        
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
        """Extract blood test data from PDF using selected AI service."""
        # Encode PDF as base64
        pdf_base64 = self.encode_pdf_to_base64(pdf_path)
        
        # Extract using appropriate service
        if self.service == "claude":
            return self.extract_with_claude(pdf_base64)
        else:  # openai
            return self.extract_with_openai(pdf_base64)
    
    def format_results_as_csv(self, results: Dict, include_ranges: bool = False) -> str:
        """Format extraction results as CSV."""
        lines = []
        
        # Add header
        if include_ranges:
            lines.append("Test Name,Value,MinRange,MaxRange")
        else:
            lines.append("Test Name,Value")
        
        # Add results
        for result in results.get("results", []):
            marker = result.get("marker", "")
            value = result.get("value", "")
            
            if include_ranges:
                min_range = result.get("min_range", "")
                max_range = result.get("max_range", "")
                lines.append(f'"{marker}","{value}","{min_range}","{max_range}"')
            else:
                lines.append(f'"{marker}","{value}"')
        
        return "\n".join(lines)


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--service', '-s', type=click.Choice(['claude', 'openai', 'gpt4o']), 
              default='claude', help='AI service to use for extraction')
@click.option('--output', '-o', type=click.Path(), 
              help='Output CSV file path (defaults to input filename with .csv extension)')
@click.option('--include-ranges', '-r', is_flag=True, 
              help='Include reference ranges in output')
@click.option('--json', 'output_json', is_flag=True, 
              help='Output raw JSON instead of CSV')
def main(pdf_path: str, service: str, output: Optional[str], include_ranges: bool, output_json: bool):
    """Extract blood test results from PDF using AI services."""
    try:
        # Initialize extractor
        if service == 'gpt4o':
            service = 'openai'
        extractor = WellavyAIExtractor(service=service)
        
        logger.info(f"Processing PDF: {Path(pdf_path).name} with {service}...")
        
        # Extract data
        results = extractor.extract(pdf_path)
        
        # Determine output path
        if not output:
            output = Path(pdf_path).stem + ('.json' if output_json else '.csv')
        
        # Save results
        if output_json:
            with open(output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output}")
        else:
            csv_content = extractor.format_results_as_csv(results, include_ranges)
            with open(output, 'w') as f:
                f.write(csv_content)
            logger.info(f"Results saved to {output}")
            
        # Print summary
        num_results = len(results.get("results", []))
        test_date = results.get("test_date", "Unknown")
        logger.info(f"Extracted {num_results} markers from test dated {test_date}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()