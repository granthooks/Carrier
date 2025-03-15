#!/usr/bin/env python3
import logging

def configure_logging():
    """Configure logging for the application"""
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Configure logger with custom formatter to control timestamp format
    logger = logging.getLogger("logbot")
    for handler in logging.root.handlers:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S'
        ))

    # Add logging filters
    def filter_unwanted_logs(record):
        filtered_messages = [
            "PyNaCl is not installed, voice will NOT be supported",
            "logging in using static token",
            "Shard ID None has connected to Gateway"
        ]
        return not any(message in record.getMessage() for message in filtered_messages)
    
    # Apply log filter to discord logger
    discord_logger = logging.getLogger("discord.client")
    discord_logger.addFilter(filter_unwanted_logs)
    
    # Suppress httpx INFO messages
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logger

def get_logger(name):
    """Get a logger with the given name"""
    return logging.getLogger(name) 