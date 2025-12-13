"""
Gemini API service for generating pins, explanations, and chat responses.

Reuses Gemini client setup from the original executor.py.
"""

import os
import json
import re
import logging
from typing import Iterator, List, Dict, Any, Optional
from dotenv import load_dotenv
from google import genai

from ..models import Pin, Viewport
from .news import NewsService, GeocodingService

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Gemini API."""
    
    def __init__(self):
        """Initialize Gemini client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables. "
                "Please create a .env file with your API key."
            )
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"
        self.news_service = NewsService()
        self.geocoding_service = GeocodingService()
    
    def generate_pins(
        self,
        date: str,
        viewport: Viewport,
        language: str = "en",
        max_pins: int = 8
    ) -> List[Pin]:
        """
        Generate event pins for a given date and viewport.
        
        Args:
            date: Date in YYYY-MM-DD format
            viewport: Map viewport with bbox and zoom
            language: Language code
            max_pins: Maximum number of pins to generate
            
        Returns:
            List of Pin objects
        """
        # Determine if we should focus on local or global events
        zoom = viewport.zoom
        is_local = zoom >= 6
        
        # Fetch real news articles for the date and region
        news_articles = self.news_service.fetch_news(
            date=date,
            bbox={
                "west": viewport.bbox.west,
                "south": viewport.bbox.south,
                "east": viewport.bbox.east,
                "north": viewport.bbox.north,
            },
            language=language,
            max_results=max_pins * 3  # Get more articles to filter from
        )
        
        # Build prompt with real news data
        system_instruction = """You are a world events curator. Your task is to identify significant historical events or news that occurred on a specific date, relevant to a geographic viewport.

You will be provided with REAL NEWS ARTICLES from that date. Your job is to:
1. Extract the most significant events from the news articles
2. Identify the EXACT LOCATION where each event occurred or is most relevant
3. Place pins at the CLOSEST POSSIBLE LOCATION that is relevant to the news/event
4. Ensure pins are within or as close as possible to the viewport bounding box

Return STRICT JSON only - no markdown, no explanations, just valid JSON matching this exact schema:
{
  "pins": [
    {
      "event_id": "evt_YYYY-MM-DD_location_001",
      "title": "Event Title",
      "date": "YYYY-MM-DD",
      "lat": 0.0,
      "lng": 0.0,
      "location_label": "City, Country",
      "category": "politics|conflict|culture|science|economics|other",
      "significance_score": 0.0-1.0,
      "one_liner": "One sentence preview",
      "confidence": 0.0-1.0,
      "related_event_ids": ["evt_..."] or null
    }
  ]
}

CRITICAL LOCATION RULES:
- lat/lng MUST be the actual location where the event occurred or is most relevant
- If the event is about a specific city, use that city's coordinates
- If the event is about a country, use the capital or most relevant city's coordinates
- If zoom >= 6: prioritize events WITHIN the viewport bbox, or closest to it
- If zoom < 6: can include globally significant events, but still try to place within viewport if possible
- ALWAYS verify coordinates are within valid ranges: lat [-90, 90], lng [-180, 180]
- location_label should be the actual place name (e.g., "New York, USA", "London, UK")

Guidelines:
- Use REAL events from the provided news articles
- If no news articles provided, you can suggest historical events for that date
- Significance score: 0.9+ for major global events, 0.7-0.9 for regional, 0.5-0.7 for local
- Confidence: 0.9+ for well-documented events, lower for approximate/uncertain
- Keep neutral tone, avoid sensational language
- Prioritize events that are geographically relevant to the viewport
"""
        
        # Build news context
        news_context = ""
        if news_articles:
            news_context = "\n\nREAL NEWS ARTICLES FROM THIS DATE:\n"
            for i, article in enumerate(news_articles[:10], 1):  # Limit to 10 articles
                news_context += f"\n{i}. {article.get('title', 'No title')}\n"
                if article.get('description'):
                    news_context += f"   {article.get('description')}\n"
                if article.get('source'):
                    news_context += f"   Source: {article.get('source')}\n"
        else:
            news_context = "\n\nNote: No news articles found for this date. You may suggest historical events that occurred on this date."
        
        user_prompt = f"""Date: {date}
Viewport: bbox=[{viewport.bbox.west}, {viewport.bbox.south}, {viewport.bbox.east}, {viewport.bbox.north}], zoom={zoom}
Language: {language}
Focus: {"Local events within viewport" if is_local else "Globally significant events, but prioritize viewport region"}
Max pins: {max_pins}

{news_context}

Generate pins for significant events on this date. For each event:
1. Extract the event from the news articles (if available)
2. Identify the EXACT location where it occurred
3. Use accurate lat/lng coordinates for that location
4. Ensure the location is within or as close as possible to the viewport bbox
5. If the event location is outside the viewport but relevant, place it at the closest relevant point within or near the viewport"""

        try:
            # Call Gemini API
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "user", "parts": [{"text": user_prompt}]}
                ],
                config={
                    "temperature": 0.2,  # Low temperature for structured output
                    "max_output_tokens": 4000,
                }
            )
            
            # Parse JSON response
            raw_text = response.text.strip()
            logger.info(f"Raw Gemini response length: {len(raw_text)} chars")
            logger.debug(f"Raw Gemini response (first 500 chars): {raw_text[:500]}")
            
            # Remove markdown code blocks if present (handle multiple formats)
            text = self._extract_json_from_text(raw_text)
            logger.info(f"Extracted JSON text length: {len(text)} chars")
            logger.debug(f"Extracted JSON text (first 500 chars): {text[:500]}")
            
            try:
                data = json.loads(text)
                logger.info(f"Successfully parsed JSON, type: {type(data)}")
            except json.JSONDecodeError as parse_error:
                logger.error(f"JSON parse error at line {parse_error.lineno}, col {parse_error.colno}: {parse_error.msg}")
                logger.error(f"Problematic text around error (char {parse_error.pos}): {text[max(0, parse_error.pos-100):parse_error.pos+100]}")
                raise
            # Handle case where data might be a list or not a dict
            if isinstance(data, dict):
                pins_data = data.get("pins", [])
            elif isinstance(data, list):
                # If Gemini returns a list directly, use it
                pins_data = data
            else:
                print(f"Warning: Unexpected data type: {type(data)}")
                pins_data = []
            
            # Validate and create Pin objects, and ensure locations are accurate
            pins = []
            for pin_data in pins_data[:max_pins]:
                try:
                    # Validate and potentially geocode location
                    lat = pin_data.get("lat", 0)
                    lng = pin_data.get("lng", 0)
                    location_label = pin_data.get("location_label", "")
                    
                    # If coordinates seem invalid or location doesn't match, try geocoding
                    if (lat == 0 and lng == 0) or not self._is_in_viewport(lat, lng, viewport):
                        # Try to geocode the location
                        geocoded = self.geocoding_service.geocode_location(
                            location_label,
                            bbox={
                                "west": viewport.bbox.west,
                                "south": viewport.bbox.south,
                                "east": viewport.bbox.east,
                                "north": viewport.bbox.north,
                            }
                        )
                        if geocoded:
                            pin_data["lat"] = geocoded["lat"]
                            pin_data["lng"] = geocoded["lng"]
                            if geocoded.get("display_name"):
                                pin_data["location_label"] = geocoded["display_name"]
                    
                    # Ensure coordinates are within valid ranges
                    pin_data["lat"] = max(-90, min(90, pin_data.get("lat", 0)))
                    pin_data["lng"] = max(-180, min(180, pin_data.get("lng", 0)))
                    
                    pin = Pin(**pin_data)
                    pins.append(pin)
                except Exception as e:
                    # Skip invalid pins
                    print(f"Warning: Invalid pin data: {e}")
                    continue
            
            return pins
            
        except json.JSONDecodeError as e:
            # Try to extract valid pins from partial JSON before retrying
            logger.warning(f"JSON parse error, attempting to extract partial data: {e.msg} at line {e.lineno}, col {e.colno}")
            # text might not be defined if error happened before extraction
            failed_text = text if 'text' in locals() else raw_text if 'raw_text' in locals() else ""
            
            # Try to extract valid pins from partial JSON
            partial_pins = self._extract_partial_pins(failed_text)
            if partial_pins:
                logger.info(f"Extracted {len(partial_pins)} valid pins from partial JSON")
                return partial_pins
            
            # If partial extraction failed, retry with Gemini
            logger.warning("Partial extraction failed, retrying with Gemini")
            logger.debug(f"Failed JSON text (first 1000 chars): {failed_text[:1000] if isinstance(failed_text, str) else 'N/A'}")
            try:
                fix_prompt = f"{user_prompt}\n\nThe previous response had invalid JSON. Please return ONLY valid JSON matching the schema, no markdown. Return a JSON object with a 'pins' array. Ensure all strings are properly escaped and closed. Do not include incomplete objects."
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=fix_prompt,
                    config={"temperature": 0.1, "max_output_tokens": 4000}
                )
                raw_text = response.text.strip()
                logger.info(f"Retry response length: {len(raw_text)} chars")
                text = self._extract_json_from_text(raw_text)
                logger.debug(f"Retry extracted JSON (first 500 chars): {text[:500]}")
                try:
                    data = json.loads(text)
                    logger.info("Retry JSON parse successful")
                except json.JSONDecodeError as retry_error:
                    logger.error(f"Retry JSON parse error at line {retry_error.lineno}, col {retry_error.colno}: {retry_error.msg}")
                    logger.error(f"Retry problematic text around error (char {retry_error.pos}): {text[max(0, retry_error.pos-100):retry_error.pos+100]}")
                    # Try partial extraction one more time
                    partial_pins = self._extract_partial_pins(text)
                    if partial_pins:
                        logger.info(f"Extracted {len(partial_pins)} valid pins from retry partial JSON")
                        return partial_pins
                    raise
                
                # Handle case where data might be a list or not a dict
                if isinstance(data, dict):
                    pins_data = data.get("pins", [])
                elif isinstance(data, list):
                    pins_data = data
                else:
                    pins_data = []
                
                pins = []
                for p in pins_data[:max_pins]:
                    if self._validate_pin(p):
                        try:
                            pins.append(Pin(**p))
                        except Exception as pin_error:
                            print(f"Warning: Failed to create pin: {pin_error}")
                            continue
                return pins
            except Exception as retry_error:
                print(f"Error in retry: {retry_error}")
                return []
        except Exception as e:
            print(f"Error generating pins: {e}")
            return []
    
    def _validate_pin(self, pin_data: Dict[str, Any]) -> bool:
        """Validate pin data structure."""
        try:
            Pin(**pin_data)
            return True
        except:
            return False
    
    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from text, handling various markdown formats.
        
        Handles:
        - ```json ... ```
        - ``` ... ```
        - Plain JSON
        - JSON with leading/trailing text
        - Unterminated strings (attempts to fix)
        - Incomplete objects in arrays
        """
        original_text = text
        text = text.strip()
        
        # Remove markdown code blocks
        if "```" in text:
            # Find all code blocks
            parts = text.split("```")
            # Look for JSON block (usually the largest or contains "pins")
            json_candidates = []
            for i, part in enumerate(parts):
                part = part.strip()
                # Skip language identifier
                if part.lower().startswith("json"):
                    part = part[4:].strip()
                # Check if it looks like JSON
                if part.startswith("{") or part.startswith("["):
                    json_candidates.append(part)
            
            if json_candidates:
                # Use the longest candidate (usually the actual JSON)
                text = max(json_candidates, key=len)
            else:
                # Fallback: try to find JSON object/array in the text
                json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
                if json_match:
                    text = json_match.group(1)
        
        # Clean up common issues
        text = text.strip()
        
        # Fix incomplete/invalid objects in arrays before other fixes
        # Look for patterns like incomplete event objects: "event_id": "evt_..."}}]
        # Remove incomplete objects from the array
        if '"pins"' in text or text.startswith('['):
            # Try to find and remove incomplete objects
            # Pattern: incomplete object ending with incomplete field like "event_id": "partial"
            # Look for objects that don't have all required fields
            text = self._remove_incomplete_objects(text)
        
        # Fix unterminated strings - handle multi-line strings
        text = self._fix_unterminated_strings(text)
        
        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        
        # Additional fix: try to balance braces/brackets if JSON is cut off
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        if open_braces > 0:
            text += '}' * open_braces
            logger.debug(f"Added {open_braces} closing braces")
        if open_brackets > 0:
            text += ']' * open_brackets
            logger.debug(f"Added {open_brackets} closing brackets")
        
        if text != original_text:
            logger.debug(f"Text was modified during extraction")
        
        return text
    
    def _remove_incomplete_objects(self, text: str) -> str:
        """Remove incomplete objects from JSON arrays."""
        # Look for incomplete objects - objects that are cut off mid-field
        # Pattern: "field": "incomplete_value"}}] or "field": "incomplete_value"}] 
        # where incomplete_value doesn't have closing quote or is incomplete
        
        # Strategy: Find objects that end abruptly with }}] or }] and check if they're complete
        # Look for the pattern where an object ends with incomplete field values
        
        # Pattern 1: Objects ending with incomplete event_id like "event_id": "evt_..."}}]
        # This indicates the object was cut off mid-field
        incomplete_end_patterns = [
            r'"event_id":\s*"[^"]*"}}]',      # Incomplete event_id with double closing braces
            r'"event_id":\s*"[^"]*"}]',       # Incomplete event_id with single closing brace
            r'"[^"]+":\s*"[^"]*"}}]',         # Any incomplete field with double closing braces
            r'"[^"]+":\s*"[^"]*"}]',          # Any incomplete field with single closing brace
        ]
        
        for pattern in incomplete_end_patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                for match in reversed(matches):  # Process from end to start
                    match_end = match.end()
                    match_start = match.start()
                    
                    # Find the start of this object
                    # Look backwards for the opening brace
                    obj_start = text.rfind('{', 0, match_start)
                    if obj_start == -1:
                        # Try to find ", {" pattern
                        comma_brace = text.rfind(', {', 0, match_start)
                        if comma_brace != -1:
                            obj_start = comma_brace + 2
                    
                    if obj_start != -1:
                        # Check if this object has all required fields
                        obj_content = text[obj_start:match_end]
                        required_fields = ['event_id', 'title', 'date', 'lat', 'lng', 'location_label', 'category', 'significance_score', 'one_liner', 'confidence']
                        missing_fields = [field for field in required_fields if f'"{field}"' not in obj_content]
                        
                        # If missing critical fields or has incomplete event_id, remove it
                        if missing_fields or '"event_id": "' in obj_content and not obj_content.count('"event_id": "') == obj_content.count('"event_id": "[^"]*"'):
                            # Remove the incomplete object
                            before_obj = text[:obj_start].rstrip()
                            # Remove comma before object if present
                            if before_obj.endswith(','):
                                before_obj = before_obj[:-1].rstrip()
                            after_obj = text[match_end:]
                            text = before_obj + after_obj
                            logger.debug(f"Removed incomplete object (missing: {missing_fields}) starting at position {obj_start}")
        
        # Also remove objects that end with unterminated strings
        # Pattern: "field": "text...}}] where text doesn't have closing quote
        unterminated_pattern = r'"[^"]+":\s*"[^"]*[^"]"}}]'
        matches = list(re.finditer(unterminated_pattern, text))
        for match in reversed(matches):
            obj_start = text.rfind('{', 0, match.start())
            if obj_start != -1:
                before_obj = text[:obj_start].rstrip()
                if before_obj.endswith(','):
                    before_obj = before_obj[:-1].rstrip()
                after_obj = text[match.end():]
                text = before_obj + after_obj
                logger.debug(f"Removed object with unterminated string at position {obj_start}")
        
        return text
    
    def _fix_unterminated_strings(self, text: str) -> str:
        """Fix unterminated strings in JSON, handling multi-line cases."""
        lines = text.split('\n')
        fixed_lines = []
        in_string = False
        string_start_line = -1
        
        for line_idx, line in enumerate(lines):
            # Track string state across lines
            i = 0
            escaped = False
            new_line = list(line)
            
            while i < len(new_line):
                char = new_line[i]
                
                if escaped:
                    escaped = False
                    i += 1
                    continue
                
                if char == '\\':
                    escaped = True
                    i += 1
                    continue
                
                if char == '"':
                    in_string = not in_string
                    if in_string:
                        string_start_line = line_idx
                    else:
                        string_start_line = -1
                
                i += 1
            
            # If we're still in a string at the end of the line, try to close it
            if in_string:
                # Check if this looks like an incomplete string value
                # Pattern: "field": "text... (no closing quote)
                if re.search(r':\s*"[^"]*$', line):
                    # Add closing quote
                    line = line.rstrip() + '"'
                    in_string = False
                    logger.debug(f"Fixed unterminated string at line {line_idx + 1}")
                # Or if it's a continuation, make sure it's properly handled
                elif line_idx > 0 and string_start_line >= 0:
                    # This is a continuation line, might need to escape it or close it
                    # For now, just ensure it doesn't break JSON structure
                    pass
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _extract_partial_pins(self, text: str) -> List[Pin]:
        """
        Try to extract valid pin objects from partial/invalid JSON.
        Uses regex to find complete pin objects even if the overall JSON is invalid.
        """
        pins = []
        
        # More flexible pattern that handles escaped quotes and optional fields
        # Match pin objects with all required fields, allowing for escaped quotes in strings
        # Pattern matches: { "field": "value", ... } where value can contain escaped quotes
        pin_pattern = r'\{\s*"event_id":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"title":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"date":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"lat":\s*([-\d.]+)'
        pin_pattern += r',\s*"lng":\s*([-\d.]+)'
        pin_pattern += r',\s*"location_label":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"category":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"significance_score":\s*([\d.]+)'
        pin_pattern += r',\s*"one_liner":\s*"((?:[^"\\]|\\.)*)"'
        pin_pattern += r',\s*"confidence":\s*([\d.]+)'
        
        matches = re.finditer(pin_pattern, text, re.DOTALL)
        for match in matches:
            try:
                # Unescape string values
                def unescape(s):
                    return s.replace('\\"', '"').replace('\\\\', '\\')
                
                pin_data = {
                    "event_id": unescape(match.group(1)),
                    "title": unescape(match.group(2)),
                    "date": unescape(match.group(3)),
                    "lat": float(match.group(4)),
                    "lng": float(match.group(5)),
                    "location_label": unescape(match.group(6)),
                    "category": unescape(match.group(7)),
                    "significance_score": float(match.group(8)),
                    "one_liner": unescape(match.group(9)),
                    "confidence": float(match.group(10)),
                    "related_event_ids": None
                }
                
                # Validate and create pin
                if self._validate_pin(pin_data):
                    pins.append(Pin(**pin_data))
                    logger.debug(f"Extracted partial pin: {pin_data['event_id']}")
            except (ValueError, IndexError, AttributeError) as e:
                logger.debug(f"Failed to extract pin from match: {e}")
                continue
        
        return pins
    
    def _is_in_viewport(self, lat: float, lng: float, viewport: Viewport) -> bool:
        """Check if coordinates are within viewport bbox."""
        return (
            viewport.bbox.south <= lat <= viewport.bbox.north and
            viewport.bbox.west <= lng <= viewport.bbox.east
        )
    
    def stream_explanation(
        self,
        pin: Pin,
        language: str = "en"
    ) -> Iterator[str]:
        """
        Stream explanation for an event pin.
        
        Args:
            pin: Pin object to explain
            language: Language code
            
        Yields:
            Text chunks of the explanation
        """
        prompt = f"""You are a knowledgeable history teacher explaining a significant event.

Event:
- Title: {pin.title}
- Date: {pin.date}
- Location: {pin.location_label} ({pin.lat}, {pin.lng})
- Category: {pin.category}
- Significance: {pin.significance_score}

Provide a clear, educational explanation in {language} with this structure:
1. One sentence summary
2. What happened (2-3 bullets)
3. Why it matters (2-3 bullets)
4. Context (1-2 bullets)
5. What to watch next (if current/recent event)

Keep it concise (200-300 words). Use bullet points with • symbol."""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0.6,
                    "max_output_tokens": 1000,
                }
            )
            
            # Stream the response in chunks (simulate streaming)
            text = response.text
            chunk_size = 50
            for i in range(0, len(text), chunk_size):
                yield text[i:i + chunk_size]
                
        except Exception as e:
            yield f"Error generating explanation: {str(e)}"
    
    def stream_chat(
        self,
        event_id: str,
        pin: Pin,
        question: str,
        history: List[Dict[str, str]],
        language: str = "en"
    ) -> Iterator[str]:
        """
        Stream chat response for event Q&A.
        
        Args:
            event_id: Event identifier
            pin: Pin object
            question: User question
            history: Chat history
            language: Language code
            
        Yields:
            Text chunks of the response
        """
        # Build context from history
        context = ""
        if history:
            context = "\nPrevious conversation:\n"
            for msg in history[-3:]:  # Last 3 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context += f"{role.capitalize()}: {content}\n"
        
        prompt = f"""You are a helpful guide answering questions about a historical event.

Event:
- Title: {pin.title}
- Date: {pin.date}
- Location: {pin.location_label}
- Category: {pin.category}

{context}

User question: {question}

Answer the question clearly and concisely in {language}. If helpful, end with one follow-up question to deepen understanding."""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0.7,
                    "max_output_tokens": 800,
                }
            )
            
            # Stream the response in chunks
            text = response.text
            chunk_size = 50
            for i in range(0, len(text), chunk_size):
                yield text[i:i + chunk_size]
                
        except Exception as e:
            yield f"Error generating response: {str(e)}"

