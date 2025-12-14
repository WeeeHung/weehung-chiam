"""
Pydantic models for Atlantis API.

Defines data structures for viewport, pins, events, and API requests/responses.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box for map viewport."""
    west: float = Field(..., description="Western longitude")
    south: float = Field(..., description="Southern latitude")
    east: float = Field(..., description="Eastern longitude")
    north: float = Field(..., description="Northern latitude")


class Viewport(BaseModel):
    """Map viewport information."""
    bbox: BBox = Field(..., description="Bounding box")
    zoom: float = Field(..., ge=0, le=20, description="Zoom level (0-20)")


class Pin(BaseModel):
    """Event pin displayed on the map."""
    event_id: str = Field(..., description="Unique event identifier")
    title: str = Field(..., description="Event title")
    date: str = Field(..., description="Event date (YYYY-MM-DD)")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    location_label: str = Field(..., description="Human-readable location name")
    category: Literal["politics", "conflict", "culture", "science", "economics", "other"] = Field(
        ..., description="Event category"
    )
    significance_score: float = Field(..., ge=0, le=1, description="Significance score (0-1)")
    one_liner: str = Field(..., description="One sentence preview")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    positivity_scale: float = Field(..., ge=0, le=1, description="Positivity scale (0-1), where 1 is positive news and 0 is negative news")
    related_event_ids: Optional[List[str]] = Field(
        default=None, description="IDs of related events"
    )


class EventDetail(BaseModel):
    """Detailed event information for dialog display."""
    event_id: str
    title: str
    who: List[str] = Field(default_factory=list, description="Key people/entities involved")
    what: str = Field(..., description="What happened")
    when: str = Field(..., description="When it happened")
    where: str = Field(..., description="Where it happened")
    why_it_matters: List[str] = Field(default_factory=list, description="Why this event matters")
    timeline: List[str] = Field(default_factory=list, description="Timeline of events")
    key_terms: List[str] = Field(default_factory=list, description="Key terms/concepts")
    suggested_questions: List[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


# Request/Response models for API endpoints

class PinsRequest(BaseModel):
    """Request to generate pins."""
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    language: str = Field(default="en", description="Language code (en, zh, etc.)")
    max_pins: int = Field(default=8, ge=1, le=20, description="Maximum number of pins")
    viewport: Viewport = Field(..., description="Map viewport")


class PinsResponse(BaseModel):
    """Response containing generated pins."""
    start_date: str
    end_date: str
    pins: List[Pin]


class ChatRequest(BaseModel):
    """Request for event Q&A."""
    language: str = Field(default="en", description="Language code")
    question: str = Field(..., description="User question")
    history: List[dict] = Field(
        default_factory=list,
        description="Chat history with role and content"
    )


class ChatMessage(BaseModel):
    """Chat message in history."""
    role: Literal["user", "assistant"]
    content: str


class ParseCommandRequest(BaseModel):
    """Request to parse voice command and extract location, language, and date."""
    text: str = Field(..., description="Transcribed voice command text")


class ParseCommandResponse(BaseModel):
    """Response containing extracted location, language, and date range."""
    location: Optional[dict] = Field(
        default=None,
        description="Location with lat/lng coordinates, or None if not found"
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code (en, zh, es, fr, etc.), or None if not found"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Start date in YYYY-MM-DD format, or None if not found"
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date in YYYY-MM-DD format, or None if not found"
    )

