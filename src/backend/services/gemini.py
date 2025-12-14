"""
Gemini API service for generating pins, explanations, and chat responses.

Reuses Gemini client setup from the original executor.py.
"""

import os
import json
import re
import base64
import logging
from typing import Iterator, List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

from ..models import Pin, Viewport
from .news import GeocodingService

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
        self.model = "gemini-2.0-flash"
        self.geocoding_service = GeocodingService()
    
    def generate_pins(
        self,
        start_date: str,
        end_date: str,
        viewport: Viewport,
        language: str = "en",
        max_pins: int = 10
    ) -> List[Pin]:
        """
        Generate event pins for a given date range and viewport.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            viewport: Map viewport with bbox and zoom
            language: Language code
            max_pins: Maximum number of pins to generate
            
        Returns:
            List of Pin objects
        """
        # Determine if we should focus on local or global events
        zoom = viewport.zoom
        is_local = zoom >= 6
        
        # Calculate approximate region name from viewport for better web search
        center_lat = (viewport.bbox.north + viewport.bbox.south) / 2
        center_lng = (viewport.bbox.east + viewport.bbox.west) / 2
        
        # Build prompt with web search instructions
        system_instruction = """You are a world events curator. Your task is to identify significant historical events or LOCAL news that occurred on a specific date or date period, relevant to a geographic viewport.

CRITICAL: You MUST use web search to find REAL, ACCURATE and LOCAL news and events from reliable sources for the specified date. 
- Search for news articles, historical records, and verified sources
- Reference credible news outlets, historical databases, and official records
- Cite your sources when possible
- DO NOT make up or hallucinate events - only use information from web search results

Your job is to:
1. Use web search to find significant events/news for the exact date and region
2. Extract the most significant events from reliable sources
3. Identify the EXACT LOCATION where each event occurred or is most relevant
4. Place pins at the CLOSEST POSSIBLE LOCATION that is relevant to the news/event
5. Ensure pins are within or as close as possible to the viewport bounding box
6. Curate eye-catching titles and one-liners to attract attention and engagement

Return STRICT JSON only - no markdown, no explanations, just valid JSON matching this exact schema:
{
  "pins": [
    {
      "event_id": "evt_YYYY-MM-DD_location_001",
      "title": "Eye-catching title",
      "date": "YYYY-MM-DD",
      "lat": 0.0,
      "lng": 0.0,
      "location_label": "Specific Place, City, Country",
      "category": "politics|conflict|culture|science|economics|other",
      "significance_score": 0.0-1.0,
      "one_liner": "Eye-catching one-liner",
      "confidence": 0.0-1.0,
      "positivity_scale": 0.0-1.0,
      "related_event_ids": ["evt_..."] or null
    }
  ]
}

CRITICAL DATE REQUIREMENTS:
- The date provided is in YYYY-MM-DD format (e.g., "2025-12-14" means December 14, 2025)
- You MUST only return events that occurred on the EXACT date specified, including the EXACT year
- DO NOT return events from different years, even if they occurred on the same month and day
- The "date" field in each pin MUST match the requested date exactly (same year, month, and day)
- If the requested date is "2025-12-14", only return events from December 14, 2025 - NOT from 1819, 1941, or any other year

CRITICAL LOCATION RULES:
- lat/lng MUST be the actual location where the event occurred or is most relevant
- If the event is about a specific city, use that city's coordinates
- If the event is about a country, use the capital or most relevant city's coordinates
- If zoom >= 6: prioritize events WITHIN the viewport bbox, or closest to it
- If zoom < 6: can include globally significant events, but still try to place within viewport if possible
- ALWAYS verify coordinates are within valid ranges: lat [-90, 90], lng [-180, 180]
- location_label MUST be a SPECIFIC place, not a generic location. Examples:
  * GOOD: "Marina Bay, Singapore", "Times Square, New York, USA", "Westminster, London, UK", "Tiananmen Square, Beijing, China"
  * BAD: "Singapore", "New York", "London", "China" (too generic)
  * Prefer specific districts, neighborhoods, landmarks, or notable locations within the city/country

Guidelines:
- ALWAYS use web search to find real events - do not rely on memory alone
- Search for events matching the exact date (year, month, day)
- Use reliable sources: major news outlets, historical databases, official records
- Significance score: 0.9+ for major global events, 0.7-0.9 for regional, 0.5-0.7 for local
- Confidence: 0.9+ for well-documented events from reliable sources, lower for approximate/uncertain
- Positivity scale: 0.0-1.0 where 1.0 is positive/good news (e.g., achievements, celebrations, breakthroughs) and 0.0 is negative/bad news (e.g., conflicts, disasters, crises). Use 0.5 for neutral news. Assess the overall sentiment and impact of the event.
- Keep neutral tone, avoid sensational language
- Prioritize events that are geographically relevant to the viewport
- If web search finds no events for the exact date, indicate this in the confidence score
"""
        
        # Parse dates to extract information
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_year = start_date_obj.year
            end_year = end_date_obj.year
            start_month_day = start_date_obj.strftime("%B %d")
            end_month_day = end_date_obj.strftime("%B %d")
        except:
            start_year = start_date.split("-")[0] if "-" in start_date else "unknown"
            end_year = end_date.split("-")[0] if "-" in end_date else "unknown"
            start_month_day = start_date
            end_month_day = end_date
        
        # Check if it's a single day
        is_single_day = start_date == end_date
        
        # Calculate approximate region name from viewport for better web search
        center_lat = (viewport.bbox.north + viewport.bbox.south) / 2
        center_lng = (viewport.bbox.east + viewport.bbox.west) / 2
        
        # Build region context for web search
        region_context = ""
        if is_local:
            # For local view, provide approximate region
            region_context = f"Region: Approximately centered at {center_lat:.2f}°N, {center_lng:.2f}°E"
        
        # Build date range description
        if is_single_day:
            date_range_desc = f"{start_date} ({start_year}, {start_month_day})"
            date_instruction = f"CRITICAL: You MUST only return events that occurred on {start_date} (the EXACT year {start_year}, month, and day). DO NOT return events from other years, even if they occurred on {start_month_day} in a different year."
            search_instruction = f"- Search for: \"news {start_date}\" OR \"events {start_date}\" OR \"{start_month_day} {start_year} news\""
        else:
            date_range_desc = f"{start_date} to {end_date} ({start_year} to {end_year})"
            date_instruction = f"CRITICAL: You MUST only return events that occurred between {start_date} and {end_date} (inclusive). Events can be from any day within this date range."
            search_instruction = f"- Search for: \"news {start_date} to {end_date}\" OR \"events {start_date} to {end_date}\" OR \"news from {start_date} to {end_date}\""
        
        user_prompt = f"""Date Range: {date_range_desc}

{date_instruction}

MANDATORY WEB SEARCH:
- You MUST use web search to find real news and events for the date range {start_date} to {end_date}
{search_instruction}
- Include region-specific searches if relevant: \"[region] news {start_date} to {end_date}\"
- Only use information from reliable sources found via web search
- Cite sources when possible
- Web search MUST be performed every time to get the most current and accurate information

Viewport: bbox=[{viewport.bbox.west}, {viewport.bbox.south}, {viewport.bbox.east}, {viewport.bbox.north}], zoom={zoom}
{region_context}
MUST Respond in {language}.
Focus: {"Local events within viewport" if is_local else "Globally significant events, but prioritize viewport region"}
Max pins: {max_pins}

Generate pins for significant events between {start_date} and {end_date} (inclusive). For each event:
1. Use web search to find the event - ensure the event date is within the range {start_date} to {end_date}
2. Identify the EXACT, SPECIFIC location where it occurred (e.g., "Marina Bay", "Times Square", "Westminster", NOT just "Singapore", "New York", "London")
3. Use accurate lat/lng coordinates for that specific location
4. Ensure the location is within or as close as possible to the viewport bbox
5. If the event location is outside the viewport but relevant, place it at the closest relevant point within or near the viewport
6. location_label MUST be specific: use districts, neighborhoods, landmarks, or notable places, not just city/country names
7. The "date" field in each pin MUST be a date within the range {start_date} to {end_date} (YYYY-MM-DD format)
8. Base your information on web search results from reliable sources"""

        try:
            # Call Gemini API
            # Calculate token limit dynamically: ~600 tokens per pin, minimum 4000
            token_limit = max(4000, max_pins * 600)
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "user", "parts": [{"text": user_prompt}]}
                ],
                config=types.GenerateContentConfig( # Use the typed config
                    temperature=0.2,
                    tools=[types.Tool(google_search=types.GoogleSearch())], # Explicit typing
                    response_modalities=["TEXT"], 
                    max_output_tokens=token_limit,
                )
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
                    # CRITICAL: Validate that the pin date is within the requested date range
                    pin_date = pin_data.get("date", "")
                    if not self._is_date_in_range(pin_date, start_date, end_date):
                        logger.warning(f"Skipping pin with date outside range: pin_date={pin_date}, range={start_date} to {end_date}")
                        continue
                    
                    # Validate and potentially geocode location
                    lat = pin_data.get("lat", 0)
                    lng = pin_data.get("lng", 0)
                    location_label = pin_data.get("location_label", "")
                    
                    # Check if location_label is too generic and try to make it more specific
                    location_label = self._make_location_specific(location_label, viewport)
                    pin_data["location_label"] = location_label
                    
                    # Only geocode if coordinates are invalid (0,0) - don't re-geocode based on viewport
                    # This ensures pins use actual geographic coordinates that don't change when map moves
                    if lat == 0 and lng == 0:
                        # Try to geocode the location
                        # DO NOT use viewport bbox - geocoding should return actual geographic coordinates
                        geocoded = self.geocoding_service.geocode_location(
                            location_label
                            # Removed bbox parameter - geocoding should be viewport-independent
                        )
                        if geocoded:
                            pin_data["lat"] = geocoded["lat"]
                            pin_data["lng"] = geocoded["lng"]
                            # Use geocoded display_name only if it's more specific than what we have
                            if geocoded.get("display_name"):
                                geocoded_name = geocoded["display_name"]
                                # Prefer the geocoded name if it contains more detail
                                if self._is_more_specific(geocoded_name, location_label):
                                    pin_data["location_label"] = geocoded_name
                                else:
                                    pin_data["location_label"] = location_label
                    
                    # Ensure coordinates are within valid ranges
                    pin_data["lat"] = max(-90, min(90, pin_data.get("lat", 0)))
                    pin_data["lng"] = max(-180, min(180, pin_data.get("lng", 0)))
                    
                    # Keep the pin's date as-is (it's already validated to be in range)
                    
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
            partial_pins = self._extract_partial_pins(failed_text, start_date=start_date, end_date=end_date)
            if partial_pins:
                logger.info(f"Extracted {len(partial_pins)} valid pins from partial JSON")
                return partial_pins
            
            # If partial extraction failed, retry with Gemini
            logger.warning("Partial extraction failed, retrying with Gemini")
            logger.debug(f"Failed JSON text (first 1000 chars): {failed_text[:1000] if isinstance(failed_text, str) else 'N/A'}")
            try:
                fix_prompt = f"{user_prompt}\n\nThe previous response had invalid JSON. Please return ONLY valid JSON matching the schema, no markdown. Return a JSON object with a 'pins' array. Ensure all strings are properly escaped and closed. Do not include incomplete objects."
                # Calculate token limit dynamically: ~600 tokens per pin, minimum 4000
                token_limit = max(4000, max_pins * 600)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=fix_prompt,
                    config=types.GenerateContentConfig( # Use the typed config
                        temperature=0.1,
                        tools=[types.Tool(google_search=types.GoogleSearch())], # Explicit typing
                        response_modalities=["TEXT"], 
                        max_output_tokens=token_limit,
                    )
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
                    partial_pins = self._extract_partial_pins(text, start_date=start_date, end_date=end_date)
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
                    # CRITICAL: Validate that the pin date is within the requested date range
                    pin_date = p.get("date", "")
                    if not self._is_date_in_range(pin_date, start_date, end_date):
                        logger.warning(f"Skipping pin with date outside range: pin_date={pin_date}, range={start_date} to {end_date}")
                        continue
                    
                    if self._validate_pin(p):
                        try:
                            # Keep the pin's date as-is (it's already validated to be in range)
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
    
    def _is_date_in_range(self, date_str: str, start_date: str, end_date: str) -> bool:
        """Check if a date string is within the given date range (inclusive)."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            return start_obj <= date_obj <= end_obj
        except (ValueError, AttributeError):
            return False
    
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
                        required_fields = ['event_id', 'title', 'date', 'lat', 'lng', 'location_label', 'category', 'significance_score', 'one_liner', 'confidence', 'positivity_scale']
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
    
    def _extract_partial_pins(self, text: str, start_date: str = None, end_date: str = None) -> List[Pin]:
        """
        Try to extract valid pin objects from partial/invalid JSON.
        Uses regex to find complete pin objects even if the overall JSON is invalid.
        
        Args:
            text: Text containing JSON (possibly invalid)
            start_date: If provided, only extract pins with dates >= start_date
            end_date: If provided, only extract pins with dates <= end_date
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
        pin_pattern += r',\s*"positivity_scale":\s*([\d.]+)'
        
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
                    "positivity_scale": float(match.group(11)),
                    "related_event_ids": None
                }
                
                # CRITICAL: Validate that the pin date is within the date range if specified
                pin_date = pin_data.get("date", "")
                if start_date and end_date and not self._is_date_in_range(pin_date, start_date, end_date):
                    logger.debug(f"Skipping partial pin with date outside range: pin_date={pin_date}, range={start_date} to {end_date}")
                    continue
                
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
    
    def _make_location_specific(self, location_label: str, viewport: Viewport) -> str:
        """
        Try to make a generic location more specific.
        
        If location has fewer than 2 comma-separated parts, it's likely generic
        (e.g., "Singapore" or "New York" instead of "Marina Bay, Singapore").
        Try to geocode and get a more specific place name.
        """
        if not location_label:
            return location_label
        
        # Check if location is generic (has fewer than 2 comma-separated parts)
        parts = [p.strip() for p in location_label.split(",")]
        is_generic = len(parts) < 2
        
        # If it's generic, try to geocode and get a more specific name
        if is_generic:
            try:
                # DO NOT use viewport bbox - geocoding should return actual geographic coordinates
                geocoded = self.geocoding_service.geocode_location(
                    location_label
                    # Removed bbox parameter - geocoding should be viewport-independent
                )
                if geocoded and geocoded.get("display_name"):
                    # Nominatim display_name format: "Place, District, City, Region, Country"
                    # Extract a more specific part (first 2-3 components)
                    display_name = geocoded["display_name"]
                    geocoded_parts = [p.strip() for p in display_name.split(",")]
                    # Take first 2-3 parts for specificity (e.g., "Marina Bay, Downtown Core, Singapore")
                    if len(geocoded_parts) >= 2:
                        # Combine first 2-3 parts for a specific but readable location
                        specific_parts = geocoded_parts[:min(3, len(geocoded_parts))]
                        return ", ".join(specific_parts)
                    return display_name
            except Exception as e:
                logger.debug(f"Error making location specific: {e}")
        
        return location_label
    
    def _is_more_specific(self, name1: str, name2: str) -> bool:
        """
        Check if name1 is more specific than name2.
        More specific = has more components (parts separated by commas).
        """
        if not name1 or not name2:
            return False
        
        parts1 = [p.strip() for p in name1.split(",")]
        parts2 = [p.strip() for p in name2.split(",")]
        
        # More specific if it has more parts, or same parts but longer
        if len(parts1) > len(parts2):
            return True
        elif len(parts1) == len(parts2):
            # Same number of parts, check if first part is more detailed
            return len(parts1[0]) > len(parts2[0]) if parts1 and parts2 else False
        return False
    
    def stream_explanation(
        self,
        pin: Pin,
        language: str = "en"
    ) -> Iterator[str]:
        """
        Stream a TLDR news article for an event pin.
        
        Args:
            pin: Pin object to write about
            language: Language code
            
        Yields:
            Text chunks of the news article
        """
        prompt = f"""You are a professional news writer. Write a concise TLDR news article about this event. Include **bold** for important sentences (at least 3 instances).

Event:
- Title: {pin.title}
- Date: {pin.date}
- Location: {pin.location_label} ({pin.lat}, {pin.lng})
- Category: {pin.category}
- Significance: {pin.significance_score}

Write a news article in {language} that reads like a brief news report. 
IMPORTANT RULES for the ARTICLE:
- NO TITLE as title would be provided
- DO NOT mention the lat and longitude in the article
- DO NOT mention the significance score in the article
- DO give A compelling headline-style opening paragraph (2-3 sentences)
- DO include key facts about what happened
- DO include why this event is significant
- DO include relevant context

Keep it concise (200-300 words). Write in a journalistic style as a TLDR - users can ask for more details if needed."""

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

