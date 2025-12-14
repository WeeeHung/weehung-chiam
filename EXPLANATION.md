# Technical Explanation

## 1. Agent Workflow

The Atlantis agent follows a Planner-Executor-Memory pattern to process user requests. Here's how it works step-by-step:

### Overview Process

1. **Receive user input** - API receives request (date range, viewport, language, etc.)
2. **Retrieve relevant memory** - Check cache for previously computed results
3. **Plan sub-tasks** - Break down the goal into dependent tasks
4. **Execute tasks** - Call tools/APIs in dependency order
5. **Store results in memory** - Cache results for future use
6. **Return final output** - Send response to user

### Detailed Workflows

#### A. Pins Generation Workflow

**Endpoint:** `POST /api/events/pins`

**Step-by-step:**

1. **Memory Check**

   - Generate cache key from: date range, viewport (rounded bbox), zoom level, language, max_pins
   - Check if cached pins exist in memory
   - If cache hit: return cached pins immediately

2. **Planning Phase**

   - `Planner.plan_pins_generation()` creates three tasks:
     - **Task 1: `search_events`** (tool: "gemini")
       - Operation: `generate_pins`
       - Uses Gemini API with web search to find real events
       - Parameters: start_date, end_date, viewport, language, max_pins
     - **Task 2: `geocode_locations`** (tool: "geocoding")
       - Depends on: `search_events`
       - Geocodes location labels to lat/lng coordinates
     - **Task 3: `validate_pins`** (tool: "validate")
       - Depends on: `geocode_locations`
       - Validates dates are in range
       - Validates coordinates are within valid ranges (-90 to 90 lat, -180 to 180 lng)

3. **Execution Phase**

   - Execute tasks in dependency order:
     - First: `search_events` → Gemini API call
       - Gemini uses Google Search tool to find real events
       - Parses JSON response (handles partial/invalid JSON)
       - Returns list of Pin objects (may have 0,0 coordinates)
     - Second: `geocode_locations` → Nominatim API calls
       - For each pin with 0,0 coordinates or location_label, geocode it
       - Updates pin coordinates and potentially location_label
     - Third: `validate_pins` → Validation logic
       - Filters pins with dates outside requested range
       - Clamps coordinates to valid ranges
       - Validates Pin objects using Pydantic models

4. **Memory Storage**

   - Merge new pins with existing date range cache (deduplicate by event_id)
   - Cache viewport-specific result with 1-hour TTL
   - Store individual pins in pin store for later retrieval

5. **Response**
   - Return PinsResponse with validated pins

#### B. Explanation Streaming Workflow

**Endpoint:** `GET /api/events/{event_id}/explain/stream`

**Step-by-step:**

1. **Memory Check**

   - Generate cache key from: event_id, language
   - Check if cached explanation exists
   - If cache hit: stream cached explanation as SSE

2. **Pin Retrieval**

   - Retrieve pin from pin store or search through cache

3. **Planning Phase**

   - `Planner.plan_explanation()` creates single task:
     - **Task: `generate_explanation`** (tool: "gemini")
       - Operation: `stream_explanation`
       - Parameters: pin, language

4. **Execution Phase**

   - Execute task: Gemini API generates explanation
   - Stream chunks back as Server-Sent Events (SSE)
   - Collect full explanation text for caching

5. **Memory Storage**

   - Store explanation in cache with 12-hour TTL

6. **Response**
   - Stream explanation chunks to frontend as SSE

#### C. Chat Response Workflow

**Endpoint:** `POST /api/events/{event_id}/chat/stream`

**Step-by-step:**

1. **Pin Retrieval**

   - Retrieve pin from pin store or cache

2. **Planning Phase**

   - `Planner.plan_chat_response()` creates single task:
     - **Task: `generate_response`** (tool: "gemini")
       - Operation: `stream_chat`
       - Parameters: event_id, pin, question, history, language

3. **Execution Phase**

   - Execute task: Gemini API generates response with conversation context
   - Stream chunks back as SSE

4. **Response**
   - Stream response chunks to frontend as SSE
   - Note: Chat responses are not cached (conversational, contextual)

#### D. Command Parsing Workflow

**Endpoint:** `POST /api/events/parse-command`

**Step-by-step:**

1. **Planning Phase**

   - `Planner.plan_command_parsing()` creates two tasks:
     - **Task 1: `extract_entities`** (tool: "gemini")
       - Operation: `parse_command`
       - Uses Gemini to extract: location_name, language, start_date, end_date
     - **Task 2: `geocode_location`** (tool: "geocoding")
       - Depends on: `extract_entities`
       - Geocodes extracted location_name

2. **Execution Phase**

   - Execute `extract_entities`: Gemini parses voice command text
     - Handles date formats: year (YYYY), month (YYYY-MM), single date, date range
     - Extracts language code from command
     - Returns structured JSON
   - Execute `geocode_location`: Geocode location if provided

3. **Response**
   - Return ParseCommandResponse with location, language, date range

#### E. Random Event Workflow

**Endpoint:** `GET /api/events/random-event`

**Step-by-step:**

1. **Planning Phase**

   - `Planner.plan_random_event()` creates two tasks:
     - **Task 1: `generate_random_event`** (tool: "gemini")
       - Operation: `random_event`
       - Uses Gemini with web search to find a random historic event
     - **Task 2: `geocode_location`** (tool: "geocoding")
       - Depends on: `generate_random_event`
       - Geocodes event location

2. **Execution Phase**

   - Execute `generate_random_event`: Gemini searches for historic events
     - Validates dates are in the past
     - Returns event name, location, dates
   - Execute `geocode_location`: Geocode event location

3. **Response**
   - Return ParseCommandResponse with random event details

## 2. Key Modules

### Planner (`src/backend/services/agent/planner.py`)

**Purpose:** Decompose high-level goals into executable tasks with dependencies.

**Key Features:**

- Task decomposition for different operations
- Dependency management (tasks depend on previous task results)
- Tool assignment (each task specifies which tool to use)

**Task Types:**

- `plan_pins_generation()`: 3-task pipeline (search → geocode → validate)
- `plan_explanation()`: Single task (generate explanation)
- `plan_chat_response()`: Single task (generate chat response)
- `plan_command_parsing()`: 2-task pipeline (extract → geocode)
- `plan_random_event()`: 2-task pipeline (generate → geocode)

**Task Structure:**

```python
@dataclass
class Task:
    name: str                    # Unique task identifier
    tool: str                    # Tool to use: "gemini", "geocoding", "validate", "format"
    params: Dict[str, Any]       # Parameters for the tool
    dependencies: List[str]      # Task names that must complete first
```

### Executor (`src/backend/services/agent/executor.py`)

**Purpose:** Execute tasks by routing to appropriate tools and managing dependencies.

**Key Features:**

- Dependency resolution: Ensures tasks execute in correct order
- Parameter resolution: Fills parameters from previous task results
- Tool routing: Routes tasks to correct service (Gemini, Geocoding, etc.)
- Error handling: Catches and logs errors

**Tool Handlers:**

- `_execute_gemini_task()`: Routes to GeminiService based on operation
  - `generate_pins`: Event discovery with web search
  - `stream_explanation`: Generate explanations
  - `stream_chat`: Q&A responses
  - `parse_command`: Entity extraction
  - `random_event`: Random event discovery
- `_execute_geocoding_task()`: Calls GeocodingService
- `_execute_validate_task()`: Validates pin data (dates, coordinates)
- `_execute_format_task()`: Data formatting operations

**Context Passing:**

- Executor maintains a `context` dict that stores results of each task
- Tasks can access results from dependencies via context
- Parameters are resolved from context when value is `None`

### Memory (`src/backend/services/agent/memory.py`)

**Purpose:** Unified memory management for cache, pins, and conversations.

**Components:**

1. **Cache Service Integration**

   - Wraps `CacheService` for TTL-based caching
   - Methods: `store_cache()`, `retrieve_cache()`
   - Cache keys: Generated from request parameters

2. **Pin Store**

   - In-memory dictionary: `{event_id: Pin}`
   - Methods: `store_pin()`, `retrieve_pin()`, `find_pin_in_cache()`
   - Used to retrieve pins for explanations/chat

3. **Conversation History**
   - In-memory dictionary: `{session_id: List[messages]}`
   - Methods: `store_conversation()`, `retrieve_conversation()`, `append_to_conversation()`
   - Used for WebSocket chat sessions

**Cache Strategies:**

- Pins: 1-hour TTL, keyed by date range + viewport + language
- Explanations: 12-hour TTL, keyed by event_id + language
- Date range accumulation: Merges pins across viewports

### GeminiService (`src/backend/services/gemini.py`)

**Purpose:** Integration with Google Gemini API for LLM operations.

**Model:** `gemini-2.0-flash`

**Key Operations:**

1. **`generate_pins()`**

   - Uses Gemini with Google Search tool to find real events
   - Prompts Gemini to search for events matching date range and viewport
   - Parses JSON response (handles partial/invalid JSON with recovery)
   - Validates dates are in requested range
   - Geocodes locations if coordinates are missing
   - Returns list of Pin objects

2. **`stream_explanation()`**

   - Generates TLDR news article about an event
   - Formats with markdown (bold for important sentences)
   - Streams response in chunks (simulated streaming)
   - Language-aware generation

3. **`stream_chat()`**
   - Answers questions about events
   - Uses conversation history for context
   - Streams response in chunks
   - Language-aware responses

**Web Search Integration:**

- Uses Gemini's `GoogleSearch` tool via `types.Tool(google_search=types.GoogleSearch())`
- System prompts instruct model to use web search for real-time information
- Model searches web, extracts information, and formats as structured JSON

**JSON Parsing Robustness:**

- Handles markdown code blocks (```json)
- Fixes unterminated strings
- Removes incomplete objects from arrays
- Extracts partial pins from invalid JSON using regex
- Retries with Gemini if parsing fails

### CacheService (`src/backend/services/cache.py`)

**Purpose:** TTL-based in-memory caching with expiration management.

**Cache Structure:**

- Dictionary: `{cache_key: (value, expiry_datetime)}`
- Automatic expiration check on retrieval
- Cleanup method for expired entries

**TTL Settings:**

- Pins: 1 hour (`timedelta(minutes=60)`)
- Explanations: 12 hours (`timedelta(hours=12)`)

**Cache Key Generation:**

- MD5 hash of JSON-serialized parameters
- Pins: Date range, rounded bbox, zoom bucket, language, max_pins
- Explanations: event_id, language
- Date range pins: start_date, end_date, language

**Date Range Accumulation:**

- `merge_and_set_date_range_pins()` merges pins across viewports
- Deduplicates by event_id
- Allows accumulation of pins for same date range but different viewports

### GeocodingService (`src/backend/services/news.py`)

**Purpose:** Geocode location names to lat/lng coordinates.

**Service:** Nominatim (OpenStreetMap) - free, no API key

**Features:**

- Returns actual geographic coordinates (not viewport-biased)
- Prefers specific locations (places, buildings, amenities) over generic (cities, countries)
- Returns enhanced display names with address components
- Handles rate limiting (1 request/second for free tier)

**Geocoding Logic:**

1. Query Nominatim with location name
2. Sort results by specificity (place type priority + importance score)
3. Select most specific result
4. Extract coordinates and build enhanced display name from address components

## 3. Tool Integration

### Google Gemini API

**SDK:** `google-genai` (v0.2.0+)

**Usage:**

```python
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[...],
    config=types.GenerateContentConfig(
        temperature=0.2,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        response_modalities=["TEXT"],
        max_output_tokens=4000
    )
)
```

**Features Used:**

- Text generation with temperature control
- Google Search tool for real-time web search
- Streaming responses (for explanations/chat)
- Structured JSON output (for event pins)

**Configuration:**

- Temperature: 0.2 (pins), 0.6-0.7 (explanations/chat), 1.0 (random events)
- Max tokens: Dynamic based on operation (~600 per pin, 800-1000 for text)
- Response format: TEXT modality

### Nominatim Geocoding API

**API:** REST API (no authentication)

**Usage:**

```python
response = requests.get(
    "https://nominatim.openstreetmap.org/search",
    params={"q": location_name, "format": "json", "limit": 1},
    headers={"User-Agent": "Atlantis-WorldNews/1.0"}
)
```

**Rate Limits:**

- Free tier: 1 request/second
- System minimizes requests through caching

**Response Format:**

- Returns JSON array of results
- Each result contains: `lat`, `lon`, `display_name`, `address`, `importance`, `type`

## 4. Observability & Testing

### Logging

**Framework:** Python `logging` module

**Configuration:**

- Level: INFO (configurable via environment)
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Location: Configured in `src/backend/main.py`

**Logging Points:**

- API request/response (FastAPI automatic)
- Gemini API calls and responses (INFO level)
- JSON parsing errors with context (ERROR/WARNING)
- Geocoding failures (WARNING)
- Cache hits/misses (implicit via timing)
- Task execution errors (ERROR)
- WebSocket connection/disconnection (INFO)

**Example Log Messages:**

```
INFO:src.backend.routers.events:Generating pins for 2024-01-01 to 2024-01-07
INFO:src.backend.services.gemini:Raw Gemini response length: 15234 chars
WARNING:src.backend.services.news:Geocoding failed for location: UnknownPlace
ERROR:src.backend.services.gemini:JSON parse error at line 45, col 12: Expecting ',' delimiter
```

### Testing

**Smoke Tests (`TEST.sh`):**

- Verifies all Python modules can be imported
- Checks for syntax errors
- Validates dependency installation
- Can run in CI/CD pipelines (doesn't fail on missing API keys)

**Test Coverage:**

- Module imports (agent, routers, services)
- FastAPI app initialization
- Basic functionality verification

**Manual Testing:**

- API endpoints via curl/Postman
- Frontend integration via browser
- SSE streaming verification
- WebSocket chat testing

## 5. Known Limitations

### Current Limitations

1. **In-Memory Storage**

   - Cache is in-memory (lost on server restart)
   - Pin storage is in-memory (not database-backed)
   - Conversation history is in-memory (lost on restart)
   - **Impact:** No persistence across deployments
   - **Workaround:** None currently (designed for MVP)

2. **Geocoding Rate Limits**

   - Nominatim free tier: 1 request/second
   - **Impact:** May slow down pin generation with many locations
   - **Workaround:** Caching geocoded results, but still limited

3. **Gemini API Rate Limits**

   - Subject to Google API quotas
   - **Impact:** May hit rate limits with high traffic
   - **Workaround:** Caching reduces API calls

4. **Web Search Accuracy**

   - Gemini web search results may vary
   - **Impact:** Some events may not be found or may be inaccurate
   - **Workaround:** Validation ensures dates are in range, but can't verify event accuracy

5. **JSON Parsing Edge Cases**

   - Complex JSON responses from Gemini may fail to parse
   - **Impact:** Some pin generations may return empty results
   - **Workaround:** Robust parsing with partial extraction and retry logic

6. **Date Validation**

   - Strict date range validation ensures events are within requested range
   - **Impact:** Some events near boundaries may be filtered out
   - **Workaround:** Validation is necessary for accuracy

7. **Single Server Deployment**

   - Not designed for horizontal scaling
   - **Impact:** Cache and state not shared across instances
   - **Workaround:** Use single instance or implement Redis/database

8. **Error Handling**
   - Some errors may not be gracefully handled
   - **Impact:** API may return 500 errors for unexpected failures
   - **Workaround:** Error logging helps debug, but user experience may suffer

### Performance Considerations

- **Cache Hit Rate:** Depends on user query patterns (viewport movement, date selection)
- **API Latency:** Gemini API calls are the slowest operation (~2-5 seconds)
- **Geocoding Latency:** Nominatim calls add ~0.5-1 second per unique location
- **Memory Usage:** In-memory cache grows with usage (no size limits currently)

### Future Improvements

- **Database Integration:** Store pins and cache in database (PostgreSQL, MongoDB)
- **Redis Cache:** Shared cache across instances
- **Rate Limiting:** Implement request rate limiting
- **Monitoring:** Add metrics collection (Prometheus, Datadog)
- **Error Tracking:** Integrate error tracking (Sentry)
- **Batch Geocoding:** Batch geocoding requests to improve performance
- **Background Jobs:** Move heavy operations to background workers
