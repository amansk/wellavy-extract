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
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import click
from dotenv import load_dotenv

# Import PDF processing
try:
    import pdfplumber
    PDF_PROCESSING_AVAILABLE = True
except ImportError:
    PDF_PROCESSING_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

import io

# Import token counting utilities
try:
    from token_counter import (
        calculate_request_tokens, 
        check_token_limit,
        split_document_for_chunks,
        optimize_markers_for_document,
        TokenManager
    )
    TOKEN_COUNTING_AVAILABLE = True
except ImportError:
    TOKEN_COUNTING_AVAILABLE = False

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
    logger = get_logger("wellavy-ai-extractor")
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


class WellavyAIExtractor:
    """Wellavy extractor with intelligent database marker mapping."""
    
    def __init__(self, service: str = "claude", database_markers: Optional[List[Dict]] = None, token_limit: int = 30000,
                 request_id: Optional[str] = None, filename: Optional[str] = None):
        self.service = service.lower()
        self.database_markers = database_markers or []
        self.token_limit = token_limit
        self.request_id = request_id or "unknown"
        self.filename = filename or "unknown"
        self.client = self._initialize_client()
        self.token_manager = TokenManager(token_limit) if TOKEN_COUNTING_AVAILABLE else None
        
    def _log_with_context(self, level: str, message: str, **extra):
        """Log message with request context using structured logging."""
        context = {
            'request_id': self.request_id,
            'filename': self.filename,
            **extra
        }
        getattr(logger, level)(message, extra=context)
        
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
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using pdfplumber."""
        if not PDF_PROCESSING_AVAILABLE:
            raise ImportError("pdfplumber not available. Install with: pip install pdfplumber")
        
        text_content = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"=== PAGE {page_num} ===\n{page_text}\n")
                    
            return "\n".join(text_content)
        except Exception as e:
            self._log_with_context("error", f"Error extracting text from PDF: {e}")
            raise
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get the number of pages in a PDF."""
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2 required for PDF processing")
            
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            return len(reader.pages)
    
    def estimate_pdf_tokens(self, pdf_path: str) -> int:
        """
        Estimate token count for a PDF without extracting text.
        Blood test PDFs average ~3000 tokens per page when sent as PDF.
        """
        page_count = self.get_pdf_page_count(pdf_path)
        # Conservative estimate: 3000 tokens per page for blood test PDFs
        estimated_pdf_tokens = page_count * 3000
        
        # Add prompt and markers
        prompt_tokens = 4000  # Typical prompt size
        markers_tokens = len(str(self.database_markers)) // 3  # Rough estimate
        
        total_estimate = estimated_pdf_tokens + prompt_tokens + markers_tokens
        self._log_with_context("info", f"Estimated tokens - Pages: {page_count}, PDF: {estimated_pdf_tokens}, Total: {total_estimate}")
        
        return total_estimate
    
    def chunk_pdf_by_pages(self, pdf_path: str, max_pages_per_chunk: int = 5) -> List[str]:
        """
        Split a PDF into smaller PDFs by pages.
        Returns list of base64-encoded PDF chunks.
        """
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2 required for PDF chunking")
        
        chunks = []
        
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            
            # Calculate optimal pages per chunk
            # With ~3k tokens per page, 5 pages = 15k tokens
            # Plus 4k prompt + 5k markers = 24k total (under 30k limit)
            
            self._log_with_context("info", f"Splitting {total_pages} page PDF into chunks of {max_pages_per_chunk} pages")
            
            for start_page in range(0, total_pages, max_pages_per_chunk):
                end_page = min(start_page + max_pages_per_chunk, total_pages)
                
                # Create new PDF with subset of pages
                writer = PyPDF2.PdfWriter()
                for page_num in range(start_page, end_page):
                    writer.add_page(reader.pages[page_num])
                
                # Convert to base64
                pdf_bytes = io.BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)
                
                chunk_base64 = base64.b64encode(pdf_bytes.read()).decode('utf-8')
                chunks.append(chunk_base64)
                
                self._log_with_context("info", f"Created chunk {len(chunks)}: pages {start_page+1}-{end_page}")
        
        self._log_with_context("info", f"Split PDF into {len(chunks)} chunks")
        return chunks
    
    # DEPRECATED: Old text-based chunking - kept for compatibility
    def chunk_pdf_text(self, text: str, max_tokens_per_chunk: int = 18000) -> List[str]:
        """
        Split PDF text into chunks that fit within token limits.
        Leaves room for prompt + markers (~12k tokens).
        """
        if not TOKEN_COUNTING_AVAILABLE:
            # Fallback: split by character count (rough estimate)
            max_chars = max_tokens_per_chunk * 3  # ~3 chars per token
            chunks = []
            for i in range(0, len(text), max_chars):
                chunks.append(text[i:i + max_chars])
            return chunks
        
        # Split by pages first
        pages = text.split("=== PAGE")
        if len(pages) <= 1:
            # No page markers, split by paragraphs
            paragraphs = text.split('\n\n')
            pages = [f"PAGE 1 ===\n{text}"]  # Treat as single page
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for page in pages:
            if not page.strip():
                continue
                
            page_text = page if page.startswith(" ===") else f"=== PAGE{page}"
            page_tokens = len(page_text) // 3  # Rough estimate
            
            # If this page alone exceeds limit, split it further
            if page_tokens > max_tokens_per_chunk:
                # Save current chunk if it exists
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_tokens = 0
                
                # Split large page by sentences or paragraphs
                sentences = page_text.split('. ')
                page_chunk = ""
                
                for sentence in sentences:
                    sentence_tokens = len(sentence) // 3
                    if len(page_chunk) // 3 + sentence_tokens > max_tokens_per_chunk:
                        if page_chunk:
                            chunks.append(page_chunk)
                        page_chunk = sentence
                    else:
                        page_chunk += (". " if page_chunk else "") + sentence
                
                if page_chunk:
                    chunks.append(page_chunk)
                    
            elif current_tokens + page_tokens > max_tokens_per_chunk:
                # Current chunk + this page exceeds limit
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = page_text
                current_tokens = page_tokens
            else:
                # Add page to current chunk
                current_chunk += "\n" + page_text if current_chunk else page_text
                current_tokens += page_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        self._log_with_context("info", f"Split PDF into {len(chunks)} chunks")
        return chunks
    
    def create_chunk_extraction_prompt(self, chunk_number: int, total_chunks: int) -> str:
        """Create a prompt for extracting from a specific chunk."""
        base_prompt = self.create_extraction_prompt()
        
        # Add chunk context
        chunk_prefix = f"""
CHUNK PROCESSING: This is chunk {chunk_number} of {total_chunks} from the PDF.
Extract ALL test results found in this chunk. Other chunks will handle other parts.

"""
        
        return chunk_prefix + base_prompt
    
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
    
    def extract_with_claude(self, pdf_base64: str, pdf_path: str = None) -> Dict:
        """Extract data using Claude with token counting and chunking."""
        prompt = self.create_extraction_prompt()
        
        # Log prompt summary
        self._log_with_context("info", "Claude extraction started", 
                               prompt_length=len(prompt),
                               database_markers_count=len(self.database_markers))
        
        # Check token count if available
        if pdf_path and PYPDF2_AVAILABLE:
            # Use proper PDF token estimation (not text extraction!)
            estimated_tokens = self.estimate_pdf_tokens(pdf_path)
            
            # Check if within limits
            if estimated_tokens > self.token_limit:
                self._log_with_context("warning", f"Token limit exceeded: {estimated_tokens} > {self.token_limit}")
                return self._handle_large_document(pdf_path, {"total": estimated_tokens})
        elif TOKEN_COUNTING_AVAILABLE:
            # Fallback to old method if no pdf_path provided
            pdf_text_estimate = base64.b64decode(pdf_base64).decode('utf-8', errors='ignore')
            
            token_counts = calculate_request_tokens(
                prompt=prompt,
                pdf_text=pdf_text_estimate,
                database_markers=self.database_markers
            )
            
            self._log_with_context("info", f"Estimated tokens (fallback): {token_counts['total']}")
            
            within_limit, error_msg = check_token_limit(token_counts['total'], self.token_limit)
            
            if not within_limit:
                self._log_with_context("warning", f"Token limit exceeded: {error_msg}")
                if pdf_path:
                    return self._handle_large_document(pdf_path, token_counts)
                else:
                    self._log_with_context("error", "Cannot chunk without pdf_path")
                    raise ValueError("PDF path required for chunking")
            
            # Check if we have capacity in current window
            if self.token_manager and not self.token_manager.can_process(token_counts['total']):
                wait_time = 60  # Wait 60 seconds for rate limit window to reset
                self._log_with_context("info", f"Rate limit approaching, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                self.token_manager.reset()
            
            # Record usage
            if self.token_manager:
                self.token_manager.add_usage(token_counts['total'])
        
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
            
            # Log response summary with filename and full response
            self._log_with_context("info", "Claude extraction completed", 
                                   response_length=len(content))
            self._log_with_context("info", "Claude full response", 
                                   response_content=content)
            
            # Find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                
                # Try to parse, with better error handling
                try:
                    result = json.loads(json_str)
                    self._log_extraction_summary(self.filename, result)
                    return result
                except json.JSONDecodeError as e:
                    self._log_with_context("error", f"JSON decode error: {e}")
                    
                    # Try to clean common issues
                    # Remove trailing commas
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    # Fix missing commas between objects
                    json_str = re.sub(r'}\s*{', '},{', json_str)
                    # Remove any null bytes or special characters
                    json_str = json_str.replace('\x00', '').replace('\r', '')
                    
                    try:
                        result = json.loads(json_str)
                        self._log_extraction_summary(self.filename, result)
                        return result
                    except Exception as parse_error:
                        self._log_with_context("error", f"Failed to parse JSON response: {parse_error}")
                        raise
            else:
                self._log_with_context("error", "No JSON found in Claude response")
                result = {"results": [], "test_date": None}
                self._log_extraction_summary(self.filename, result)
                return result
                
        except Exception as e:
            self._log_with_context("error", f"Error with Claude extraction: {e}")
            raise
    
    def _log_extraction_summary(self, filename: str, result: Dict):
        """Log detailed extraction summary statistics."""
        results = result.get("results", [])
        
        # Count extraction statistics
        total_extracted = len(results)
        mapped_count = 0
        unmapped_count = 0
        failed_count = 0
        
        # Count mapped vs unmapped markers
        database_marker_names = set()
        if isinstance(self.database_markers, list):
            database_marker_names = {marker.get('name', '').lower() 
                                   for marker in self.database_markers 
                                   if marker.get('name')}
        
        for res in results:
            marker_name = res.get("marker", "").lower()
            value = res.get("value", "")
            
            if not value or value.lower() in ["", "not found", "n/a", "null"]:
                failed_count += 1
            elif marker_name in database_marker_names:
                mapped_count += 1
            else:
                unmapped_count += 1
        
        # Log comprehensive extraction summary
        self._log_with_context("info", "Extraction summary completed", 
                               total_extracted=total_extracted,
                               mapped=mapped_count,
                               unmapped=unmapped_count,
                               failed=failed_count)
    
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
            self._log_with_context("error", f"Error with OpenAI extraction: {e}")
            raise
    
    def _handle_large_document(self, pdf_path: str, token_counts: Dict) -> Dict:
        """Handle documents that exceed token limits using PDF page chunking."""
        self._log_with_context("info", "Document exceeds token limit. Using PDF page chunking...")
        
        if not PYPDF2_AVAILABLE:
            self._log_with_context("error", "PyPDF2 not available. Cannot chunk document.")
            raise ImportError("PyPDF2 required for PDF chunking")
        
        try:
            # Split PDF into smaller PDFs by pages
            pdf_chunks = self.chunk_pdf_by_pages(pdf_path, max_pages_per_chunk=5)
            
            # Process each PDF chunk
            all_results = []
            test_date = None
            
            for i, pdf_chunk_base64 in enumerate(pdf_chunks, 1):
                self._log_with_context("info", f"Processing PDF chunk {i}/{len(pdf_chunks)}")
                
                # Create prompt for this chunk
                chunk_prompt = self.create_chunk_extraction_prompt(i, len(pdf_chunks))
                
                try:
                    # Process chunk with Claude using actual PDF (not text!)
                    chunk_result = self._extract_chunk_with_claude_pdf(chunk_prompt, pdf_chunk_base64)
                    
                    if chunk_result.get('results'):
                        all_results.extend(chunk_result['results'])
                    
                    # Capture test date from any chunk that has it
                    if chunk_result.get('test_date') and not test_date:
                        test_date = chunk_result['test_date']
                        
                    # Add small delay between requests to avoid rate limits
                    if i < len(pdf_chunks):  # Don't sleep after last chunk
                        time.sleep(1)
                        
                except Exception as e:
                    self._log_with_context("error", f"Error processing chunk {i}: {e}")
                    # Continue with other chunks even if one fails
                    continue
            
            # Merge and deduplicate results
            merged_results = self._merge_chunk_results(all_results)
            
            self._log_with_context("info", f"Chunked processing complete: {len(merged_results)} markers from {len(pdf_chunks)} chunks")
            
            return {
                "success": True,
                "test_date": test_date,
                "results": merged_results,
                "processing_info": {
                    "chunks_processed": len(pdf_chunks),
                    "total_markers": len(merged_results)
                }
            }
            
        except Exception as e:
            self._log_with_context("error", f"Error in chunked processing: {e}")
            raise
    
    def _extract_chunk_with_claude_pdf(self, prompt: str, pdf_chunk_base64: str) -> Dict:
        """Extract data from a PDF chunk using Claude - sends actual PDF, not text!"""
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
                                    "data": pdf_chunk_base64
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
                
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Clean common issues
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    json_str = re.sub(r'}\s*{', '},{', json_str)
                    json_str = json_str.replace('\x00', '').replace('\r', '')
                    
                    return json.loads(json_str)
            else:
                return {"results": [], "test_date": None}
                
        except Exception as e:
            self._log_with_context("error", f"Error processing PDF chunk: {e}")
            return {"results": [], "test_date": None}
    
    # DEPRECATED: Old text-based chunk extraction - kept for compatibility
    def _extract_chunk_with_claude_text(self, prompt: str, text_chunk: str) -> Dict:
        """DEPRECATED: Extract data from a text chunk using Claude."""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                temperature=0,
                messages=[
                    {
                        "role": "user", 
                        "content": f"{prompt}\n\nTEXT TO ANALYZE:\n{text_chunk}"
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
                
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Clean common issues
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    json_str = re.sub(r'}\s*{', '},{', json_str)
                    json_str = json_str.replace('\x00', '').replace('\r', '')
                    
                    return json.loads(json_str)
            else:
                return {"results": [], "test_date": None}
                
        except Exception as e:
            self._log_with_context("error", f"Error processing text chunk: {e}")
            return {"results": [], "test_date": None}
    
    def _merge_chunk_results(self, all_results: List[Dict]) -> List[Dict]:
        """Merge and deduplicate results from multiple chunks."""
        if not all_results:
            return []
        
        # Use a dictionary to track unique markers
        # Key: (marker_name, value) to handle same marker with different values
        unique_markers = {}
        
        for result in all_results:
            marker_name = result.get('marker', '').strip().lower()
            marker_value = str(result.get('value', '')).strip()
            marker_id = result.get('marker_id')
            
            if not marker_name or not marker_value:
                continue
                
            # Create unique key
            key = (marker_name, marker_value)
            
            # If we haven't seen this marker+value combination, add it
            if key not in unique_markers:
                unique_markers[key] = result
            else:
                # If we have a marker_id in new result but not in existing, update it
                existing = unique_markers[key]
                if marker_id and not existing.get('marker_id'):
                    existing['marker_id'] = marker_id
                    # Also use the properly formatted marker name if we have an ID
                    if marker_id:
                        existing['marker'] = result.get('marker', existing['marker'])
        
        # Convert back to list, sorted by marker name
        merged_results = list(unique_markers.values())
        merged_results.sort(key=lambda x: x.get('marker', '').lower())
        
        self._log_with_context("info", f"Merged {len(all_results)} raw results into {len(merged_results)} unique markers")
        return merged_results
    
    def _extract_with_claude_basic(self, pdf_base64: str) -> Dict:
        """Basic extraction without token checking (original method)."""
        prompt = self.create_extraction_prompt()
        
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
            
            # Find JSON in the response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Clean common issues
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    json_str = re.sub(r'}\s*{', '},{', json_str)
                    json_str = json_str.replace('\x00', '').replace('\r', '')
                    
                    return json.loads(json_str)
            else:
                return {"results": [], "test_date": None}
                
        except Exception as e:
            self._log_with_context("error", f"Error with Claude extraction: {e}")
            raise
    
    def extract(self, pdf_path: str) -> Dict:
        """Extract blood test data from PDF using selected AI service."""
        # Update filename if not already set or if different
        if self.filename == "unknown" or pdf_path:
            self.filename = pdf_path.split('/')[-1] if pdf_path else "unknown"
            
        # Encode PDF as base64
        pdf_base64 = self.encode_pdf_to_base64(pdf_path)
        
        # Extract using appropriate service
        if self.service == "claude":
            return self.extract_with_claude(pdf_base64, pdf_path)
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