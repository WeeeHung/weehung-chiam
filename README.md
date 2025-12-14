# Atlantis - World News / History Map Explorer

An interactive world map explorer that displays historical events and news as pins, with streaming explanations and Q&A powered by Gemini AI. Built with a Planner-Executor-Memory agent architecture for structured, reliable task execution.

## 📋 Features

- **Interactive Map**: Explore world events on an interactive map with pins for significant historical events
- **Date Selection**: Choose any date range to see events that occurred during that period
- **Streaming Explanations**: Get real-time streaming explanations for each event
- **Contextual Q&A**: Ask questions about events and get AI-powered responses
- **Multi-language Support**: Available in multiple languages (English, Chinese, Spanish, French, and more)
- **Zoom-aware Events**: Local events when zoomed in, global events when zoomed out
- **Voice Commands**: Natural language commands for date and location selection
- **Random Events**: Discover random interesting historic events

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm/yarn
- A Google Gemini API key (get it free from [Google AI Studio](https://aistudio.google.com/))
- A Mapbox access token (get it free from [Mapbox](https://account.mapbox.com/access-tokens/))

### Installation

#### Option 1: Standard Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd weehung-chiam
   ```

2. **Set up backend:**

   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   ```

   Alternatively, use Conda:

   ```bash
   conda env create -f environment.yml
   conda activate agent-env
   ```

3. **Set up frontend:**

   ```bash
   cd src/frontend
   npm install
   cd ../..
   ```

4. **Configure environment variables:**

   Create a `.env` file in the project root:

   ```bash
   # Backend
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

   Create a `.env` file in `src/frontend/`:

   ```bash
   # Frontend
   VITE_MAPBOX_TOKEN=your_mapbox_token_here
   VITE_GEMINI_API_KEY=your_token_here
   ```

   **Note:** The system uses Gemini's built-in web search capabilities to fetch real-time news and historical events. No additional news API is required.

#### Option 2: Docker Installation

**Using docker-compose (Recommended):**

1. **Create `.env` file in project root:**

   ```bash
   # Backend runtime secret
   GEMINI_API_KEY=your_gemini_api_key_here

   # Frontend build-time secrets (required for frontend build)
   VITE_MAPBOX_TOKEN=your_mapbox_token_here
   VITE_GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. **Build and run:**

   ```bash
   docker-compose up --build
   ```

   The application will be available at `http://localhost:8000`

**Using Docker directly:**

1. **Create `.env` file in project root:**

   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   VITE_MAPBOX_TOKEN=your_mapbox_token_here
   VITE_GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. **Build the Docker image:**

   ```bash
   # Load environment variables and build with frontend secrets
   source .env
   docker build \
     --build-arg VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN \
     --build-arg VITE_GEMINI_API_KEY=$VITE_GEMINI_API_KEY \
     -t atlantis .
   ```

   **Important:** Make sure Docker Desktop is running before building. The `.` at the end specifies the build context (current directory).

3. **Run the container:**

   ```bash
   docker run -p 8000:8000 --env-file .env -e GEMINI_API_KEY=$GEMINI_API_KEY atlantis
   ```

   Or with inline secrets:

   ```bash
   docker build \
     --build-arg VITE_MAPBOX_TOKEN=your_mapbox_token_here \
     --build-arg VITE_GEMINI_API_KEY=your_gemini_api_key_here \
     -t atlantis .

   docker run -p 8000:8000 -e GEMINI_API_KEY=your_gemini_api_key_here atlantis
   ```

   **Troubleshooting:**

   - If you see "Cannot connect to the Docker daemon", make sure Docker Desktop is running
   - The `.` at the end of the build command is required (it specifies the build context)
   - Make sure you're running the command from the project root directory

   **Note:**

   - `VITE_MAPBOX_TOKEN` and `VITE_GEMINI_API_KEY` are required at **build time** (for frontend build)
   - `GEMINI_API_KEY` is required at **runtime** (for backend API)
   - Never commit `.env` files to git (add to `.gitignore`)
   - For production, you may want to serve the built frontend static files. Consider updating `src/backend/main.py` to serve static files or use nginx as a reverse proxy.

### Running the Application

#### Development Mode

1. **Start the backend server:**

   ```bash
   # From project root
   uvicorn src.backend.main:app --reload
   ```

   The API will be available at `http://localhost:8000`

   - API docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

2. **Start the frontend development server:**

   ```bash
   # From project root
   cd src/frontend
   npm run dev
   ```

   The app will be available at `http://localhost:5173`

   - Frontend automatically proxies `/api/*` requests to the backend

### Project Structure

```
src/
├── backend/                    # FastAPI backend
│   ├── main.py                # FastAPI app entry point
│   ├── models.py              # Pydantic models
│   ├── routers/
│   │   └── events.py          # Event API endpoints
│   ├── services/
│   │   ├── agent/             # Agent architecture
│   │   │   ├── planner.py     # Task decomposition
│   │   │   ├── executor.py    # Task execution
│   │   │   └── memory.py      # Cache & state management
│   │   ├── gemini.py          # Gemini API integration
│   │   ├── cache.py           # Caching service
│   │   └── news.py            # Geocoding service (Nominatim)
│   └── utils/
│       └── sse.py             # SSE streaming utilities
└── frontend/                   # React + TypeScript frontend
    ├── src/
    │   ├── App.tsx            # Main app component
    │   ├── components/        # React components
    │   │   ├── WorldMap.tsx   # Mapbox map component
    │   │   ├── EventDialog.tsx # Event detail modal
    │   │   ├── AtlantisBar.tsx # Voice command interface
    │   │   └── ...
    │   ├── hooks/             # Custom React hooks
    │   │   ├── useSSE.ts      # SSE streaming
    │   │   ├── useEvents.ts   # Event data fetching
    │   │   └── ...
    │   └── types/             # TypeScript type definitions
    └── package.json
```

### API Endpoints

- `POST /api/events/pins` - Generate event pins for a date range and viewport
- `GET /api/events/{event_id}/explain/stream` - Stream event explanation (SSE)
- `POST /api/events/{event_id}/chat/stream` - Stream Q&A response (SSE)
- `POST /api/events/parse-command` - Parse voice command (extract location, dates, language)
- `GET /api/events/random-event` - Get a random interesting historic event
- `GET /api/events/{event_id}/live/ws` - WebSocket endpoint for live conversation
- `POST /api/events/ephemeral-token` - Create ephemeral token for Gemini Live API
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint (service info)

## 🏗️ Architecture

Atlantis uses a **Planner-Executor-Memory agent architecture** for structured task execution:

- **Planner**: Breaks down user goals into sub-tasks with dependencies
- **Executor**: Routes tasks to appropriate tools (Gemini API, geocoding, validation)
- **Memory**: Manages cache, pin storage, and conversation history

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation with diagrams.

### Backend (FastAPI)

- **FastAPI** for REST API with automatic OpenAPI documentation
- **Agent Architecture**: Planner-Executor-Memory pattern for task execution
- **Gemini API** with web search for generating event pins, explanations, and chat responses
- **In-memory caching** with TTL for performance optimization (1h for pins, 12h for explanations)
- **Server-Sent Events (SSE)** for streaming responses
- **Geocoding**: Nominatim (OpenStreetMap) for location → coordinates

### Frontend (React + TypeScript)

- **React 18** with TypeScript for type safety
- **Vite** for fast development and building
- **Mapbox GL JS** for interactive map rendering
- **React Query** for data fetching and caching
- **Custom hooks** for SSE streaming

## 🧪 Development

### Backend Development

```bash
# Run with auto-reload
uvicorn src.backend.main:app --reload

# Run from backend directory
cd src/backend
python main.py
```

### Frontend Development

```bash
# Run development server
cd src/frontend
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Testing

Run smoke tests to verify installation:

```bash
bash TEST.sh
```

This verifies:

- Python dependencies are installed
- All modules can be imported
- No syntax errors

## 📝 Configuration

### Environment Variables

**Backend (.env in project root):**

- `GEMINI_API_KEY` (required): Google Gemini API key for backend API calls

**Frontend (src/frontend/.env):**

- `VITE_MAPBOX_TOKEN` (required): Mapbox access token for map rendering
- `VITE_GEMINI_API_KEY` (required): Google Gemini API key for frontend Live API features

**Note:** Both backend and frontend need Gemini API keys, but they serve different purposes:

- Backend `GEMINI_API_KEY`: Used for generating pins, explanations, and chat responses
- Frontend `VITE_GEMINI_API_KEY`: Used for client-side Gemini Live API interactions

### Caching

The system uses in-memory caching with the following TTLs:

- Pins: 1 hour
- Explanations: 12 hours
- Date range accumulation: Merges pins across viewports

For production, consider using Redis for shared cache across instances.

## 📖 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system architecture and component descriptions
- [EXPLANATION.md](EXPLANATION.md) - Agent workflow, modules, tool integration, and limitations
- [DEMO.md](DEMO.md) - Demo video structure and timestamps

## 🔧 Known Limitations

- In-memory cache (not persistent across restarts)
- Pin storage is in-memory (not database-backed)
- Geocoding rate limits (Nominatim free tier: 1 request/second)
- Gemini API rate limits (subject to Google API quotas)
- Web search results may vary in accuracy
- Single server deployment (not designed for horizontal scaling)

See [EXPLANATION.md](EXPLANATION.md) for detailed limitations and future improvements.

## 📄 License

See LICENSE file for details.
