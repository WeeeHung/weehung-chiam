"""
Server-Sent Events (SSE) utilities for streaming responses.
"""

from typing import Iterator
import json


def format_sse_event(event_type: str, data: str) -> str:
    """
    Format data as SSE event.
    
    Args:
        event_type: Event type (e.g., 'chunk', 'done')
        data: Event data
        
    Returns:
        Formatted SSE string
    """
    # Escape newlines in data
    data = data.replace("\n", "\\n")
    return f"event: {event_type}\ndata: {data}\n\n"


def stream_text_chunks(text_stream: Iterator[str]) -> Iterator[str]:
    """
    Convert text stream to SSE format.
    
    Args:
        text_stream: Iterator yielding text chunks
        
    Yields:
        SSE-formatted strings
    """
    for chunk in text_stream:
        yield format_sse_event("chunk", chunk)
    
    # Send done event
    done_data = json.dumps({"ok": True})
    yield format_sse_event("done", done_data)

