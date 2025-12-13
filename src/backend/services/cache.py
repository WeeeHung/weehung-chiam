"""
TTL cache service for pins and explanations.

Uses in-memory dictionary with expiration timestamps.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json


class CacheService:
    """In-memory TTL cache for API responses."""
    
    def __init__(self):
        """Initialize cache with default TTLs."""
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.pins_ttl = timedelta(minutes=60)  # 1 hour for pins
        self.explanation_ttl = timedelta(hours=12)  # 12 hours for explanations
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_pins_key(
        self,
        date: str,
        bbox: Dict[str, float],
        zoom: float,
        language: str,
        max_pins: int
    ) -> str:
        """Generate cache key for pins request."""
        # Round bbox and zoom for cache efficiency
        rounded_bbox = {
            "west": round(bbox["west"], 1),
            "south": round(bbox["south"], 1),
            "east": round(bbox["east"], 1),
            "north": round(bbox["north"], 1),
        }
        zoom_bucket = int(zoom)  # Bucket by integer zoom level
        
        return self._make_key(
            "pins",
            date,
            rounded_bbox,
            zoom_bucket,
            language,
            max_pins
        )
    
    def get_explanation_key(self, event_id: str, language: str) -> str:
        """Generate cache key for explanation."""
        return self._make_key("explanation", event_id, language)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        if datetime.now() > expiry:
            # Expired, remove it
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any, ttl: timedelta) -> None:
        """Set value in cache with TTL."""
        expiry = datetime.now() + ttl
        self._cache[key] = (value, expiry)
    
    def set_pins(self, key: str, value: Any) -> None:
        """Set pins in cache with default TTL."""
        self.set(key, value, self.pins_ttl)
    
    def set_explanation(self, key: str, value: Any) -> None:
        """Set explanation in cache with default TTL."""
        self.set(key, value, self.explanation_ttl)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if now > expiry
        ]
        for key in expired_keys:
            del self._cache[key]

