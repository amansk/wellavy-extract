#!/usr/bin/env python3
"""
InBody AI Extractor for body composition analysis PDFs.
Specialized extractor for InBody 970 and similar body composition analyzers.
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path
from typing import Dict, List, Optional
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


class InBodyAIExtractor:
    """InBody-specific extractor for body composition analysis."""
    
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
        """Create a detailed prompt for InBody data extraction."""
        
        # If we have database markers, create mapping prompt
        if self.database_markers:
            marker_list = "\n".join([f"- {m['name']} (ID: {m['id']})" 
                                    for m in self.database_markers])
            
            return f"""Extract ONLY these specific metrics from the InBody report PDF:

Available database markers for mapping:
{marker_list}

INSTRUCTIONS:
1. Extract ONLY these 8 metrics:
   - Test Date
   - Weight
   - Lean Body Mass
   - Body Fat Mass
   - BMI
   - Percent Body Fat (PBF)
   - Visceral Fat Area
   - Skeletal Muscle Mass (SMM)

2. For each metric, try to match it to a database marker above
3. If matched: use the database marker name and ID
4. If NOT matched: use the exact InBody metric name and set ID to null
5. Return ONLY valid JSON, no markdown, no explanations

For each metric, provide:
{{
    "marker": "database name if matched, otherwise InBody metric name",
    "marker_id": "database ID if matched, otherwise null",
    "value": "numeric value",
    "unit": "unit of measurement if shown",
    "min_range": "min reference or null",
    "max_range": "max reference or null"
}}

Return this exact JSON structure:
{{
    "success": true,
    "test_date": "YYYY-MM-DD or null",
    "device": "InBody model if shown",
    "patient_info": {{
        "age": "age or null",
        "gender": "gender or null",
        "height": "height or null"
    }},
    "results": [array of ALL metrics]
}}

CRITICAL: Return ONLY the JSON object. No text before or after."""
        
        else:
            # Prompt without mapping for InBody
            return """Extract ONLY these specific metrics from the InBody report PDF:
1. Test Date
2. Weight
3. Lean Body Mass
4. Body Fat Mass
5. BMI
6. Percent Body Fat (PBF)
7. Visceral Fat Area
8. Skeletal Muscle Mass (SMM)

Format the output as JSON with this structure:
{
    "success": true,
    "test_date": "YYYY-MM-DD or null",
    "device": "InBody model if shown",
    "patient_info": {
        "age": "age or null",
        "gender": "gender or null", 
        "height": "height or null"
    },
    "results": [
        {
            "marker": "metric name",
            "value": "numeric value",
            "unit": "unit of measurement",
            "min_range": "minimum reference value or null",
            "max_range": "maximum reference value or null"
        }
    ]
}

Important guidelines:
- Extract ONLY the 8 metrics listed above
- Use these exact marker names:
  - "Weight"
  - "Lean Body Mass"
  - "Body Fat Mass"
  - "BMI"
  - "Percent Body Fat"
  - "Visceral Fat Area"
  - "Skeletal Muscle Mass"
- Include units (lb, kg, %, cm², etc.)
- Include reference ranges if shown
- Return ONLY valid JSON"""
    
    def extract_with_claude(self, pdf_base64: str) -> Dict:
        """Extract data using Claude."""
        prompt = self.create_extraction_prompt()
        
        logger.info(f"Processing InBody report with Claude")
        logger.info(f"Number of database markers: {len(self.database_markers)}")
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
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
            logger.info(f"Claude response length: {len(content)} characters")
            
            # Find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    result = json.loads(json_str)
                    
                    # Add mapping statistics
                    if self.database_markers and result.get("results"):
                        mapped_count = sum(1 for r in result["results"] if r.get("marker_id"))
                        unmapped_count = len(result["results"]) - mapped_count
                        
                        result["mapping_stats"] = {
                            "total_extracted": len(result["results"]),
                            "successfully_mapped": mapped_count,
                            "unmapped": unmapped_count
                        }
                        
                        # Log unmapped markers for analysis
                        unmapped_markers = [r["marker"] for r in result["results"] if not r.get("marker_id")]
                        if unmapped_markers:
                            logger.info(f"Unmapped InBody metrics: {', '.join(unmapped_markers[:10])}")
                    
                    return result
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    # Save for debugging
                    with open("inbody_failed_response.json", "w") as f:
                        f.write(json_str)
                    raise
            else:
                logger.error("No JSON found in Claude response")
                return {"success": False, "results": [], "test_date": None}
                
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
                    {"role": "system", "content": "You are a medical data extraction assistant specialized in InBody reports. Always respond with valid JSON."},
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
            
            result = json.loads(response.choices[0].message.content)
            
            # Add mapping statistics if using database markers
            if self.database_markers and result.get("results"):
                mapped_count = sum(1 for r in result["results"] if r.get("marker_id"))
                unmapped_count = len(result["results"]) - mapped_count
                
                result["mapping_stats"] = {
                    "total_extracted": len(result["results"]),
                    "successfully_mapped": mapped_count,
                    "unmapped": unmapped_count
                }
            
            return result
                
        except Exception as e:
            logger.error(f"Error with OpenAI extraction: {e}")
            raise
    
    def extract(self, pdf_path: str) -> Dict:
        """Extract InBody data from PDF using selected AI service."""
        # Encode PDF as base64
        pdf_base64 = self.encode_pdf_to_base64(pdf_path)
        
        # Extract using appropriate service
        if self.service == "claude":
            return self.extract_with_claude(pdf_base64)
        else:  # openai
            return self.extract_with_openai(pdf_base64)
    
    def format_results_as_csv(self, results: Dict, include_units: bool = True) -> str:
        """Format extraction results as CSV."""
        lines = []
        
        # Add header
        if include_units:
            lines.append("Metric,Value,Unit,MinRange,MaxRange")
        else:
            lines.append("Metric,Value,MinRange,MaxRange")
        
        # Add results
        for result in results.get("results", []):
            marker = result.get("marker", "")
            value = result.get("value", "")
            unit = result.get("unit", "")
            min_range = result.get("min_range", "")
            max_range = result.get("max_range", "")
            
            if include_units:
                lines.append(f'"{marker}","{value}","{unit}","{min_range}","{max_range}"')
            else:
                lines.append(f'"{marker}","{value}","{min_range}","{max_range}"')
        
        return "\n".join(lines)


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--service', '-s', type=click.Choice(['claude', 'openai', 'gpt4o']), 
              default='claude', help='AI service to use for extraction')
@click.option('--output', '-o', type=click.Path(), 
              help='Output file path (defaults to input filename with .json extension)')
@click.option('--csv', 'output_csv', is_flag=True, 
              help='Output as CSV instead of JSON')
@click.option('--markers', '-m', type=click.Path(exists=True),
              help='JSON file containing database markers for mapping')
def main(pdf_path: str, service: str, output: Optional[str], output_csv: bool, markers: Optional[str]):
    """Extract InBody composition data from PDF using AI services."""
    try:
        # Load database markers if provided
        database_markers = []
        if markers:
            with open(markers, 'r') as f:
                database_markers = json.load(f)
            logger.info(f"Loaded {len(database_markers)} database markers")
        
        # Initialize extractor
        if service == 'gpt4o':
            service = 'openai'
        extractor = InBodyAIExtractor(service=service, database_markers=database_markers)
        
        logger.info(f"Processing InBody report: {pdf_path} with {service}...")
        
        # Extract data
        results = extractor.extract(pdf_path)
        
        # Determine output path
        if not output:
            output = Path(pdf_path).stem + ('.csv' if output_csv else '.json')
        
        # Save results
        if output_csv:
            csv_content = extractor.format_results_as_csv(results)
            with open(output, 'w') as f:
                f.write(csv_content)
            logger.info(f"Results saved to {output}")
        else:
            with open(output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output}")
            
        # Print summary
        num_results = len(results.get("results", []))
        test_date = results.get("test_date", "Unknown")
        device = results.get("device", "Unknown")
        logger.info(f"Extracted {num_results} metrics from InBody {device} report dated {test_date}")
        
        if results.get("mapping_stats"):
            stats = results["mapping_stats"]
            logger.info(f"Mapping: {stats['successfully_mapped']}/{stats['total_extracted']} markers mapped to database")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()