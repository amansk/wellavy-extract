#!/usr/bin/env python3
"""
Test script for AI extraction API endpoint.
"""

import requests
import sys
from pathlib import Path

def test_ai_extract_api(pdf_path: str, api_key: str, base_url: str = "http://localhost:8000"):
    """Test the AI extraction API endpoint."""
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"Error: File {pdf_path} not found")
        return
    
    # Prepare the request
    url = f"{base_url}/api/v1/ai-extract"
    headers = {
        "X-API-Key": api_key
    }
    
    # Include ranges parameter
    params = {
        "include_ranges": "true"
    }
    
    # Open and send the file
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        
        print(f"Sending request to {url}")
        print(f"Using API key: {api_key[:10]}...")
        
        try:
            response = requests.post(url, headers=headers, files=files, params=params)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ Success!")
                print(f"Test Date: {data.get('test_date', 'N/A')}")
                print(f"Markers Found: {data.get('marker_count', 0)}")
                print("\nFirst 5 results:")
                for i, result in enumerate(data.get('results', [])[:5], 1):
                    print(f"{i}. {result['marker']}: {result['value']}")
                    if 'min_range' in result:
                        print(f"   Range: {result.get('min_range', 'N/A')} - {result.get('max_range', 'N/A')}")
            
            elif response.status_code == 401:
                print("❌ Authentication failed - Invalid API key")
            
            elif response.status_code == 400:
                print(f"❌ Bad request: {response.json().get('detail', 'Unknown error')}")
            
            else:
                print(f"❌ Error: {response.json()}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Error: Could not connect to API. Is the server running?")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Example usage
    print("AI Extraction API Test")
    print("=" * 40)
    
    # You can modify these for testing
    test_pdf = "pdf_reports/ofer1.pdf"  # Change to any test PDF
    test_api_key = "test-api-key-123"  # This should match API_SECRET_KEY env var
    
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
    if len(sys.argv) > 2:
        test_api_key = sys.argv[2]
    
    test_ai_extract_api(test_pdf, test_api_key)