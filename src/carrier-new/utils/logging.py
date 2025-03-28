"""
Logging configuration for Carrier agents
"""

import logging
import os
import sys
from typing import Optional


def configure_logging(
    level: str = "INFO",
    format_str: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for Carrier agents.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_str: Custom format string for log messages
        log_file: Path to write logs to (in addition to console)
        
    Returns:
        Configured logger instance
    """
    # Set default format if not provided
    if not format_str:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Add file handler if log_file specified
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(format_str))
        logging.getLogger().addHandler(file_handler)
    
    # Create and return a logger for this module
    logger = logging.getLogger("carrier")
    return logger
