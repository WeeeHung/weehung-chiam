"""
Executor module for executing tasks by calling LLMs and tools.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.genai import types

from .planner import Task
from ..gemini import GeminiService
from ..news import GeocodingService
from ...models import Pin, Viewport

load_dotenv()
logger = logging.getLogger(__name__)


class Executor:
    """Executes tasks by calling appropriate tools and LLMs."""
    
    def __init__(self):
        """Initialize executor with services."""
        self.gemini_service = GeminiService()
        self.geocoding_service = GeocodingService()
        self.client = self.gemini_service.client
        self.model = self.gemini_service.model
    
    def execute_task(self, task: Task, context: Dict[str, Any]) -> Any:
        """
        Execute a task by routing to appropriate tool handler.
        
        Args:
            task: Task to execute
            context: Results from previous tasks (keyed by task name)
            
        Returns:
            Result of task execution
        """
        # Check dependencies
        for dep in task.dependencies:
            if dep not in context:
                raise ValueError(f"Task {task.name} depends on {dep} which is not in context")
        
        # Fill in params from context
        params = self._resolve_params(task.params, context)
        
        # Route to appropriate handler
        if task.tool == "gemini":
            return self._execute_gemini_task(task, params, context)
        elif task.tool == "geocoding":
            return self._execute_geocoding_task(task, params, context)
        elif task.tool == "web_search":
            return self._execute_web_search_task(task, params, context)
        elif task.tool == "format":
            return self._execute_format_task(task, params, context)
        elif task.tool == "validate":
            return self._execute_validate_task(task, params, context)
        else:
            raise ValueError(f"Unknown tool: {task.tool}")
    
    def _resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter values from context."""
        resolved = {}
        for key, value in params.items():
            if value is None:
                # Try to get from context if key exists
                if key in context:
                    resolved[key] = context[key]
                else:
                    resolved[key] = None
            else:
                resolved[key] = value
        
        # Special handling: if geocoding task and pins not in params, get from search_events
        if "pins" not in resolved and "search_events" in context:
            resolved["pins"] = context["search_events"]
        
        # Special handling: if validate task and pins not in params, get from geocode_locations or search_events
        if "pins" not in resolved:
            if "geocode_locations" in context:
                resolved["pins"] = context["geocode_locations"]
            elif "search_events" in context:
                resolved["pins"] = context["search_events"]
        
        return resolved
    
    def _execute_gemini_task(self, task: Task, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a Gemini API task."""
        operation = params.get("operation")
        
        if operation == "generate_pins":
            return self.gemini_service.generate_pins(
                start_date=params["start_date"],
                end_date=params["end_date"],
                viewport=params["viewport"],
                language=params["language"],
                max_pins=params["max_pins"]
            )
        elif operation == "stream_explanation":
            return self.gemini_service.stream_explanation(
                pin=params["pin"],
                language=params["language"]
            )
        elif operation == "stream_chat":
            return self.gemini_service.stream_chat(
                event_id=params["event_id"],
                pin=params["pin"],
                question=params["question"],
                history=params["history"],
                language=params["language"]
            )
        elif operation == "parse_command":
            return self._parse_command_with_gemini(params["text"])
        elif operation == "random_event":
            return self._generate_random_event_with_gemini()
        else:
            raise ValueError(f"Unknown Gemini operation: {operation}")
    
    def _parse_command_with_gemini(self, text: str) -> Dict[str, Any]:
        """Parse voice command using Gemini, directly extracting start_date and end_date."""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        default_start = today - timedelta(days=6)
        
        system_instruction = """You are a command parser that extracts location name, language code, and date range from user voice commands. 
The user may mention an event or a news article, deduce the most likely intention and extract the location name, language code, and dates accordingly.

Extract:
1. LOCATION_NAME: The place/city/country mentioned (e.g., "Tokyo", "New York", "Johor Bahru"). Return just the location name, nothing else.
2. LANGUAGE: 2-letter ISO code (en, zh, ja, es, fr, de, ko, pt, ru, ar, hi) - extract from phrases like "in chinese" or infer from context
3. START_DATE: Start date in YYYY-MM-DD format
4. END_DATE: End date in YYYY-MM-DD format

CRITICAL DATE RULES:
- If user mentions a YEAR (e.g., "2024", "in 2020"): 
  * START_DATE = YYYY-01-01 (first day of that year)
  * END_DATE = YYYY-12-31 (last day of that year)
- If user mentions a MONTH (e.g., "December 2024", "2024-12"):
  * START_DATE = YYYY-MM-01 (first day of that month)
  * END_DATE = last day of that month (e.g., 2024-12-31 for December)
- If user mentions a single DATE (e.g., "today", "yesterday", "2024-12-14"):
  * START_DATE = END_DATE = that specific date
- If user mentions a DATE RANGE (e.g., "from X to Y"):
  * START_DATE = first date mentioned
  * END_DATE = second date mentioned
- If no date is mentioned:
  * START_DATE = null
  * END_DATE = null (will default to last 7 days)

Return ONLY valid JSON with this exact structure:
{
  "location_name": "string or null",
  "language": "string or null", 
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null"
}"""
        
        user_prompt = f"""Parse this voice command:

Command: "{text}"

Current date: {today.strftime('%Y-%m-%d')}
Yesterday: {yesterday.strftime('%Y-%m-%d')}
Default period (if not specified): last 7 days ({default_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})

Extract location_name, language, start_date, and end_date. Return JSON only."""
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "user", "parts": [{"text": user_prompt}]}
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_modalities=["TEXT"],
                    max_output_tokens=200,
                )
            )
            
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            # Validate and normalize dates
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")
            
            # If dates are provided, ensure they're valid
            if start_date and start_date.lower() not in ["null", "none", ""]:
                try:
                    datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    start_date = None
            
            if end_date and end_date.lower() not in ["null", "none", ""]:
                try:
                    datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    end_date = None
            
            return {
                "location_name": parsed.get("location_name"),
                "language": parsed.get("language"),
                "start_date": start_date if start_date and start_date.lower() not in ["null", "none", ""] else None,
                "end_date": end_date if end_date and end_date.lower() not in ["null", "none", ""] else None
            }
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return {
                "location_name": None,
                "language": None,
                "start_date": None,
                "end_date": None
            }
    
    def _generate_random_event_with_gemini(self) -> Dict[str, Any]:
        """
        Generate random historic event using Gemini with web search.
        First searches for a real historic event, then extracts actual dates from search results.
        """
        today = datetime.now().date()
        
        system_instruction = """You are a historian that finds interesting and significant historic events from world history using web search.

CRITICAL: You MUST use web search to find REAL, VERIFIED historic events. DO NOT make up or hallucinate dates or events.

Process:
1. Use web search to find a random, interesting historic event from any era, any country, any topic
2. Examples: NATO treaty signing, US Declaration of Independence, moon landing, fall of Berlin Wall, 
   Japan surrender in WWII, opening of national parks, peace treaties, major battles, scientific discoveries, etc.
3. Extract the ACTUAL date(s) from the web search results - use the REAL dates from reliable sources
4. Extract the ACTUAL location from the web search results

CRITICAL DATE RULES:
- Dates MUST be in the PAST (before today's date)
- Dates MUST be extracted from web search results, not generated
- If the event occurred on a single DATE: 
  * START_DATE = END_DATE = that specific date (YYYY-MM-DD)
- If the event occurred over a DATE RANGE:
  * START_DATE = first date of the event
  * END_DATE = last date of the event
- For single-day events, START_DATE and END_DATE should be the same
- NEVER return future dates or invalid dates

Return ONLY valid JSON with this exact structure:
{
  "event_name": "Brief name of the event",
  "location_name": "Specific location name (city, country, or landmark)",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "language": "en or null (optional, can be null)"
}"""
        
        user_prompt = f"""Use web search to find a random interesting historic event from world history. 
Search for significant events like major treaties, declarations, battles, discoveries, or cultural milestones.
Extract the ACTUAL dates and location from the web search results.

Today's date: {today.strftime('%Y-%m-%d')}
Make sure the event date is in the PAST (before today).

Return the event name, location name, start_date, end_date, and optionally language in JSON format."""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "user", "parts": [{"text": user_prompt}]}
                ],
                config=types.GenerateContentConfig(
                    temperature=1.0,  # Lower temperature for more reliable results
                    tools=[types.Tool(google_search=types.GoogleSearch())],  # Enable web search
                    response_modalities=["TEXT"],
                    max_output_tokens=300,
                )
            )
            
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            # Validate and normalize dates
            start_date = parsed.get("start_date")
            end_date = parsed.get("end_date")
            
            # Validate dates are in the past and properly formatted
            if start_date and start_date.lower() not in ["null", "none", ""]:
                try:
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                    # Ensure date is in the past
                    if start_date_obj > today:
                        logger.warning(f"Start date {start_date} is in the future, rejecting")
                        start_date = None
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}")
                    start_date = None
            
            if end_date and end_date.lower() not in ["null", "none", ""]:
                try:
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                    # Ensure date is in the past
                    if end_date_obj > today:
                        logger.warning(f"End date {end_date} is in the future, rejecting")
                        end_date = None
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}")
                    end_date = None
            
            # If only one date is provided, use it for both
            if start_date and not end_date:
                end_date = start_date
            elif end_date and not start_date:
                start_date = end_date
            
            # Final validation - if dates are still invalid, use fallback
            if not start_date or not end_date:
                logger.warning("Invalid dates from Gemini, using fallback event")
                return {
                    "event_name": "US Declaration of Independence",
                    "location_name": "Philadelphia",
                    "start_date": "1776-07-04",
                    "end_date": "1776-07-04",
                    "language": None
                }
            
            return {
                "event_name": parsed.get("event_name", "Historic Event"),
                "location_name": parsed.get("location_name"),
                "start_date": start_date,
                "end_date": end_date,
                "language": parsed.get("language") if parsed.get("language") and parsed.get("language").lower() not in ["null", "none", ""] else None
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from Gemini response: {e}")
            logger.debug(f"Response text: {response_text if 'response_text' in locals() else 'N/A'}")
            return {
                "event_name": "US Declaration of Independence",
                "location_name": "Philadelphia",
                "start_date": "1776-07-04",
                "end_date": "1776-07-04",
                "language": None
            }
        except Exception as e:
            logger.error(f"Error generating random event: {e}")
            return {
                "event_name": "US Declaration of Independence",
                "location_name": "Philadelphia",
                "start_date": "1776-07-04",
                "end_date": "1776-07-04",
                "language": None
            }
    
    def _execute_geocoding_task(self, task: Task, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a geocoding task."""
        if "pins" in params and params["pins"] is not None:
            # Geocode locations for pins
            pins = params["pins"]
            geocoded_pins = []
            for pin in pins:
                if isinstance(pin, Pin):
                    # If already a Pin object, check if needs geocoding
                    if pin.lat == 0 and pin.lng == 0 and pin.location_label:
                        geocoded = self.geocoding_service.geocode_location(pin.location_label)
                        if geocoded:
                            # Create new pin with geocoded coordinates
                            pin_dict = pin.dict()
                            pin_dict["lat"] = geocoded["lat"]
                            pin_dict["lng"] = geocoded["lng"]
                            if geocoded.get("display_name"):
                                pin_dict["location_label"] = geocoded["display_name"]
                            geocoded_pins.append(Pin(**pin_dict))
                        else:
                            geocoded_pins.append(pin)
                    else:
                        geocoded_pins.append(pin)
                elif isinstance(pin, dict):
                    # Handle dict format
                    location_label = pin.get("location_label", "")
                    if location_label and (pin.get("lat") == 0 and pin.get("lng") == 0):
                        geocoded = self.geocoding_service.geocode_location(location_label)
                        if geocoded:
                            pin["lat"] = geocoded["lat"]
                            pin["lng"] = geocoded["lng"]
                            if geocoded.get("display_name"):
                                pin["location_label"] = geocoded["display_name"]
                    geocoded_pins.append(pin)
                else:
                    geocoded_pins.append(pin)
            return geocoded_pins
        elif "location_name" in params:
            # Geocode a single location
            location_name = params["location_name"]
            if location_name and location_name.lower() not in ["null", "none", ""]:
                geocoded = self.geocoding_service.geocode_location(location_name)
                if geocoded:
                    return {
                        "lat": geocoded["lat"],
                        "lng": geocoded["lng"],
                        "name": geocoded.get("display_name", location_name)
                    }
            return None
        else:
            raise ValueError("Geocoding task requires 'pins' or 'location_name' parameter")
    
    def _execute_web_search_task(self, task: Task, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a web search task (uses Gemini's built-in web search)."""
        # Web search is handled via Gemini's tools parameter
        # This is a placeholder for future web search operations
        return {}
    
    def _execute_format_task(self, task: Task, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute a formatting task (e.g., date parsing)."""
        if "date_period" in params:
            return self._parse_date_period(params["date_period"])
        return {}
    
    def _execute_validate_task(self, task: Task, params: Dict[str, Any], context: Dict[str, Any]) -> List[Pin]:
        """Execute a validation task for pins."""
        pins_data = params.get("pins", [])
        if not pins_data:
            return []
        
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        
        validated_pins = []
        for pin_data in pins_data:
            if isinstance(pin_data, Pin):
                # Already a Pin object, validate date and coordinates
                if start_date and end_date and not self._is_date_in_range(pin_data.date, start_date, end_date):
                    continue
                
                # Ensure coordinates are valid
                pin_dict = pin_data.dict()
                pin_dict["lat"] = max(-90, min(90, pin_data.lat))
                pin_dict["lng"] = max(-180, min(180, pin_data.lng))
                validated_pins.append(Pin(**pin_dict))
            elif isinstance(pin_data, dict):
                # Validate date is in range
                pin_date = pin_data.get("date", "")
                if start_date and end_date and not self._is_date_in_range(pin_date, start_date, end_date):
                    continue
                
                # Ensure coordinates are valid
                pin_data["lat"] = max(-90, min(90, pin_data.get("lat", 0)))
                pin_data["lng"] = max(-180, min(180, pin_data.get("lng", 0)))
                
                try:
                    pin = Pin(**pin_data)
                    validated_pins.append(pin)
                except Exception as e:
                    logger.warning(f"Invalid pin data: {e}")
                    continue
        
        return validated_pins
    
    def _is_date_in_range(self, date_str: str, start_date: str, end_date: str) -> bool:
        """Check if a date string is within the given date range (inclusive)."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            return start_obj <= date_obj <= end_obj
        except (ValueError, AttributeError):
            return False
    
    def _parse_date_period(self, date_str: str) -> Dict[str, str]:
        """
        Parse a date string and return start_date and end_date.
        
        Returns:
            Dict with 'start_date' and 'end_date' keys
        """
        from calendar import monthrange
        
        today = datetime.now().date()
        
        if not date_str or date_str.lower() in ["null", "none", ""]:
            end_date = today
            start_date = today - timedelta(days=6)
            return {
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": end_date.strftime('%Y-%m-%d')
            }
        
        date_str = date_str.strip()
        
        if date_str.lower() == "today":
            date_str = today.strftime('%Y-%m-%d')
        elif date_str.lower() == "yesterday":
            date_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            if len(date_str) == 10 and date_str.count('-') == 2:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                return {
                    "start_date": date_str,
                    "end_date": date_str
                }
            
            if len(date_str) == 7 and date_str.count('-') == 1:
                year, month = map(int, date_str.split('-'))
                start_date = datetime(year, month, 1).date()
                last_day = monthrange(year, month)[1]
                end_date = datetime(year, month, last_day).date()
                return {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d')
                }
            
            if len(date_str) == 4 and date_str.isdigit():
                year = int(date_str)
                start_date = datetime(year, 1, 1).date()
                end_date = datetime(year, 12, 31).date()
                return {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d')
                }
            
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return {
                "start_date": date_str,
                "end_date": date_str
            }
        except (ValueError, AttributeError):
            end_date = today
            start_date = today - timedelta(days=6)
            return {
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": end_date.strftime('%Y-%m-%d')
            }
    
    def call_gemini(self, prompt: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """Direct call to Gemini API."""
        if config is None:
            config = {}
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(**config)
        )
        return response
    
    def call_geocoding(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Direct call to geocoding service."""
        return self.geocoding_service.geocode_location(location_name)
