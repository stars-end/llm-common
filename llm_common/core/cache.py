"""Abstract cache backend interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class CacheBackend(ABC):
    """Abstract base class for persistent cache storage."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        """Store value in cache.
        
        Args:
            key: Cache key
            value: Value to store (must be serializable)
            ttl: Time to live in seconds
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache.
        
        Args:
            key: Cache key
        """
        pass
