# Multi-stage Dockerfile for Atlantis - World News/History Map Explorer

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY src/frontend/package*.json ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source
COPY src/frontend/ ./

# Build frontend (production build)
# Note: VITE_MAPBOX_TOKEN and VITE_GEMINI_API_KEY should be provided at build time via --build-arg

RUN npm run build

# Stage 2: Python backend with frontend
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY src/backend ./src/backend

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command - run the server
# In production, you may want to serve static files using nginx or update main.py
# For now, we serve the API and static files need to be handled separately or via main.py update
CMD ["python", "-m", "uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
