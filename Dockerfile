# Docker build file (alternative to Conda)
FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set working directory for execution
WORKDIR /app/src

# Default command
CMD ["python", "main.py"]

