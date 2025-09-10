"""
Unit tests for WellavyAIExtractor logging functionality.
Tests the contextual logging and extraction summary features.
"""

import unittest
from unittest.mock import Mock, patch, call
from wellavy_ai_extractor import WellavyAIExtractor


class TestWellavyLogging(unittest.TestCase):
    """Test cases for WellavyAIExtractor logging enhancements."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = WellavyAIExtractor(
            service="claude",
            database_markers=[
                {'id': '1', 'name': 'Glucose'},
                {'id': '2', 'name': 'Cholesterol'},
                {'id': '3', 'name': 'Hemoglobin A1C'}
            ],
            request_id="test-request-123",
            filename="test_results.pdf"
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_with_context_basic(self, mock_logger):
        """Test basic contextual logging functionality."""
        # Act
        self.extractor._log_with_context("info", "Test message")
        
        # Assert
        mock_logger.info.assert_called_once_with(
            "Test message", 
            extra={
                'request_id': 'test-request-123',
                'filename': 'test_results.pdf'
            }
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_with_context_with_extra_fields(self, mock_logger):
        """Test contextual logging with additional fields."""
        # Act
        self.extractor._log_with_context(
            "info", 
            "Processing chunk",
            chunk_number=2,
            total_chunks=5
        )
        
        # Assert
        mock_logger.info.assert_called_once_with(
            "Processing chunk", 
            extra={
                'request_id': 'test-request-123',
                'filename': 'test_results.pdf',
                'chunk_number': 2,
                'total_chunks': 5
            }
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_with_context_error_level(self, mock_logger):
        """Test contextual logging with error level."""
        # Act
        self.extractor._log_with_context("error", "Error occurred")
        
        # Assert
        mock_logger.error.assert_called_once_with(
            "Error occurred", 
            extra={
                'request_id': 'test-request-123',
                'filename': 'test_results.pdf'
            }
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_extraction_summary_with_database_markers(self, mock_logger):
        """Test extraction summary logging with database markers."""
        # Arrange
        result = {
            "results": [
                {"marker": "Glucose", "value": "95"},  # mapped
                {"marker": "CHOLESTEROL", "value": "180"},  # mapped (case insensitive)
                {"marker": "Unknown Marker", "value": "100"},  # unmapped
                {"marker": "Failed Test", "value": ""},  # failed
                {"marker": "Another Failed", "value": "not found"},  # failed
            ]
        }
        
        # Act
        self.extractor._log_extraction_summary("test_results.pdf", result)
        
        # Assert
        mock_logger.info.assert_called_once_with(
            "Extraction summary completed",
            extra={
                'request_id': 'test-request-123',
                'filename': 'test_results.pdf',
                'total_extracted': 5,
                'mapped': 2,
                'unmapped': 1,
                'failed': 2
            }
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_extraction_summary_empty_results(self, mock_logger):
        """Test extraction summary logging with empty results."""
        # Arrange
        result = {"results": []}
        
        # Act
        self.extractor._log_extraction_summary("test_results.pdf", result)
        
        # Assert
        mock_logger.info.assert_called_once_with(
            "Extraction summary completed",
            extra={
                'request_id': 'test-request-123',
                'filename': 'test_results.pdf',
                'total_extracted': 0,
                'mapped': 0,
                'unmapped': 0,
                'failed': 0
            }
        )
    
    @patch('wellavy_ai_extractor.logger')
    def test_log_extraction_summary_no_database_markers(self, mock_logger):
        """Test extraction summary when no database markers are provided."""
        # Arrange
        extractor = WellavyAIExtractor(
            database_markers=[],  # Empty markers
            request_id="test-123",
            filename="test.pdf"
        )
        result = {
            "results": [
                {"marker": "Test1", "value": "value1"},
                {"marker": "Test2", "value": "value2"}
            ]
        }
        
        # Act
        extractor._log_extraction_summary("test.pdf", result)
        
        # Assert - All should be unmapped since no database markers
        mock_logger.info.assert_called_once_with(
            "Extraction summary completed",
            extra={
                'request_id': 'test-123',
                'filename': 'test.pdf',
                'total_extracted': 2,
                'mapped': 0,
                'unmapped': 2,
                'failed': 0
            }
        )
    
    def test_default_values_in_constructor(self):
        """Test that default values are properly set when not provided."""
        # Act
        extractor = WellavyAIExtractor()
        
        # Assert
        self.assertEqual(extractor.request_id, "unknown")
        self.assertEqual(extractor.filename, "unknown")
    
    def test_filename_extraction_in_extract_method(self):
        """Test that filename is extracted from PDF path."""
        # Arrange
        extractor = WellavyAIExtractor(request_id="test-123")
        pdf_path = "/path/to/test_document.pdf"
        
        # Act
        extractor.filename = "unknown"  # Reset to test extraction
        # We need to mock the extract method calls to avoid actual API calls
        with patch.object(extractor, 'encode_pdf_to_base64', return_value='mock_base64'), \
             patch.object(extractor, 'extract_with_claude', return_value={'results': []}):
            extractor.extract(pdf_path)
        
        # Assert
        self.assertEqual(extractor.filename, "test_document.pdf")
    
    @patch('wellavy_ai_extractor.logger')
    def test_edge_case_malformed_database_markers(self, mock_logger):
        """Test handling of malformed database markers."""
        # Arrange
        extractor = WellavyAIExtractor(
            database_markers=[
                {'id': '1', 'name': 'Valid Marker'},
                {'id': '2'},  # Missing 'name' key
                {'name': ''},  # Empty name
                {},  # Empty dictionary
            ],
            request_id="test-123",
            filename="test.pdf"
        )
        result = {
            "results": [
                {"marker": "Valid Marker", "value": "123"},
                {"marker": "Invalid", "value": "456"}
            ]
        }
        
        # Act - Should not crash despite malformed markers
        extractor._log_extraction_summary("test.pdf", result)
        
        # Assert
        mock_logger.info.assert_called_once_with(
            "Extraction summary completed",
            extra={
                'request_id': 'test-123',
                'filename': 'test.pdf',
                'total_extracted': 2,
                'mapped': 1,  # Only 'Valid Marker' should match
                'unmapped': 1,
                'failed': 0
            }
        )


if __name__ == '__main__':
    unittest.main()