"""
Logging utilities for Carrier framework.
"""

import logging
import os
import sys
from typing import Optional


def configure_logging(level: Optional[int] = None) -> logging.Logger:
    """
    Configure logging for Carrier framework.
    
    Args:
        level: Logging level (defaults to INFO or value from CARRIER_LOG_LEVEL env var)
        
    Returns:
        Configured logger instance
    """
    # Get log level from environment or use default
    if level is None:
        level_name = os.environ.get("CARRIER_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create Carrier logger
    logger = logging.getLogger("carrier")
    logger.setLevel(level)
    
    return logger
