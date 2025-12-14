# Demo Video

This demo showcases Atlantis - an AI-powered spatial explorer that organizes the world's history and news by geography, transforming abstract headlines into personal journeys through an interactive map. The system uses a Planner-Executor-Memory agent architecture with Google Gemini API integration, including Gemini Live API for conversational interactions.

## Video Link

**📺 Public Video Link:**

```
https://www.loom.com/share/57888dd26d304879bba5b996716b9aa9
```

## Demo Overview

The demo demonstrates how Atlantis addresses information isolation by anchoring news and historical events to physical spaces. The walkthrough shows:

1. Interactive news reporting with AI-powered conversations
2. Spatial exploration of events through map navigation
3. Real-time article generation with web search integration
4. Intelligent caching and memory management
5. Multilingual support for global accessibility
6. Random event discovery through dice feature

## Timestamps

### 00:00–00:13 — Problem Introduction

**Key Points:**

- **Problem solved**: Addresses information isolation caused by algorithmic echo chambers that trap users in filtered content bubbles
- Loss of spatial and temporal context ("where and when") in traditional news consumption
- Sets the foundation for geographic, agent-driven approach to news and history exploration

### 00:13–00:46 — Atlantis Introduction & Spatial Concept

**Key Points:**

- **Problem solved**: Transforms abstract headlines into personal journeys by anchoring data to physical space
- Core solution: Geographic organization of news and history instead of traditional field-based categorization
- Voice-powered interaction enables natural exploration through agent-driven conversations
- Personal connection established through home location anchoring, making global events locally relevant

### 00:46–01:28 — Interactive News Reporting & AI Conversation

**Key Points:**

- **End-to-end agent behavior**: User explores news near home → Agent plans search tasks → Executes web search tool calls → Generates article → Provides conversational interface
- **Agentic steps demonstrated**:
  - **Planning**: Agent breaks down "explore news near me" into location-based search tasks
  - **Tool calls**: Gemini API with web search retrieves real-time event information (e.g., Singapore Christmas Market)
  - **Memory use**: Conversation context maintained for follow-up questions (e.g., "What's the price?")
- **Problem solved**: Provides personalized, conversational news delivery instead of passive reading
- Real-time article generation with web search ensures current, accurate information

### 01:28–02:13 — Web Search, Caching & Map Navigation

**Key Points:**

- **End-to-end agent behavior**: Voice command "What happened in San Francisco in March 2020?" → Agent plans location/date search → Executes web search tool → Geocodes location → Validates events → Caches results → Displays on map
- **Agentic steps highlighted**:
  - **Planning**: Agent decomposes voice query into search_events, geocode_locations, and validate_pins tasks
  - **Tool calls**: Gemini API with web search, geocoding service (Nominatim), and validation tools work in sequence
  - **Memory use**: "This conversation will also be caching memory" - agent stores results to avoid redundant API calls on repeat queries
- **Problem solved**: Enables exploration beyond home country through intuitive map navigation and voice commands
- Agent architecture intelligently handles memory and context across conversations

### 02:13–02:59 — Pin Color System & Event Analysis

**Key Points:**

- **Agentic steps**: Agent performs sentiment analysis during event processing, categorizing events as positive (green) or negative (red) through tool calls
- **Problem solved**: Provides instant visual understanding of event sentiment, helping users quickly grasp the nature of news without reading details
- Color-coded visualization enables pattern recognition (e.g., COVID-19 impact visible through red pin concentration)
- Agent's analysis and categorization tools enhance information comprehension

### 02:59–03:28 — Random Event Discovery (Dice Feature)

**Key Points:**

- **End-to-end agent behavior**: Dice click → Agent plans random event selection → Executes search across historical database → Retrieves event → Geocodes location → Displays on map
- **Problem solved**: Breaks echo chamber effect by exposing users to events outside their familiar time periods and cultural contexts
- Agent's planning capabilities enable intelligent random selection that maintains educational value
- Promotes serendipitous learning and global historical awareness

### 03:28–04:16 — Multilingual Support

**Key Points:**

- **End-to-end agent behavior**: Chinese query "What happened recently in Hong Kong?" → Agent plans multilingual search → Executes web search → Generates Chinese article → Reports in Chinese → Maintains conversation context in Chinese
- **Agentic steps**: Agent adapts tool calls and responses based on language preference, demonstrating context-aware planning and execution
- **Problem solved**: Removes language barriers, enabling global users to explore news and history in their native language
- Agent's memory system maintains language context throughout the conversation
- Localized content generation ensures culturally appropriate information delivery

### 04:16–04:43 — Conclusion & Vision

**Key Points:**

- **Agent architecture summary**: Robust Planner-Executor-Memory pattern combines real-time knowledge (web search) with intelligent planning and memory management to "engineer truth"
- **Problem solved**: Transforms passive information consumption into active, interactive understanding through agent-driven exploration
- Core philosophy: Agent architecture turns raw information into contextual understanding by combining planning, tool execution, and memory
- Vision: Interactive, intelligent news consumption powered by agentic AI that maintains context, learns from interactions, and provides personalized experiences

## Key Highlights Emphasized

1. **Spatial Organization**: Geographic anchoring transforms abstract headlines into personal journeys
2. **AI Reporter**: Conversational interface with Gemini Live API for natural news interaction
3. **Real-time Web Search**: Dynamic article generation with current, accurate information
4. **Intelligent Caching**: Memory system stores conversations and results for efficiency
5. **Visual Sentiment Analysis**: Color-coded pins (green/red) provide instant event understanding
6. **Random Discovery**: Dice feature encourages serendipitous learning beyond familiar timeframes
7. **Multilingual Support**: Native language support for global accessibility
8. **Agent Architecture**: Robust Planner-Executor-Memory pattern handles complex workflows
9. **Voice Commands**: Hands-free exploration through natural language interaction
10. **Truth Engineering**: Combining AI architecture with real-time knowledge to turn information into understanding
