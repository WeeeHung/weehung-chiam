"""
Events API router for generating pins, explanations, and chat.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List

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


@router.post("/pins", response_model=PinsResponse)
async def generate_pins(request: PinsRequest) -> PinsResponse:
    """
    Generate event pins for a given date and viewport.
    
    Returns cached result if available, otherwise generates new pins.
    """
    # Check cache
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
        return PinsResponse(date=request.date, pins=cached_pins)
    
    # Generate new pins
    try:
        pins = gemini_service.generate_pins(
            date=request.date,
            viewport=request.viewport,
            language=request.language,
            max_pins=request.max_pins
        )
        
        # Cache the result
        cache_service.set_pins(cache_key, pins)
        
        # Store pins for later retrieval
        for pin in pins:
            _pin_store[pin.event_id] = pin
        
        return PinsResponse(date=request.date, pins=pins)
        
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
    # Try to get pin from store, otherwise create minimal pin
    try:
        pin = _pin_store.get(event_id)
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
        # Try to get pin from store, otherwise create minimal pin
        pin = _pin_store.get(event_id)
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

