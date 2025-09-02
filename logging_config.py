"""
BetterStack logging configuration module.
Provides centralized logging setup for the entire application.
"""

import os
import logging
import sys
from typing import Optional
from logtail import LogtailHandler
import logtail


def setup_logging(
    service_name: str = "wellavy-extract",
    log_level: str = "INFO"
) -> logging.Logger:
    """
    Set up logging with BetterStack integration.
    
    Args:
        service_name: Name of the service for logging context
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    # Get BetterStack source token from environment
    betterstack_token = os.getenv("BETTERSTACK_TOKEN")
    betterstack_endpoint = os.getenv("BETTERSTACK_ENDPOINT")
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Configure formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add BetterStack handler if token is available
    if betterstack_token:
        try:
            handler_kwargs = {'source_token': betterstack_token}
            if betterstack_endpoint:
                handler_kwargs['host'] = betterstack_endpoint
            
            betterstack_handler = LogtailHandler(**handler_kwargs)
            logger.addHandler(betterstack_handler)
            logger.info("BetterStack logging initialized successfully")
        except Exception as e:
            # Fallback to console if BetterStack fails
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.warning(f"Failed to initialize BetterStack logging: {e}")
            logger.warning("Continuing with console logging only")
    else:
        # Only use console logging if BetterStack token not available
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.warning("BETTERSTACK_TOKEN not found - using console logging only")
    
    return logger


def get_logger(name: str = "wellavy-extract") -> logging.Logger:
    """
    Get a logger instance. If not already configured, set up with default config.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set it up
    if not logger.handlers:
        logger = setup_logging(name)
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """
    Log a message with structured context data.
    
    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        **context: Additional context data to include
    """
    # Get the logging method by level name
    log_method = getattr(logger, level.lower())
    
    # Log with context as extra data
    log_method(message, extra=context)


class RequestLogger:
    """Context manager for logging request-specific information."""
    
    def __init__(self, logger: logging.Logger, request_id: str, endpoint: str):
        self.logger = logger
        self.request_context = {
            'request': {
                'id': request_id,
                'endpoint': endpoint
            }
        }
        self.context = None
        
    def __enter__(self):
        # Set up logtail context for this request if available
        try:
            self.context = logtail.context(**self.request_context)
            self.context.__enter__()
        except (ValueError, AttributeError):
            # Fallback if logtail context fails
            self.context = None
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.__exit__(exc_type, exc_val, exc_tb)
    
    def info(self, message: str, **extra):
        """Log info message with request context."""
        flattened_context = {
            'request_id': self.request_context['request']['id'],
            'endpoint': self.request_context['request']['endpoint'],
            **extra
        }
        self.logger.info(message, extra=flattened_context)
        
    def warning(self, message: str, **extra):
        """Log warning message with request context."""
        flattened_context = {
            'request_id': self.request_context['request']['id'],
            'endpoint': self.request_context['request']['endpoint'],
            **extra
        }
        self.logger.warning(message, extra=flattened_context)
        
    def error(self, message: str, **extra):
        """Log error message with request context."""
        flattened_context = {
            'request_id': self.request_context['request']['id'],
            'endpoint': self.request_context['request']['endpoint'],
            **extra
        }
        self.logger.error(message, extra=flattened_context)
        
    def exception(self, message: str, **extra):
        """Log exception with request context."""
        flattened_context = {
            'request_id': self.request_context['request']['id'],
            'endpoint': self.request_context['request']['endpoint'],
            **extra
        }
        self.logger.exception(message, extra=flattened_context)