"""
Phase 2: Data Infrastructure - Cache Manager
"""
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Redis-like cache manager for market data.
    """
    
    def __init__(self):
        self.cache = {}
        self.ttl_map = {}
        
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300
    ):
        """
        Set cache value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        self.cache[key] = value
        self.ttl_map[key] = datetime.now() + timedelta(seconds=ttl_seconds)
        
    def get(self, key: str) -> Optional[Any]:
        """
        Get cache value.
        
        Returns:
            Cached value or None if expired/not found
        """
        if key not in self.cache:
            return None
        
        # Check TTL
        if datetime.now() > self.ttl_map.get(key, datetime.min):
            self.delete(key)
            return None
        
        return self.cache[key]
    
    def delete(self, key: str):
        """Delete cache entry."""
        self.cache.pop(key, None)
        self.ttl_map.pop(key, None)
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.ttl_map.clear()
        logger.info("Cache cleared")
    
    def get_or_set(
        self,
        key: str,
        factory,
        ttl_seconds: int = 300
    ) -> Any:
        """
        Get from cache or set using factory function.
        
        Args:
            key: Cache key
            factory: Function to generate value if not cached
            ttl_seconds: Time to live in seconds
            
        Returns:
            Cached or newly generated value
        """
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl_seconds)
        return value
    
    def get_keys(self, pattern: str = "*") -> list:
        """Get all keys matching pattern."""
        import fnmatch
        return [k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)]
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = datetime.now()
        active = sum(1 for v in self.ttl_map.values() if now < v)
        expired = len(self.ttl_map) - active
        
        return {
            "total_entries": len(self.cache),
            "active_entries": active,
            "expired_entries": expired
        }
