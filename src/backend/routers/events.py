"""
Events API router for generating pins, explanations, and chat.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime

from ..models import PinsRequest, PinsResponse, ChatRequest, Pin
from ..services.gemini import GeminiService
from ..services.cache import CacheService
from ..utils.sse import stream_text_chunks

router = APIRouter(prefix="/api/events", tags=["events"])

# Initialize services
gemini_service = GeminiService()
cache_service = CacheService()

# Simple in-memory pin store (for MVP)
# In production, use a database
_pin_store: dict[str, Pin] = {}


def _find_pin_in_cache(event_id: str, cache_service: CacheService) -> Optional[Pin]:
    """
    Search through cached pins to find a pin by event_id.
    
    This is a fallback when pin is not in _pin_store (e.g., after server restart).
    """
    # Search through all cache entries that might contain pins
    # This is not ideal but works for MVP
    for cache_key, (cached_value, expiry) in cache_service._cache.items():
        if datetime.now() > expiry:
            continue
        
        # Check if this is a pins cache entry (contains list of pins)
        if isinstance(cached_value, list) and len(cached_value) > 0:
            # Check if first item looks like a Pin
            if hasattr(cached_value[0], 'event_id'):
                # Search for the pin in this cached list
                for pin in cached_value:
                    if pin.event_id == event_id:
                        # Found it! Store in _pin_store for future use
                        _pin_store[event_id] = pin
                        return pin
    
    return None


@router.post("/pins", response_model=PinsResponse)
async def generate_pins(request: PinsRequest) -> PinsResponse:
    """
    Generate event pins for a given date and viewport.
    
    Returns cached result if available, otherwise generates new pins.
    Accumulates pins across different viewports for the same date.
    """
    # Check viewport-specific cache first (for fast lookup)
    cache_key = cache_service.get_pins_key(
        date=request.date,
        bbox={
            "west": request.viewport.bbox.west,
            "south": request.viewport.bbox.south,
            "east": request.viewport.bbox.east,
            "north": request.viewport.bbox.north,
        },
        zoom=request.viewport.zoom,
        language=request.language,
        max_pins=request.max_pins
    )
    
    cached_pins = cache_service.get(cache_key)
    if cached_pins is not None:
        # Store pins in _pin_store when returning from cache
        # This ensures pins are available for explanation endpoint
        for pin in cached_pins:
            _pin_store[pin.event_id] = pin
        
        # Also ensure these pins are in the date-accumulated cache
        cache_service.merge_and_set_date_pins(
            request.date,
            request.language,
            cached_pins
        )
        
        return PinsResponse(date=request.date, pins=cached_pins)
    
    # Generate new pins
    try:
        new_pins = gemini_service.generate_pins(
            date=request.date,
            viewport=request.viewport,
            language=request.language,
            max_pins=request.max_pins
        )
        
        # Merge new pins with accumulated pins for this date
        # This ensures pins are accumulated across different viewports
        merged_pins = cache_service.merge_and_set_date_pins(
            request.date,
            request.language,
            new_pins
        )
        
        # Cache the viewport-specific result (for fast lookup next time)
        cache_service.set_pins(cache_key, new_pins)
        
        # Store pins for later retrieval
        for pin in merged_pins:
            _pin_store[pin.event_id] = pin
        
        # Return the merged pins (all accumulated pins for this date)
        return PinsResponse(date=request.date, pins=merged_pins)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating pins: {str(e)}")


@router.get("/{event_id}/explain/stream")
async def stream_explanation(event_id: str, language: str = "en"):
    """
    Stream event explanation as SSE.
    
    Checks cache first, then streams from Gemini if not cached.
    """
    # For now, we need to get the pin from somewhere
    # In a real implementation, you'd store pins or fetch them
    # For MVP, we'll generate a minimal pin from event_id
    # This is a limitation - ideally pins would be stored
    
    # Check cache
    cache_key = cache_service.get_explanation_key(event_id, language)
    cached_explanation = cache_service.get(cache_key)
    
    if cached_explanation is not None:
        # Stream cached explanation
        def cached_stream():
            yield cached_explanation
        return StreamingResponse(
            stream_text_chunks(cached_stream()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Generate explanation
    # Try to get pin from store, otherwise search cache, otherwise create minimal pin
    try:
        pin = _pin_store.get(event_id)
        
        # If not in store, try to find it in cached pins
        if not pin:
            pin = _find_pin_in_cache(event_id, cache_service)
        
        # If still not found, create minimal pin from event_id
        if not pin:
            # Parse event_id to extract date and create minimal pin
            # Format: evt_YYYY-MM-DD_location_001
            parts = event_id.split("_")
            if len(parts) >= 2:
                date = parts[1]
            else:
                date = "2025-01-01"
            
            # Create minimal pin as fallback
            pin = Pin(
                event_id=event_id,
                title="Event",
                date=date,
                lat=0.0,
                lng=0.0,
                location_label="Unknown",
                category="other",
                significance_score=0.5,
                one_liner="Event description",
                confidence=0.5
            )
        
        explanation_stream = gemini_service.stream_explanation(pin, language)
        
        # Collect explanation for caching
        explanation_text = ""
        chunks = []
        
        def stream_with_cache():
            nonlocal explanation_text
            for chunk in explanation_stream:
                explanation_text += chunk
                chunks.append(chunk)
                yield chunk
            
            # Cache the full explanation
            cache_service.set_explanation(cache_key, explanation_text)
        
        return StreamingResponse(
            stream_text_chunks(stream_with_cache()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming explanation: {str(e)}"
        )


@router.post("/{event_id}/chat/stream")
async def stream_chat(event_id: str, request: ChatRequest):
    """
    Stream Q&A response for an event.
    
    Accepts question and chat history, returns SSE stream.
    """
    try:
        # Try to get pin from store, otherwise search cache, otherwise create minimal pin
        pin = _pin_store.get(event_id)
        
        # If not in store, try to find it in cached pins
        if not pin:
            pin = _find_pin_in_cache(event_id, cache_service)
        
        # If still not found, create minimal pin from event_id
        if not pin:
            # Parse event_id to create minimal pin
            parts = event_id.split("_")
            if len(parts) >= 2:
                date = parts[1]
            else:
                date = "2025-01-01"
            
            pin = Pin(
                event_id=event_id,
                title="Event",
                date=date,
                lat=0.0,
                lng=0.0,
                location_label="Unknown",
                category="other",
                significance_score=0.5,
                one_liner="Event description",
                confidence=0.5
            )
        
        chat_stream = gemini_service.stream_chat(
            event_id=event_id,
            pin=pin,
            question=request.question,
            history=request.history,
            language=request.language
        )
        
        return StreamingResponse(
            stream_text_chunks(chat_stream),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming chat: {str(e)}"
        )

