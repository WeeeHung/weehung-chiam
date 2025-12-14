"""
Events API router using agent-based architecture.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
import json
import base64

logger = logging.getLogger(__name__)

from ..models import PinsRequest, PinsResponse, ChatRequest, Pin, ParseCommandRequest, ParseCommandResponse
from ..services.agent import Planner, Executor, Memory
from ..utils.sse import stream_text_chunks

router = APIRouter(prefix="/api/events", tags=["events"])

# Initialize agent components
planner = Planner()
executor = Executor()
memory = Memory()


@router.post("/pins", response_model=PinsResponse)
async def generate_pins(request: PinsRequest) -> PinsResponse:
    """
    Generate event pins for a given date range and viewport.
    
    Agent workflow:
    1. Check memory (cache)
    2. Plan sub-tasks
    3. Execute tasks
    4. Store in memory
    5. Return response
    """
    # 1. Check memory (cache)
    cache_key = memory.get_pins_key(
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
    
    cached_pins = memory.retrieve_cache(cache_key)
    if cached_pins is not None:
        # Store pins in memory
        for pin in cached_pins:
            memory.store_pin(pin)
        
        # Ensure pins are in date range accumulated cache
        memory.merge_and_set_date_range_pins(
            request.start_date,
            request.end_date,
            request.language,
            cached_pins
        )
        
        return PinsResponse(start_date=request.start_date, end_date=request.end_date, pins=cached_pins)
    
    # 2. Plan sub-tasks
    tasks = planner.plan_pins_generation(
        start_date=request.start_date,
        end_date=request.end_date,
        viewport=request.viewport,
        language=request.language,
        max_pins=request.max_pins
    )
    
    # 3. Execute tasks
    try:
        context = {}
        for task in tasks:
            result = executor.execute_task(task, context)
            context[task.name] = result
        
        # Get validated pins from context
        new_pins = context.get("validate_pins", context.get("geocode_locations", context.get("search_events", [])))
        
        # 4. Store in memory
        merged_pins = memory.merge_and_set_date_range_pins(
            request.start_date,
            request.end_date,
            request.language,
            new_pins
        )
        
        # Cache the viewport-specific result
        memory.store_cache(cache_key, new_pins)
        
        # Store pins for later retrieval
        for pin in merged_pins:
            memory.store_pin(pin)
        
        # 5. Return response
        return PinsResponse(start_date=request.start_date, end_date=request.end_date, pins=merged_pins)
        
    except Exception as e:
        logger.error(f"Error generating pins: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating pins: {str(e)}")


@router.post("/parse-command", response_model=ParseCommandResponse)
async def parse_command(request: ParseCommandRequest):
    """
    Parse voice command to extract location, language, and date period.
    
    Agent workflow:
    1. Plan sub-tasks
    2. Execute tasks
    3. Return response
    """
    # 1. Plan sub-tasks
    tasks = planner.plan_command_parsing(request.text)
    
    # 2. Execute tasks
    try:
        context = {}
        for task in tasks:
            result = executor.execute_task(task, context)
            context[task.name] = result
        
        # Extract results from context
        entities = context.get("extract_entities", {})
        location_result = context.get("geocode_location")
        
        # Get location name and geocode if needed
        location_name = entities.get("location_name")
        if location_name and location_name.lower() not in ["null", "none", ""]:
            if not location_result:
                # Try geocoding if not already done
                location_result = executor.call_geocoding(location_name)
                if location_result:
                    location_result = {
                        "lat": location_result["lat"],
                        "lng": location_result["lng"],
                        "name": location_result.get("display_name", location_name)
                    }
        
        # Get language
        language = entities.get("language")
        if language and language.lower() in ["null", "none", ""]:
            language = None
        
        # Get dates directly from entities (Gemini now returns start_date and end_date)
        start_date = entities.get("start_date")
        end_date = entities.get("end_date")
        
        # If dates are not provided, default to last 7 days
        if not start_date or not end_date:
            today = datetime.now().date()
            default_start = today - timedelta(days=6)
            start_date = start_date or default_start.strftime('%Y-%m-%d')
            end_date = end_date or today.strftime('%Y-%m-%d')
        
        return ParseCommandResponse(
            location=location_result,
            language=language,
            start_date=start_date,
            end_date=end_date
        )
    
    except Exception as e:
        logger.error(f"Error parsing command: {str(e)}")
        # Return default date range on error
        today = datetime.now().date()
        default_start = today - timedelta(days=6)
        return ParseCommandResponse(
            start_date=default_start.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d')
        )


@router.get("/{event_id}/explain/stream")
async def stream_explanation(event_id: str, language: str = "en"):
    """
    Stream event explanation as SSE.
    
    Agent workflow:
    1. Retrieve memory (cache and pin)
    2. Plan sub-tasks
    3. Execute tasks (streaming)
    4. Store in memory
    """
    # 1. Retrieve memory
    cache_key = memory.get_explanation_key(event_id, language)
    cached_explanation = memory.retrieve_cache(cache_key)
    
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
    
    # Get pin from memory
    pin = memory.retrieve_pin(event_id)
    if not pin:
        pin = memory.find_pin_in_cache(event_id)
    
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
            confidence=0.5,
            positivity_scale=0.5
        )
    
    # 2. Plan sub-tasks
    tasks = planner.plan_explanation(pin, language)
    
    # 3. Execute tasks (streaming)
    try:
        explanation_stream = executor.execute_task(tasks[0], {})
        
        # Collect explanation for caching
        explanation_text = ""
        
        def stream_with_cache():
            nonlocal explanation_text
            for chunk in explanation_stream:
                explanation_text += chunk
                yield chunk
            
            # 4. Store in memory
            memory.set_explanation(cache_key, explanation_text)
        
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
        logger.error(f"Error streaming explanation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming explanation: {str(e)}"
        )


@router.post("/{event_id}/chat/stream")
async def stream_chat(event_id: str, request: ChatRequest):
    """
    Stream Q&A response for an event.
    
    Agent workflow:
    1. Retrieve memory (pin)
    2. Plan sub-tasks
    3. Execute tasks (streaming)
    """
    # 1. Retrieve memory
    pin = memory.retrieve_pin(event_id)
    if not pin:
        pin = memory.find_pin_in_cache(event_id)
    
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
    
    # 2. Plan sub-tasks
    tasks = planner.plan_chat_response(
        event_id=event_id,
        pin=pin,
        question=request.question,
        history=request.history,
        language=request.language
    )
    
    # 3. Execute tasks (streaming)
    try:
        chat_stream = executor.execute_task(tasks[0], {})
        
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
        logger.error(f"Error streaming chat: {e}")
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
    """
    await websocket.accept()
    
    # Initialize session
    session_id = f"{event_id}_{language}"
    conversation_history = memory.retrieve_conversation(session_id)
    
    # Get pin information
    pin = memory.retrieve_pin(event_id)
    if not pin:
        pin = memory.find_pin_in_cache(event_id)
    
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
            # Receive message from client
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
            except:
                try:
                    data = await websocket.receive_bytes()
                    continue
                except:
                    continue
            
            if message_data.get("type") == "audio":
                # Handle audio input
                audio_data_base64 = message_data.get("data", "")
                audio_format = message_data.get("format", "text")
                
                if not audio_data_base64:
                    continue
                
                try:
                    # Decode base64 to get text transcript
                    if audio_format == "text":
                        user_transcript = base64.b64decode(audio_data_base64).decode('utf-8')
                    else:
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
                    
                    # Build conversation context
                    conversation_context = ""
                    for msg in conversation_history[-3:]:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        conversation_context += f"{role.capitalize()}: {content}\n"
                    
                    user_prompt = f"""{conversation_context}

User: {user_transcript}
Assistant:"""
                    
                    # Call Gemini API with web search enabled
                    response = executor.client.models.generate_content(
                        model=executor.model,
                        contents=[
                            {"role": "user", "parts": [{"text": system_prompt}]},
                            {"role": "user", "parts": [{"text": user_prompt}]}
                        ],
                        config={
                            "temperature": 0.7,
                            "max_output_tokens": 1000,
                            "tools": [{"google_search": {}}],
                        }
                    )
                    
                    assistant_response = response.text
                    
                    # Encode text as base64 for audio response
                    audio_response_base64 = base64.b64encode(assistant_response.encode('utf-8')).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_response_base64,
                        "format": "text"
                    })
                    
                    await websocket.send_json({"type": "done"})
                    
                except Exception as e:
                    error_msg = f"Error processing audio: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                    logger.error(f"Audio processing error: {e}")
            
            elif message_data.get("type") == "message":
                # Handle text message
                user_message = message_data.get("content", "")
                
                if not user_message.strip():
                    continue
                
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
                    response = executor.client.models.generate_content(
                        model=executor.model,
                        contents=[
                            {"role": "user", "parts": [{"text": system_prompt}]},
                            {"role": "user", "parts": [{"text": user_prompt}]}
                        ],
                        config={
                            "temperature": 0.7,
                            "max_output_tokens": 2000,
                            "tools": [{"google_search": {}}],
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
                    logger.error(f"Gemini API error: {e}")
            
    except WebSocketDisconnect:
        # Clean up session when client disconnects
        memory.clear_conversation(session_id)
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            })
        except:
            pass
        # Clean up on error
        memory.clear_conversation(session_id)


@router.get("/random-event", response_model=ParseCommandResponse)
async def get_random_event():
    """
    Get a random interesting historic event with location and date.
    
    Agent workflow:
    1. Plan sub-tasks
    2. Execute tasks
    3. Return response
    """
    # 1. Plan sub-tasks
    tasks = planner.plan_random_event()
    
    # 2. Execute tasks
    try:
        context = {}
        for task in tasks:
            result = executor.execute_task(task, context)
            context[task.name] = result
        
        # Extract results from context
        event_data = context.get("generate_random_event", {})
        location_result = context.get("geocode_location")
        
        # Get location name and geocode if needed
        location_name = event_data.get("location_name")
        if location_name and not location_result:
            location_result = executor.call_geocoding(location_name)
            if location_result:
                location_result = {
                    "lat": location_result["lat"],
                    "lng": location_result["lng"],
                    "name": location_result.get("display_name", location_name)
                }
        
        # Get dates directly from event_data (Gemini now returns start_date and end_date)
        start_date = event_data.get("start_date")
        end_date = event_data.get("end_date")
        
        # Get language from event_data
        language = event_data.get("language")
        if language and language.lower() in ["null", "none", ""]:
            language = None
        
        # If dates are not provided, fallback to default
        if not start_date or not end_date:
            today = datetime.now().date()
            default_start = today - timedelta(days=6)
            start_date = start_date or default_start.strftime('%Y-%m-%d')
            end_date = end_date or today.strftime('%Y-%m-%d')
        
        return ParseCommandResponse(
            location=location_result,
            language=language,
            start_date=start_date,
            end_date=end_date
        )
    
    except Exception as e:
        logger.error(f"Error getting random event: {str(e)}")
        # Fallback: return a default historic event
        try:
            geocoded = executor.call_geocoding("Philadelphia")
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
    """
    try:
        # Get the real API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY not found in server environment"
            )
        
        # Create Gemini client with v1alpha API version
        from google import genai
        client = genai.Client(
            api_key=api_key,
            http_options={'api_version': 'v1alpha'}
        )
        
        # Create ephemeral token
        now = datetime.now(tz=timezone.utc)
        expire_time = now + timedelta(minutes=30)
        new_session_expire_time = now + timedelta(minutes=1)
        
        token = client.auth_tokens.create(
            config={
                'uses': 1,
                'expire_time': expire_time.isoformat(),
                'new_session_expire_time': new_session_expire_time.isoformat(),
                'http_options': {'api_version': 'v1alpha'},
            }
        )
        
        return {
            "token": token.name,
            "expires_at": expire_time.isoformat(),
            "new_session_expires_at": new_session_expire_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating ephemeral token: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating ephemeral token: {str(e)}"
        )
