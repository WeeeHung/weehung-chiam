"""
Planner module for breaking down user goals into sub-tasks.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from ...models import Pin, Viewport


@dataclass
class Task:
    """Represents a single task in the agent workflow."""
    name: str
    tool: str  # "gemini", "geocoding", "web_search", "format", "validate"
    params: Dict[str, Any]
    dependencies: List[str] = None  # Other task names that must complete first
    
    def __post_init__(self):
        """Initialize dependencies if not provided."""
        if self.dependencies is None:
            self.dependencies = []


class Planner:
    """Plans sub-tasks for various agent operations."""
    
    def plan_pins_generation(
        self,
        start_date: str,
        end_date: str,
        viewport: Viewport,
        language: str,
        max_pins: int
    ) -> List[Task]:
        """
        Plan tasks for generating event pins.
        
        Returns:
            List of tasks to execute in order
        """
        return [
            Task(
                name="search_events",
                tool="gemini",
                params={
                    "operation": "generate_pins",
                    "start_date": start_date,
                    "end_date": end_date,
                    "viewport": viewport,
                    "language": language,
                    "max_pins": max_pins
                }
            ),
            Task(
                name="geocode_locations",
                tool="geocoding",
                params={},  # Pins will be resolved from search_events dependency
                dependencies=["search_events"]
            ),
            Task(
                name="validate_pins",
                tool="validate",
                params={
                    "start_date": start_date,
                    "end_date": end_date
                },
                dependencies=["geocode_locations"]
            )
        ]
    
    def plan_explanation(self, pin: Pin, language: str) -> List[Task]:
        """
        Plan tasks for generating event explanation.
        
        Returns:
            List of tasks to execute
        """
        return [
            Task(
                name="generate_explanation",
                tool="gemini",
                params={
                    "operation": "stream_explanation",
                    "pin": pin,
                    "language": language
                }
            )
        ]
    
    def plan_chat_response(
        self,
        event_id: str,
        pin: Pin,
        question: str,
        history: List[Dict[str, str]],
        language: str
    ) -> List[Task]:
        """
        Plan tasks for generating chat response.
        
        Returns:
            List of tasks to execute
        """
        return [
            Task(
                name="generate_response",
                tool="gemini",
                params={
                    "operation": "stream_chat",
                    "event_id": event_id,
                    "pin": pin,
                    "question": question,
                    "history": history,
                    "language": language
                }
            )
        ]
    
    def plan_command_parsing(self, text: str) -> List[Task]:
        """
        Plan tasks for parsing voice command.
        
        Returns:
            List of tasks to execute
        """
        return [
            Task(
                name="extract_entities",
                tool="gemini",
                params={
                    "operation": "parse_command",
                    "text": text
                }
            ),
            Task(
                name="geocode_location",
                tool="geocoding",
                params={
                    "location_name": None  # Will be filled from extract_entities result
                },
                dependencies=["extract_entities"]
            )
        ]
    
    def plan_random_event(self) -> List[Task]:
        """
        Plan tasks for generating random event.
        
        Returns:
            List of tasks to execute
        """
        return [
            Task(
                name="generate_random_event",
                tool="gemini",
                params={
                    "operation": "random_event"
                }
            ),
            Task(
                name="geocode_location",
                tool="geocoding",
                params={
                    "location_name": None  # Will be filled from generate_random_event result
                },
                dependencies=["generate_random_event"]
            )
        ]
