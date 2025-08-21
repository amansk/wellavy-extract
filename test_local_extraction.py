#!/usr/bin/env python3
"""
Test the Wellavy AI extractor locally with detailed debugging.
"""

import os
import sys
import json
import logging
from dotenv import load_dotenv

# Load environment from parent project
load_dotenv('/Users/ak/code/wellavy/.env')

from wellavy_ai_extractor import WellavyAIExtractor

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample database markers (just a few for testing)
test_markers = [
    {"id": "be9a1341-7ce3-4e18-b3d8-4147d5bb6366", "name": "Glucose"},
    {"id": "b562e4ad-2f5d-4da6-8eb7-4b7ece904d69", "name": "Cholesterol, Total"},
    {"id": "6cbb6629-5ce1-448f-a895-fc4ce7c2942a", "name": "HDL Cholesterol"},
    {"id": "70c11fe4-5c16-4107-ae63-870003942910", "name": "LDL Cholesterol"},
    {"id": "33d639cc-367c-4742-8390-e7a2295f55c4", "name": "Triglycerides"},
    {"id": "340c24f2-6e6b-4ab8-9a3b-719d4b557d88", "name": "WBC"},
    {"id": "be73cf82-2b0f-48fe-bc5d-ff93db572bd9", "name": "Hemoglobin"},
    {"id": "d17ca469-9755-4826-8391-e3c379fd5d6a", "name": "TSH"},
    {"id": "7db64afc-2958-4f0a-9710-109b916b4da5", "name": "Creatinine"},
]

def test_extraction():
    pdf_path = "/Users/ak/Dropbox/Health/AK/Blood Tests/2025_July - AK labs - Wild Health.pdf"
    
    try:
        # Test WITH marker mapping
        logger.info("=" * 60)
        logger.info("Testing WITH marker mapping...")
        logger.info("=" * 60)
        
        extractor = WellavyAIExtractor(service="claude", database_markers=test_markers)
        
        # Get the prompt to see what we're sending
        prompt = extractor.create_extraction_prompt()
        logger.debug(f"Prompt length: {len(prompt)} characters")
        logger.debug(f"First 500 chars of prompt:\n{prompt[:500]}")
        
        # Extract
        logger.info("Calling Claude API...")
        results = extractor.extract(pdf_path)
        
        # Save raw response for debugging
        with open("test_response_mapped.json", "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"✅ Extraction successful!")
        logger.info(f"Results saved to test_response_mapped.json")
        
        # Show summary
        if 'results' in results:
            logger.info(f"Total markers extracted: {len(results['results'])}")
            
            # Count mapped vs unmapped
            mapped = [r for r in results['results'] if r.get('mapped_marker_id')]
            unmapped = [r for r in results['results'] if not r.get('mapped_marker_id')]
            
            logger.info(f"Successfully mapped: {len(mapped)}")
            logger.info(f"Unmapped: {len(unmapped)}")
            
            # Show first few examples
            logger.info("\nFirst 3 mapped markers:")
            for r in mapped[:3]:
                logger.info(f"  {r.get('original_marker')} → {r.get('mapped_marker_name')} (confidence: {r.get('confidence', 0)})")
            
            logger.info("\nFirst 3 unmapped markers:")
            for r in unmapped[:3]:
                logger.info(f"  {r.get('original_marker', r.get('marker'))} (no match)")
                
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Error position: line {e.lineno}, column {e.colno}")
        
        # Try to show the problematic part
        try:
            with open("test_response_mapped.json", "r") as f:
                lines = f.readlines()
                if e.lineno <= len(lines):
                    logger.error(f"Problematic line: {lines[e.lineno-1]}")
                    if e.lineno > 1:
                        logger.error(f"Previous line: {lines[e.lineno-2]}")
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error during extraction: {e}", exc_info=True)

if __name__ == "__main__":
    test_extraction()