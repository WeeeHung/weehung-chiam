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
    Generate event pins for a given date range and viewport.
    
    Returns cached result if available, otherwise generates new pins.
    Accumulates pins across different viewports for the same date range.
    """
    # Check viewport-specific cache first (for fast lookup)
    cache_key = cache_service.get_pins_key(
        start_date=request.start_date,
        end_date=request.end_date,
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
        
        # Also ensure these pins are in the date range accumulated cache
        cache_service.merge_and_set_date_range_pins(
            request.start_date,
            request.end_date,
            request.language,
            cached_pins
        )
        
        return PinsResponse(start_date=request.start_date, end_date=request.end_date, pins=cached_pins)
    
    # Generate new pins
    try:
        new_pins = gemini_service.generate_pins(
            start_date=request.start_date,
            end_date=request.end_date,
            viewport=request.viewport,
            language=request.language,
            max_pins=request.max_pins
        )
        
        # Merge new pins with accumulated pins for this date range
        # This ensures pins are accumulated across different viewports
        merged_pins = cache_service.merge_and_set_date_range_pins(
            request.start_date,
            request.end_date,
            request.language,
            new_pins
        )
        
        # Cache the viewport-specific result (for fast lookup next time)
        cache_service.set_pins(cache_key, new_pins)
        
        # Store pins for later retrieval
        for pin in merged_pins:
            _pin_store[pin.event_id] = pin
        
        # Return the merged pins (all accumulated pins for this date range)
        return PinsResponse(start_date=request.start_date, end_date=request.end_date, pins=merged_pins)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating pins: {str(e)}")


def _parse_date_period(date_str: str) -> tuple[str, str]:
    """
    Parse a date string and return start_date and end_date.
    
    Handles:
    - Single date (YYYY-MM-DD): start_date = end_date = that date
    - Year (YYYY): start_date = YYYY-01-01, end_date = YYYY-12-31
    - Month (YYYY-MM): start_date = YYYY-MM-01, end_date = last day of that month
    - Relative dates: "today", "yesterday" -> single day
    - Default: last 7 days
    
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    from datetime import datetime, timedelta
    from calendar import monthrange
    
    today = datetime.now().date()
    
    if not date_str or date_str.lower() in ["null", "none", ""]:
        # Default: last 7 days
        end_date = today
        start_date = today - timedelta(days=6)  # 7 days inclusive
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    
    date_str = date_str.strip()
    
    # Handle relative dates
    if date_str.lower() == "today":
        date_str = today.strftime('%Y-%m-%d')
    elif date_str.lower() == "yesterday":
        date_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Try to parse as different formats
    try:
        # Try YYYY-MM-DD (single date)
        if len(date_str) == 10 and date_str.count('-') == 2:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return date_str, date_str  # Same start and end for single day
        
        # Try YYYY-MM (month)
        if len(date_str) == 7 and date_str.count('-') == 1:
            year, month = map(int, date_str.split('-'))
            start_date = datetime(year, month, 1).date()
            last_day = monthrange(year, month)[1]
            end_date = datetime(year, month, last_day).date()
            return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
        
        # Try YYYY (year)
        if len(date_str) == 4 and date_str.isdigit():
            year = int(date_str)
            start_date = datetime(year, 1, 1).date()
            end_date = datetime(year, 12, 31).date()
            return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
        
        # If we can't parse it, try as single date anyway
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        return date_str, date_str
        
    except (ValueError, AttributeError):
        # If parsing fails, default to last 7 days
        end_date = today
        start_date = today - timedelta(days=6)
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


@router.post("/parse-command", response_model=ParseCommandResponse)
async def parse_command(request: ParseCommandRequest):
    """
    Parse voice command to extract location (with geocoding), language, and date period.
    Uses Gemini Flash for accurate entity extraction, then geocodes the location.
    Handles date periods: single day, month, year, or defaults to last 7 days.
    """
    from datetime import datetime, timedelta
    from ..services.news import GeocodingService
    
    geocoding_service = GeocodingService()
    
    # Get current date for relative date handling
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    default_start = today - timedelta(days=6)  # Last 7 days
    
    # System prompt for extraction
    system_instruction = """You are a command parser that extracts location name, language code, and date/date period from user voice commands. 
    The user may mention an event or a news article, deduce the most likely intention and extract the location name, language code, and date accordingly.

Extract:
1. LOCATION_NAME: The place/city/country mentioned (e.g., "Tokyo", "New York", "Johor Bahru"). Return just the location name, nothing else.
2. LANGUAGE: 2-letter ISO code (en, zh, ja, es, fr, de, ko, pt, ru, ar, hi) - extract from phrases like "in chinese" or infer from context
3. DATE_PERIOD: Can be:
   - Single date: "YYYY-MM-DD" (e.g., "2024-12-14", "today", "yesterday")
   - Month: "YYYY-MM" (e.g., "2024-12" for December 2024)
   - Year: "YYYY" (e.g., "2024" for the entire year 2024)
   - If not specified, return null (will default to last 7 days)

Return ONLY valid JSON with this exact structure:
{
  "location_name": "string or null",
  "language": "string or null", 
  "date_period": "YYYY-MM-DD or YYYY-MM or YYYY or 'today' or 'yesterday' or null"
}"""
    
    user_prompt = f"""Parse this voice command:

Command: "{request.text}"

Current date: {today.strftime('%Y-%m-%d')}
Yesterday: {yesterday.strftime('%Y-%m-%d')}
Default period (if not specified): last 7 days ({default_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})

Extract location_name, language, and date_period. Return JSON only."""
    
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
        date_period = parsed.get("date_period")
        
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
        
        # Clean up language
        if language and language.lower() in ["null", "none", ""]:
            language = None
        
        # Parse date period to start_date and end_date
        start_date, end_date = _parse_date_period(date_period)
        
        return ParseCommandResponse(
            location=location_result,
            language=language,
            start_date=start_date,
            end_date=end_date
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: {e}")
        logger.debug(f"Response text: {response_text}")
        # Fallback: return default date range (last 7 days)
        default_start_str = default_start.strftime('%Y-%m-%d')
        default_end_str = today.strftime('%Y-%m-%d')
        return ParseCommandResponse(
            start_date=default_start_str,
            end_date=default_end_str
        )
    except Exception as e:
        logger.error(f"Error parsing command: {str(e)}")
        # Return default date range on error
        default_start_str = default_start.strftime('%Y-%m-%d')
        default_end_str = today.strftime('%Y-%m-%d')
        return ParseCommandResponse(
            start_date=default_start_str,
            end_date=default_end_str
        )


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


@router.get("/random-event", response_model=ParseCommandResponse)
async def get_random_event():
    """
    Get a random interesting historic event with location and date.
    Uses Gemini to find an interesting historic event (e.g., NATO treaty, US independence,
    Chicago Bulls second 3-peat, opening of a national park, peace treaty, Japan surrender, etc.)
    and returns the exact location and date.
    """
    from ..services.news import GeocodingService
    
    geocoding_service = GeocodingService()
    
    # System prompt for finding interesting historic events
    system_instruction = """You are a historian that finds interesting and significant historic events from world history. This event can be in any era, any country, any topic.

Find a random, interesting historic event that is:
- Significant and well-documented
- Has a specific date (YYYY-MM-DD format)
- Has a specific location (city, country, or landmark)
- Is interesting and educational (e.g., NATO treaty signing, US Declaration of Independence, 
  Chicago Bulls second 3-peat championship, opening of a US national park, peace treaties, 
  Japan surrender in WWII, moon landing, fall of Berlin Wall, etc.)

Return ONLY valid JSON with this exact structure:
{
  "event_name": "Brief name of the event",
  "location_name": "Specific location name (city, country, or landmark)",
  "date": "YYYY-MM-DD"
}

Examples:
- {"event_name": "NATO Treaty Signing", "location_name": "Washington, D.C.", "date": "1949-04-04"}
- {"event_name": "US Declaration of Independence", "location_name": "Philadelphia", "date": "1776-07-04"}
- {"event_name": "Chicago Bulls Second 3-Peat", "location_name": "Chicago", "date": "1998-06-14"}
- {"event_name": "Yellowstone National Park Opening", "location_name": "Yellowstone National Park", "date": "1872-03-01"}
- {"event_name": "Japan Surrender WWII", "location_name": "Tokyo Bay", "date": "1945-09-02"}
- {"event_name": "Fall of Berlin Wall", "location_name": "Berlin", "date": "1989-11-09"}
- {"event_name": "Apollo 11 Moon Landing", "location_name": "Sea of Tranquility", "date": "1969-07-20"}

Pick a different interesting event each time. Vary the time periods and locations."""
    
    user_prompt = """Find a random interesting historic event and return its location name and exact date in JSON format."""
    
    try:
        # Call Gemini Flash (fastest model)
        response = gemini_service.client.models.generate_content(
            model="gemini-2.0-flash-exp",  # Fastest model
            contents=[
                {"role": "user", "parts": [{"text": system_instruction}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            config=types.GenerateContentConfig(
                temperature=1.2,  # Higher temperature for variety
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
        date_str = parsed.get("date")
        
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
        
        # Parse date to start_date and end_date (single day)
        if date_str:
            start_date, end_date = _parse_date_period(date_str)
        else:
            # Fallback to a default date if parsing fails
            today = datetime.now().date()
            default_start = today - timedelta(days=6)
            start_date = default_start.strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
        
        return ParseCommandResponse(
            location=location_result,
            language=None,  # Keep current language
            start_date=start_date,
            end_date=end_date
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: {e}")
        logger.debug(f"Response text: {response_text}")
        # Fallback: return a default historic event (US Independence)
        try:
            geocoded = geocoding_service.geocode_location("Philadelphia")
            location_result = {
                "lat": geocoded["lat"],
                "lng": geocoded["lng"],
                "name": geocoded.get("display_name", "Philadelphia")
            } if geocoded else None
        except:
            location_result = None
        
        return ParseCommandResponse(
            location=location_result,
            language=None,
            start_date="1776-07-04",
            end_date="1776-07-04"
        )
    except Exception as e:
        logger.error(f"Error getting random event: {str(e)}")
        # Fallback: return a default historic event
        try:
            geocoded = geocoding_service.geocode_location("Philadelphia")
            location_result = {
                "lat": geocoded["lat"],
                "lng": geocoded["lng"],
                "name": geocoded.get("display_name", "Philadelphia")
            } if geocoded else None
        except:
            location_result = None
        
        return ParseCommandResponse(
            location=location_result,
            language=None,
            start_date="1776-07-04",
            end_date="1776-07-04"
        )


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

