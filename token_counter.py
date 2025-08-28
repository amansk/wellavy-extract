#!/usr/bin/env python3
"""
Token counting utilities for managing API rate limits.
Uses anthropic's built-in token counting for Claude models.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text.
    Rough approximation: 1 token ≈ 4 characters for English text.
    
    Args:
        text: Input text to count tokens for
        
    Returns:
        Estimated token count
    """
    # Conservative estimate: 1 token per 3 characters (safer than 4)
    return len(text) // 3


def count_anthropic_tokens(client, text: str, model: str = "claude-3-5-sonnet-20241022") -> int:
    """
    Count tokens using Anthropic's token counting method.
    
    Args:
        client: Anthropic client instance
        text: Text to count tokens for
        model: Model to use for counting
        
    Returns:
        Exact token count
    """
    try:
        # Use Anthropic's built-in token counting
        from anthropic import Anthropic
        if isinstance(client, Anthropic):
            # Anthropic SDK v0.59.0 has count_tokens method
            token_count = client.count_tokens(text)
            return token_count
    except Exception as e:
        logger.warning(f"Could not use Anthropic token counting: {e}")
    
    # Fallback to estimation
    return estimate_token_count(text)


def calculate_request_tokens(prompt: str, pdf_text: str, database_markers: List[Dict] = None) -> Dict[str, int]:
    """
    Calculate the total tokens for a request.
    
    Args:
        prompt: The system prompt
        pdf_text: Extracted text from PDF
        database_markers: Optional list of database markers
        
    Returns:
        Dictionary with token counts for each component and total
    """
    token_counts = {
        "prompt": estimate_token_count(prompt),
        "pdf_text": estimate_token_count(pdf_text),
        "markers": 0,
        "total": 0
    }
    
    if database_markers:
        markers_text = json.dumps(database_markers)
        token_counts["markers"] = estimate_token_count(markers_text)
    
    token_counts["total"] = sum([
        token_counts["prompt"],
        token_counts["pdf_text"],
        token_counts["markers"]
    ])
    
    return token_counts


def check_token_limit(token_count: int, limit: int = 30000) -> Tuple[bool, Optional[str]]:
    """
    Check if token count exceeds the limit.
    
    Args:
        token_count: Total token count
        limit: Maximum allowed tokens (default: 30000)
        
    Returns:
        Tuple of (is_within_limit, error_message)
    """
    if token_count > limit:
        return False, f"Token count ({token_count}) exceeds limit ({limit})"
    
    # Warn if getting close to limit
    if token_count > limit * 0.9:
        logger.warning(f"Token count ({token_count}) approaching limit ({limit})")
    
    return True, None


def split_document_for_chunks(pdf_text: str, max_tokens: int = 20000) -> List[str]:
    """
    Split a document into chunks that fit within token limits.
    
    Args:
        pdf_text: The full PDF text
        max_tokens: Maximum tokens per chunk (leaving room for prompt)
        
    Returns:
        List of text chunks
    """
    # Estimate characters per chunk (3 chars per token)
    max_chars = max_tokens * 3
    
    # Split by pages first if possible (look for page markers)
    pages = pdf_text.split('\n\n')
    
    chunks = []
    current_chunk = ""
    
    for page in pages:
        # Check if adding this page would exceed limit
        if len(current_chunk) + len(page) > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = page
        else:
            current_chunk += "\n\n" + page if current_chunk else page
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def optimize_markers_for_document(database_markers: List[Dict], document_type: str) -> List[Dict]:
    """
    Filter markers based on document type to reduce token usage.
    
    Args:
        database_markers: Full list of database markers
        document_type: Type of document (blood_test, dxa_scan, etc.)
        
    Returns:
        Filtered list of relevant markers
    """
    if document_type == "blood_test":
        # Common blood test categories
        relevant_categories = [
            "glucose", "cholesterol", "hdl", "ldl", "triglycerides",
            "hemoglobin", "hematocrit", "rbc", "wbc", "platelets",
            "alt", "ast", "bilirubin", "albumin", "protein",
            "creatinine", "bun", "egfr", "sodium", "potassium",
            "calcium", "magnesium", "iron", "ferritin", "b12",
            "vitamin d", "testosterone", "estrogen", "thyroid",
            "tsh", "t3", "t4", "crp", "esr", "hba1c"
        ]
        
        # Filter markers that match relevant categories
        filtered_markers = []
        for marker in database_markers:
            marker_name = marker.get("name", "").lower()
            if any(category in marker_name for category in relevant_categories):
                filtered_markers.append(marker)
        
        logger.info(f"Filtered markers from {len(database_markers)} to {len(filtered_markers)} for blood test")
        return filtered_markers
    
    elif document_type == "dxa_scan":
        # DXA scan specific markers
        relevant_keywords = ["bone", "density", "bmd", "t-score", "z-score", "fracture"]
        filtered_markers = [
            m for m in database_markers 
            if any(kw in m.get("name", "").lower() for kw in relevant_keywords)
        ]
        return filtered_markers
    
    elif document_type == "inbody":
        # Body composition markers
        relevant_keywords = ["muscle", "fat", "weight", "bmi", "body", "lean", "mass"]
        filtered_markers = [
            m for m in database_markers 
            if any(kw in m.get("name", "").lower() for kw in relevant_keywords)
        ]
        return filtered_markers
    
    # Default: return all markers for unknown types
    return database_markers


class TokenManager:
    """Manages token usage and rate limiting."""
    
    def __init__(self, limit: int = 30000):
        self.limit = limit
        self.current_usage = 0
        self.usage_history = []
    
    def can_process(self, token_count: int) -> bool:
        """Check if we can process a request with given token count."""
        return (self.current_usage + token_count) <= self.limit
    
    def add_usage(self, tokens: int):
        """Record token usage."""
        self.current_usage += tokens
        self.usage_history.append(tokens)
        logger.info(f"Token usage: {tokens} (total: {self.current_usage}/{self.limit})")
    
    def reset(self):
        """Reset usage counter (call this every minute)."""
        self.current_usage = 0
        logger.info("Token usage counter reset")
    
    def get_remaining(self) -> int:
        """Get remaining tokens in current window."""
        return max(0, self.limit - self.current_usage)