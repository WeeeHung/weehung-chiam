"""
Events API router for generating pins, explanations, and chat.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
import json
import asyncio
import base64
import io

logger = logging.getLogger(__name__)

from ..models import PinsRequest, PinsResponse, ChatRequest, Pin, ParseCommandRequest, ParseCommandResponse
from ..services.gemini import GeminiService
from ..services.cache import CacheService
from ..utils.sse import stream_text_chunks
from google.genai import types

router = APIRouter(prefix="/api/events", tags=["events"])

# Initialize services
gemini_service = GeminiService()
cache_service = CacheService()

# Simple in-memory pin store (for MVP)
# In production, use a database
_pin_store: dict[str, Pin] = {}

# Store active Live API sessions (conversation history per session)
_live_sessions: Dict[str, List[Dict[str, str]]] = {}


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


@router.post("/parse-command", response_model=ParseCommandResponse)
async def parse_command(request: ParseCommandRequest):
    """
    Parse voice command to extract location (with geocoding), language, and date.
    Uses Gemini Flash for accurate entity extraction, then geocodes the location.
    """
    from datetime import datetime, timedelta
    from ..services.news import GeocodingService
    
    geocoding_service = GeocodingService()
    
    # Get current date for relative date handling
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # System prompt for extraction
    system_instruction = """You are a command parser that extracts location name, language code, and date from user voice commands. 
    The user may mention an event or a news article, deduce the most likely intention and extract the location name, language code, and date accordingly.

Extract:
1. LOCATION_NAME: The place/city/country mentioned (e.g., "Tokyo", "New York", "Johor Bahru"). Return just the location name, nothing else.
2. LANGUAGE: 2-letter ISO code (en, zh, ja, es, fr, de, ko, pt, ru, ar, hi) - extract from phrases like "in chinese" or infer from context
3. DATE: YYYY-MM-DD format - handle "today", "yesterday", or parse specific dates

Return ONLY valid JSON with this exact structure:
{
  "location_name": "string or null",
  "language": "string or null", 
  "date": "YYYY-MM-DD or null"
}"""
    
    user_prompt = f"""Parse this voice command:

Command: "{request.text}"

Current date: {today.strftime('%Y-%m-%d')}
Yesterday: {yesterday.strftime('%Y-%m-%d')}

Extract location_name, language, and date. Return JSON only."""
    
    try:
        # Call Gemini Flash (fastest model)
        response = gemini_service.client.models.generate_content(
            model="gemini-2.0-flash-exp",  # Fastest model
            contents=[
                {"role": "user", "parts": [{"text": system_instruction}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for consistent extraction
                response_modalities=["TEXT"],
                max_output_tokens=200,
            )
        )
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        parsed = json.loads(response_text)
        
        location_name = parsed.get("location_name")
        language = parsed.get("language")
        date = parsed.get("date")
        
        # Geocode location if found
        location_result = None
        if location_name and location_name.lower() not in ["null", "none", ""]:
            try:
                geocoded = geocoding_service.geocode_location(location_name)
                if geocoded:
                    location_result = {
                        "lat": geocoded["lat"],
                        "lng": geocoded["lng"],
                        "name": geocoded.get("display_name", location_name)
                    }
            except Exception as e:
                logger.warning(f"Geocoding failed for '{location_name}': {e}")
        
        # Clean up language and date
        if language and language.lower() in ["null", "none", ""]:
            language = None
        if date and date.lower() in ["null", "none", ""]:
            date = None
        
        return ParseCommandResponse(
            location=location_result,
            language=language,
            date=date
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: {e}")
        logger.debug(f"Response text: {response_text}")
        # Fallback: return empty response
        return ParseCommandResponse()
    except Exception as e:
        logger.error(f"Error parsing command: {str(e)}")
        # Return empty response on error
        return ParseCommandResponse()


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
                confidence=0.5,
                positivity_scale=0.5
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
            
            # Cache the full explanation text
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


@router.websocket("/{event_id}/live/ws")
async def live_chat_websocket(
    websocket: WebSocket, 
    event_id: str, 
    language: str = Query(default="en")
):
    """
    WebSocket endpoint for Live API conversation with Gemini.
    
    Maintains conversation state and streams responses in real-time.
    Session ends when WebSocket closes.
    """
    await websocket.accept()
    
    # Initialize session if not exists
    session_id = f"{event_id}_{language}"
    if session_id not in _live_sessions:
        _live_sessions[session_id] = []
    
    conversation_history = _live_sessions[session_id]
    
    # Get pin information
    pin = _pin_store.get(event_id)
    if not pin:
        pin = _find_pin_in_cache(event_id, cache_service)
    
    if not pin:
        # Create minimal pin from event_id
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
    
    try:
        while True:
            # Receive message from client (can be text or binary for audio)
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
            except:
                # Try receiving as bytes (for audio)
                try:
                    data = await websocket.receive_bytes()
                    # For now, handle audio as base64 in text messages
                    continue
                except:
                    continue
            
            if message_data.get("type") == "audio":
                # Handle audio input (text transcript from speech recognition)
                audio_data_base64 = message_data.get("data", "")
                audio_format = message_data.get("format", "text")
                
                if not audio_data_base64:
                    continue
                
                try:
                    # Decode base64 to get text transcript
                    if audio_format == "text":
                        user_transcript = base64.b64decode(audio_data_base64).decode('utf-8')
                    else:
                        # For actual audio, would need speech-to-text here
                        user_transcript = "[Audio input received]"
                    
                    if not user_transcript.strip():
                        continue
                    
                    # Build system prompt with event context
                    system_prompt = f"""You are a helpful assistant with access to web search, answering questions about an event.

Event Context:
- Title: {pin.title}
- Date: {pin.date}
- Location: {pin.location_label}
- Category: {pin.category}
- Significance: {pin.significance_score}

You have access to web search capabilities. Use web search to find current, accurate information about this event and related topics. Provide detailed, well-researched answers based on web search results when relevant.

Respond in {language}. Be conversational and helpful. Keep responses concise for voice output."""
                    
                    # Build conversation context (no history logging as requested)
                    conversation_context = ""
                    # Only use last 3 messages for context to keep it minimal
                    for msg in conversation_history[-3:]:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        conversation_context += f"{role.capitalize()}: {content}\n"
                    
                    user_prompt = f"""{conversation_context}

User: {user_transcript}
Assistant:"""
                    
                    # Call Gemini API with web search enabled
                    response = gemini_service.client.models.generate_content(
                        model=gemini_service.model,
                        contents=[
                            {"role": "user", "parts": [{"text": system_prompt}]},
                            {"role": "user", "parts": [{"text": user_prompt}]}
                        ],
                        config={
                            "temperature": 0.7,
                            "max_output_tokens": 1000,  # Shorter for voice
                            "tools": [{"google_search": {}}],  # Enable web search
                        }
                    )
                    
                    assistant_response = response.text
                    
                    # For voice output, we need to convert text to speech
                    # For now, we'll send the text and let the client handle TTS
                    # In production, use a TTS service or Gemini's audio output
                    
                    # Simulate audio response by encoding text as base64
                    # In production, use actual TTS to generate audio
                    audio_response_base64 = base64.b64encode(assistant_response.encode('utf-8')).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_response_base64,
                        "format": "text"  # Indicates this is text that needs TTS
                    })
                    
                    await websocket.send_json({"type": "done"})
                    
                    # Don't log conversation history as requested
                    # conversation_history.append({"role": "assistant", "content": assistant_response})
                    
                except Exception as e:
                    error_msg = f"Error processing audio: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                    print(f"Audio processing error: {e}")
            
            elif message_data.get("type") == "message":
                # Handle text message (fallback)
                user_message = message_data.get("content", "")
                
                if not user_message.strip():
                    continue
                
                # Generate response using Gemini with web search
                try:
                    # Build system prompt with event context
                    system_prompt = f"""You are a helpful assistant with access to web search, answering questions about an event.

Event Context:
- Title: {pin.title}
- Date: {pin.date}
- Location: {pin.location_label}
- Category: {pin.category}
- Significance: {pin.significance_score}

You have access to web search capabilities. Use web search to find current, accurate information about this event and related topics. Provide detailed, well-researched answers based on web search results when relevant.

Respond in {language}. Be conversational and helpful."""
                    
                    user_prompt = f"User: {user_message}\nAssistant:"
                    
                    # Call Gemini API with web search enabled
                    response = gemini_service.client.models.generate_content(
                        model=gemini_service.model,
                        contents=[
                            {"role": "user", "parts": [{"text": system_prompt}]},
                            {"role": "user", "parts": [{"text": user_prompt}]}
                        ],
                        config={
                            "temperature": 0.7,
                            "max_output_tokens": 2000,
                            "tools": [{"google_search": {}}],  # Enable web search
                        }
                    )
                    
                    assistant_response = response.text
                    
                    # Send as audio (text encoded for now)
                    audio_response_base64 = base64.b64encode(assistant_response.encode('utf-8')).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_response_base64,
                        "format": "text"
                    })
                    
                    await websocket.send_json({"type": "done"})
                    
                except Exception as e:
                    error_msg = f"Error generating response: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                    print(f"Gemini API error: {e}")
            
    except WebSocketDisconnect:
        # Clean up session when client disconnects
        if session_id in _live_sessions:
            # Optionally keep history for a while, or delete immediately
            # For now, delete immediately
            del _live_sessions[session_id]
        print(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            })
        except:
            pass
        # Clean up on error
        if session_id in _live_sessions:
            del _live_sessions[session_id]


@router.post("/ephemeral-token")
async def create_ephemeral_token():
    """
    Create an ephemeral token for client-side Live API connections.
    
    Returns a short-lived token that can be used instead of the API key
    for enhanced security when connecting from the browser.
    """
    try:
        # Get the real API key from environment (server-side only)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY not found in server environment"
            )
        
        # Create Gemini client with v1alpha API version (required for ephemeral tokens)
        from google import genai
        client = genai.Client(
            api_key=api_key,
            http_options={'api_version': 'v1alpha'}
        )
        
        # Create ephemeral token
        # Default: 1 minute to start new session, 30 minutes total expiration
        now = datetime.now(tz=timezone.utc)
        expire_time = now + timedelta(minutes=30)
        new_session_expire_time = now + timedelta(minutes=1)
        
        token = client.auth_tokens.create(
            config={
                'uses': 1,  # Token can only be used to start a single session
                'expire_time': expire_time.isoformat(),
                'new_session_expire_time': new_session_expire_time.isoformat(),
                'http_options': {'api_version': 'v1alpha'},
            }
        )
        
        # Return the token name (this is what the client uses as the API key)
        return {
            "token": token.name,
            "expires_at": expire_time.isoformat(),
            "new_session_expires_at": new_session_expire_time.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating ephemeral token: {str(e)}"
        )

