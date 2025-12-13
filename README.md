# Atlantis - World News / History Map Explorer

An interactive world map explorer that displays historical events and news as pins, with streaming explanations and Q&A powered by Gemini AI.

## 📋 Features

- **Interactive Map**: Explore world events on an interactive map with pins for significant historical events
- **Date Selection**: Choose any date to see events that occurred on that day
- **Streaming Explanations**: Get real-time streaming explanations for each event
- **Contextual Q&A**: Ask questions about events and get AI-powered responses
- **Multi-language Support**: Available in multiple languages (English, Chinese, Spanish, French)
- **Zoom-aware Events**: Local events when zoomed in, global events when zoomed out

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm/yarn
- A Google Gemini API key (get it free from [Google AI Studio](https://aistudio.google.com/))
- A Mapbox access token (get it free from [Mapbox](https://account.mapbox.com/access-tokens/))

### Installation

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

3. **Set up frontend:**

   ```bash
   cd src/frontend
   npm install
   cd ../..
   ```

4. **Configure environment variables:**

   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and add your API keys:
   # - GEMINI_API_KEY: Your Google Gemini API key (required)
   # - NEWS_API_KEY: Your NewsAPI.org key (optional, get free at https://newsapi.org/)
   # - VITE_MAPBOX_TOKEN: Your Mapbox access token (required)
   #
   # Note: NEWS_API_KEY is optional. If not provided, the system will use Gemini
   # to generate historical events, but won't fetch real-time news articles.
   ```

### Running the Application

1. **Start the backend server:**

   ```bash
   # From project root
   cd src/backend
   python -m uvicorn main:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`

2. **Start the frontend development server:**

   ```bash
   # From project root
   cd src/frontend
   npm run dev
   ```

   The app will be available at `http://localhost:5173`

### Project Structure

```
src/
├── backend/                    # FastAPI backend
│   ├── main.py                # FastAPI app entry point
│   ├── models.py              # Pydantic models
│   ├── routers/
│   │   └── events.py          # Event API endpoints
│   ├── services/
│   │   ├── gemini.py          # Gemini API integration
│   │   └── cache.py           # Caching service
│   └── utils/
│       └── sse.py             # SSE streaming utilities
└── frontend/                   # React + TypeScript frontend
    ├── src/
    │   ├── App.tsx            # Main app component
    │   ├── components/        # React components
    │   ├── hooks/             # Custom React hooks
    │   └── types/             # TypeScript type definitions
    └── package.json
```

### API Endpoints

- `POST /api/events/pins` - Generate event pins for a date and viewport
- `GET /api/events/{event_id}/explain/stream` - Stream event explanation (SSE)
- `POST /api/events/{event_id}/chat/stream` - Stream Q&A response (SSE)
- `GET /health` - Health check endpoint

## 🏗️ Architecture

### Backend (FastAPI)

- **FastAPI** for REST API with automatic OpenAPI documentation
- **Gemini API** for generating event pins, explanations, and chat responses
- **In-memory caching** with TTL for performance optimization
- **Server-Sent Events (SSE)** for streaming responses

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
cd src/backend
python -m uvicorn main:app --reload
```

### Frontend Development

```bash
# Run development server
cd src/frontend
npm run dev

# Build for production
npm run build
```

## 📝 Notes

- The app uses in-memory caching for MVP. For production, consider using Redis or a database.
- Pin storage is currently in-memory. For production, use a persistent database.
- Mapbox token is required for the map to render. Get a free token from Mapbox.

## 🏅 Judging Criteria

- **Technical Excellence**: Robust implementation with error handling and performance optimization
- **Solution Architecture**: Clean, maintainable code with proper separation of concerns
- **Innovative Gemini Integration**: Creative use of Gemini API for event generation and explanations
- **Societal Impact**: Educational tool for exploring world history and current events

## 📂 Folder Layout

![Folder Layout Diagram](images/folder-githb.png)

## 📄 License

See LICENSE file for details.
