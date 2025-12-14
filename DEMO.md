# Demo Video

This demo showcases the Atlantis World News/History Map Explorer - an AI-powered interactive map that displays historical events and current news using a Planner-Executor-Memory agent architecture with Google Gemini API integration.

## Video Link

**📺 Public Video Link:**

```
TO INSERT LINK AFTER I finish filming.
```

## Demo Overview

The demo walks through the complete agent workflow, showing how user interactions trigger the Planner-Executor-Memory agent to:

1. Plan sub-tasks based on user input
2. Execute tasks using tools (Gemini API, geocoding)
3. Store results in memory (cache)
4. Return responses to the user

## Timestamps

### 00:00–00:30 — Introduction & Setup

**What to show:**

- Brief introduction to Atlantis (world news/history map explorer)
- Show the interactive map interface
- Demonstrate key UI components:
  - Mapbox map with zoom/pan controls
  - Date picker for selecting date ranges
  - Language selector (English, Chinese, Spanish, French, etc.)
  - Voice command interface (Atlantis Bar)
- Explain the problem: Exploring world events and history on an interactive map
- Highlight the AI agent architecture (Planner-Executor-Memory pattern)

**Key Points:**

- User-friendly interface for exploring world events
- Multi-language support
- Voice commands for natural interaction
- Real-time event discovery powered by Gemini API

### 00:30–01:30 — User Input → Planning

**What to show:**

- Select a date range (e.g., "January 1-7, 2024" or historical dates)
- Show how the viewport (map bounds) affects event selection
- Demonstrate zoom levels:
  - Zoomed in: Shows local/regional events
  - Zoomed out: Shows globally significant events
- **Agent Planning Step** (explain what's happening behind the scenes):
  - User selects date → API receives request
  - Agent Planner breaks down into tasks:
    1. `search_events`: Use Gemini to find events (with web search)
    2. `geocode_locations`: Convert location names to coordinates
    3. `validate_pins`: Validate dates and coordinates
  - Show or mention cache check (memory retrieval)

**Key Points:**

- User input triggers agent workflow
- Planner decomposes goal into dependent tasks
- Tasks use different tools (Gemini, geocoding)
- Memory (cache) checked first for efficiency

### 01:30–02:30 — Tool Calls & Memory

**What to show:**

- **Tool Execution** (if possible, show backend logs or explain):
  - Gemini API call with web search to discover real events
  - Show events appearing on the map as pins
  - Explain how Gemini uses Google Search tool to find current/historical events
  - Geocoding service converting location names to map coordinates
  - Validation ensuring events match date range
- **Memory/Caching**:
  - First request: Cache miss, calls APIs
  - Second request (same parameters): Cache hit, instant response
  - Show or explain date range accumulation (merging pins across viewports)
- **Streaming Responses**:
  - Click on an event pin
  - Show explanation streaming in real-time (SSE)
  - Demonstrate how explanation is cached for future use

**Key Points:**

- Gemini API uses web search for real-time event discovery
- Geocoding service (Nominatim) converts locations to coordinates
- Memory (cache) stores results to avoid redundant API calls
- Streaming explanations provide real-time feedback
- Multiple tools work together (Gemini → Geocoding → Validation)

### 02:30–03:30 — Final Output & Edge Case Handling

**What to show:**

- **Final Output**:
  - Event pins displayed on map with different categories (politics, conflict, culture, science, economics)
  - Click pin to see detailed explanation
  - Show Q&A feature: Ask questions about events, get AI-powered responses
  - Demonstrate multi-language support (switch language, see events/explanations in different language)
- **Edge Cases & Advanced Features**:
  - Voice command parsing: Speak a command (e.g., "Show me events in Tokyo in December 2024")
  - Random event feature: Discover random historic events
  - Date validation: Show events are filtered to requested date range
  - Zoom-aware events: Zoom in/out to see different event granularity
  - Error handling: Show graceful handling of geocoding failures or API errors
  - WebSocket chat: Live conversation with event context (if time permits)

**Key Points:**

- Rich output: Pins, explanations, Q&A, multi-language support
- Edge cases handled gracefully (missing locations, API errors)
- Advanced features: Voice commands, random events, live chat
- Agent architecture ensures reliable, structured responses

## Key Highlights Emphasized

1. **Agent Architecture**: The Planner-Executor-Memory pattern enables structured, reliable task execution
2. **Web Search Integration**: Gemini API uses Google Search to find real, current events
3. **Intelligent Caching**: Memory system reduces API calls and improves response times
4. **Streaming Responses**: Real-time explanation streaming for better UX
5. **Robust Error Handling**: System handles API failures, invalid data, and edge cases gracefully
6. **Multi-language Support**: Full internationalization for global users
