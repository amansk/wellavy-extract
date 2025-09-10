#!/usr/bin/env python3
"""
Smart AI Extractor that automatically detects PDF type and routes to appropriate extractor.
Supports blood tests, InBody reports, and other health document types.
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

# Import specialized extractors
from wellavy_ai_extractor import WellavyAIExtractor
from inbody_ai_extractor import InBodyAIExtractor

# Setup logging
try:
    from logging_config import get_logger
    logger = get_logger("smart-ai-extractor")
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


class SmartAIExtractor:
    """Smart extractor that automatically detects PDF type and routes to appropriate extractor."""
    
    def __init__(self, service: str = "claude", database_markers: Optional[List[Dict]] = None,
                 request_id: Optional[str] = None, filename: Optional[str] = None):
        self.service = service.lower()
        self.database_markers = database_markers or []
        self.request_id = request_id
        self.filename = filename
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
    
    def detect_pdf_type(self, pdf_base64: str) -> Tuple[str, Dict]:
        """Detect the type of health document using AI."""
        
        detection_prompt = """Analyze this PDF and determine what type of health document it is.

Return ONLY a JSON object with this structure:
{
    "document_type": "blood_test" or "inbody" or "unsupported",
    "lab_name": "name of lab or device manufacturer if identifiable",
    "confidence": "high" or "medium" or "low",
    "indicators": ["list of key indicators that led to this classification"]
}

Classification rules:
- "blood_test": Contains blood markers like glucose, cholesterol, CBC, metabolic panel, vitamins, hormones
- "inbody": Body composition analysis with metrics like body fat %, muscle mass, visceral fat, impedance
- "unsupported": Any other document type that we don't currently support

Return ONLY the JSON object, no explanations."""

        try:
            if self.service == "claude":
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    temperature=0,
                    messages=[
                        {
                            "role": "user", 
                            "content": [
                                {
                                    "type": "text",
                                    "text": detection_prompt
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
                
                content = response.content[0].text
                
            else:  # OpenAI
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "You are a medical document classifier. Always respond with valid JSON."},
                        {
                            "role": "user", 
                            "content": [
                                {
                                    "type": "text",
                                    "text": detection_prompt
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
                
                content = response.choices[0].message.content
            
            # Parse JSON response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                detection_result = json.loads(json_str)
                
                logger.info(f"Detected document type: {detection_result.get('document_type', 'unknown')}")
                logger.info(f"Lab/Device: {detection_result.get('lab_name', 'unknown')}")
                logger.info(f"Confidence: {detection_result.get('confidence', 'unknown')}")
                logger.info(f"Indicators: {', '.join(detection_result.get('indicators', [])[:5])}")
                
                return detection_result.get('document_type', 'unknown'), detection_result
            
        except Exception as e:
            logger.error(f"Error detecting PDF type: {e}")
            return 'unknown', {"error": str(e)}
            
        return 'unknown', {"error": "Unable to parse detection response"}
    
    def extract(self, pdf_path: str) -> Dict:
        """Extract data from PDF using appropriate specialized extractor."""
        
        # Encode PDF
        pdf_base64 = self.encode_pdf_to_base64(pdf_path)
        
        # Detect document type
        logger.info(f"Analyzing PDF type for: {Path(pdf_path).name}")
        doc_type, detection_info = self.detect_pdf_type(pdf_base64)
        
        # Route to appropriate extractor
        if doc_type == "inbody":
            logger.info("Routing to InBody extractor...")
            extractor = InBodyAIExtractor(
                service=self.service,
                database_markers=self.database_markers
                # Note: InBodyAIExtractor doesn't support request_id/filename yet
            )
            results = extractor.extract(pdf_path)
            
        elif doc_type == "blood_test":
            logger.info("Routing to blood test extractor...")
            extractor = WellavyAIExtractor(
                service=self.service,
                database_markers=self.database_markers,
                request_id=self.request_id,
                filename=self.filename
            )
            results = extractor.extract(pdf_path)
            
        else:
            # For unsupported document types, return an error
            logger.warning(f"Unsupported document type: '{doc_type}'")
            results = {
                "success": False,
                "error": f"Document type '{doc_type}' is not supported. Only blood tests and InBody reports are currently supported.",
                "results": []
            }
        
        # Add detection metadata to results
        results["document_detection"] = detection_info
        results["extractor_used"] = doc_type if doc_type in ["inbody", "blood_test"] else "blood_test (fallback)"
        
        return results
    
    def format_results_as_csv(self, results: Dict, include_ranges: bool = False) -> str:
        """Format extraction results as CSV."""
        lines = []
        
        # Determine if this is InBody data (has units) or blood test data
        has_units = any(r.get("unit") for r in results.get("results", []))
        
        # Add header
        if has_units:  # InBody format
            if include_ranges:
                lines.append("Metric,Value,Unit,MinRange,MaxRange")
            else:
                lines.append("Metric,Value,Unit")
        else:  # Blood test format
            if include_ranges:
                lines.append("Test Name,Value,MinRange,MaxRange")
            else:
                lines.append("Test Name,Value")
        
        # Add results
        for result in results.get("results", []):
            marker = result.get("marker", "")
            value = result.get("value", "")
            
            if has_units:
                unit = result.get("unit", "")
                if include_ranges:
                    min_range = result.get("min_range", "")
                    max_range = result.get("max_range", "")
                    lines.append(f'"{marker}","{value}","{unit}","{min_range}","{max_range}"')
                else:
                    lines.append(f'"{marker}","{value}","{unit}"')
            else:
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
              help='Output file path (defaults to input filename with .json extension)')
@click.option('--csv', 'output_csv', is_flag=True, 
              help='Output as CSV instead of JSON')
@click.option('--include-ranges', '-r', is_flag=True, 
              help='Include reference ranges in output')
@click.option('--markers', '-m', type=click.Path(exists=True),
              help='JSON file containing database markers for mapping')
def main(pdf_path: str, service: str, output: Optional[str], output_csv: bool, 
         include_ranges: bool, markers: Optional[str]):
    """Smart extraction of health data from PDFs with automatic type detection."""
    try:
        # Load database markers if provided
        database_markers = []
        if markers:
            with open(markers, 'r') as f:
                database_markers = json.load(f)
            logger.info(f"Loaded {len(database_markers)} database markers")
        
        # Initialize smart extractor
        if service == 'gpt4o':
            service = 'openai'
        extractor = SmartAIExtractor(service=service, database_markers=database_markers)
        
        logger.info(f"Processing: {Path(pdf_path).name} with {service}...")
        
        # Extract data with automatic routing
        results = extractor.extract(pdf_path)
        
        # Determine output path
        if not output:
            output = Path(pdf_path).stem + ('.csv' if output_csv else '.json')
        
        # Save results
        if output_csv:
            csv_content = extractor.format_results_as_csv(results, include_ranges)
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
        doc_type = results.get("document_detection", {}).get("document_type", "Unknown")
        extractor_used = results.get("extractor_used", "Unknown")
        
        logger.info(f"Document type: {doc_type}")
        logger.info(f"Extractor used: {extractor_used}")
        logger.info(f"Extracted {num_results} markers/metrics dated {test_date}")
        
        if results.get("mapping_stats"):
            stats = results["mapping_stats"]
            logger.info(f"Mapping: {stats['successfully_mapped']}/{stats['total_extracted']} markers mapped to database")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()