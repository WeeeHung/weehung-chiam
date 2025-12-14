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
        start_date: str,
        end_date: str,
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
            start_date,
            end_date,
            rounded_bbox,
            zoom_bucket,
            language,
            max_pins
        )
    
    def get_explanation_key(self, event_id: str, language: str) -> str:
        """Generate cache key for explanation."""
        return self._make_key("explanation", event_id, language)
    
    def get_date_range_pins_key(self, start_date: str, end_date: str, language: str) -> str:
        """Generate cache key for accumulated pins by date range."""
        return self._make_key("date_range_pins", start_date, end_date, language)
    
    def get_date_range_pins(self, start_date: str, end_date: str, language: str) -> Optional[Any]:
        """Get all accumulated pins for a date range."""
        key = self.get_date_range_pins_key(start_date, end_date, language)
        return self.get(key)
    
    def merge_and_set_date_range_pins(self, start_date: str, end_date: str, language: str, new_pins: list) -> list:
        """
        Merge new pins with existing pins for a date range (deduplicate by event_id).
        Returns the merged list of pins.
        """
        key = self.get_date_range_pins_key(start_date, end_date, language)
        existing_pins = self.get(key) or []
        
        # Create a set of existing event_ids for fast lookup
        existing_ids = {pin.event_id for pin in existing_pins}
        
        # Add new pins that don't already exist
        merged_pins = list(existing_pins)
        for new_pin in new_pins:
            if new_pin.event_id not in existing_ids:
                merged_pins.append(new_pin)
                existing_ids.add(new_pin.event_id)
        
        # Update cache with merged pins
        self.set_pins(key, merged_pins)
        
        return merged_pins
    
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

