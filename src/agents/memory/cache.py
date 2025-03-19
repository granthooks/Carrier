"""Caching system for memory operations."""

from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class MemoryCache:
    """LRU cache for memory items with TTL support."""
    
    def __init__(self, max_size: int = 1000, max_age_ms: int = 3600000):
        """Initialize cache with max size and TTL.
        
        Args:
            max_size: Maximum number of entries in the cache
            max_age_ms: Maximum age of entries in milliseconds (default: 1 hour)
        """
        self.max_size = max_size
        self.max_age_ms = max_age_ms
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, datetime] = {}
        
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if it exists and is not expired.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            The cached value if available and not expired, None otherwise
        """
        if key not in self.cache:
            return None
            
        # Check if expired
        timestamp = self.timestamps.get(key)
        if timestamp:
            age = datetime.now() - timestamp
            if age > timedelta(milliseconds=self.max_age_ms):
                # Remove expired item
                self.cache.pop(key, None)
                self.timestamps.pop(key, None)
                return None
                
        # Move to end (most recently used)
        value = self.cache.pop(key)
        self.cache[key] = value
        return value
        
    def set(self, key: str, value: Any) -> None:
        """Set item in cache, respecting max size.
        
        Args:
            key: Cache key to set
            value: Value to cache
        """
        # Remove if already exists
        if key in self.cache:
            self.cache.pop(key)
            
        # Check if we need to remove oldest item
        if len(self.cache) >= self.max_size:
            oldest = next(iter(self.cache))
            self.cache.pop(oldest)
            self.timestamps.pop(oldest, None)
            
        # Add new item
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def clear(self) -> None:
        """Clear all items from the cache."""
        self.cache.clear()
        self.timestamps.clear()
        
    def remove(self, key: str) -> None:
        """Remove a specific item from the cache.
        
        Args:
            key: Cache key to remove
        """
        if key in self.cache:
            self.cache.pop(key)
            self.timestamps.pop(key, None)
