#!/usr/bin/env python3
"""
Unified AI Extractor for blood test PDFs using Claude and GPT-4o.
"""

import os
import sys
import json
import base64
import logging
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
try:
    from logging_config import get_logger
    logger = get_logger("unified-ai-extractor")
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


class UnifiedAIExtractor:
    """Unified extractor that uses AI services to extract blood test data."""
    
    def __init__(self, service: str = "claude"):
        self.service = service.lower()
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
        """Create a detailed prompt for AI extraction."""
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
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
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
            # Find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
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
        extractor = UnifiedAIExtractor(service=service)
        
        logger.info(f"Processing {pdf_path} with {service}...")
        
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