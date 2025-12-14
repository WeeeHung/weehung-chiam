"""
Memory module for storing and retrieving cache, conversation history, and session state.
"""

from typing import Dict, List, Optional, Any
from datetime import timedelta
from ..cache import CacheService
from ...models import Pin


class Memory:
    """Unified memory management for cache, conversations, and sessions."""
    
    def __init__(self):
        """Initialize memory with cache service."""
        self.cache_service = CacheService()
        # In-memory stores (moved from events.py)
        self._pin_store: Dict[str, Pin] = {}
        self._live_sessions: Dict[str, List[Dict[str, str]]] = {}
    
    # Cache operations
    def store_cache(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Store value in cache with optional TTL."""
        if ttl is None:
            self.cache_service.set_pins(key, value)
        else:
            self.cache_service.set(key, value, ttl)
    
    def retrieve_cache(self, key: str) -> Optional[Any]:
        """Retrieve cached value."""
        return self.cache_service.get(key)
    
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
        return self.cache_service.get_pins_key(
            start_date, end_date, bbox, zoom, language, max_pins
        )
    
    def get_explanation_key(self, event_id: str, language: str) -> str:
        """Generate cache key for explanation."""
        return self.cache_service.get_explanation_key(event_id, language)
    
    def merge_and_set_date_range_pins(
        self, start_date: str, end_date: str, language: str, new_pins: List[Pin]
    ) -> List[Pin]:
        """Merge new pins with existing pins for a date range."""
        return self.cache_service.merge_and_set_date_range_pins(
            start_date, end_date, language, new_pins
        )
    
    def set_explanation(self, key: str, value: str) -> None:
        """Store explanation in cache."""
        self.cache_service.set_explanation(key, value)
    
    # Pin store operations
    def store_pin(self, pin: Pin) -> None:
        """Store a pin in memory."""
        self._pin_store[pin.event_id] = pin
    
    def retrieve_pin(self, event_id: str) -> Optional[Pin]:
        """Retrieve a pin by event_id."""
        return self._pin_store.get(event_id)
    
    def find_pin_in_cache(self, event_id: str) -> Optional[Pin]:
        """Search through cached pins to find a pin by event_id."""
        from datetime import datetime
        for cache_key, (cached_value, expiry) in self.cache_service._cache.items():
            if datetime.now() > expiry:
                continue
            
            if isinstance(cached_value, list) and len(cached_value) > 0:
                if hasattr(cached_value[0], 'event_id'):
                    for pin in cached_value:
                        if pin.event_id == event_id:
                            self._pin_store[event_id] = pin
                            return pin
        
        return None
    
    # Conversation history operations
    def store_conversation(self, session_id: str, messages: List[Dict[str, str]]) -> None:
        """Store conversation history for a session."""
        self._live_sessions[session_id] = messages
    
    def retrieve_conversation(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieve conversation history for a session."""
        if session_id not in self._live_sessions:
            self._live_sessions[session_id] = []
        return self._live_sessions[session_id]
    
    def append_to_conversation(self, session_id: str, role: str, content: str) -> None:
        """Append a message to conversation history."""
        if session_id not in self._live_sessions:
            self._live_sessions[session_id] = []
        self._live_sessions[session_id].append({"role": role, "content": content})
    
    def clear_conversation(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if session_id in self._live_sessions:
            del self._live_sessions[session_id]
    
    # Session state operations
    def store_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Store session state data."""
        # For now, sessions are managed via conversation history
        # Can be extended if needed
        pass
    
    def retrieve_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session state data."""
        # For now, return conversation history as session data
        if session_id in self._live_sessions:
            return {"conversation": self._live_sessions[session_id]}
        return None
