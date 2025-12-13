#!/bin/bash
# Smoke-test script to verify core functionality

set -e

echo "Running smoke tests..."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Please create it from .env.example"
    echo "   Run: cp .env.example .env"
    echo ""
fi

# Check if Python dependencies are installed
echo "✓ Checking Python dependencies..."
python3 -c "from google import genai; import dotenv" 2>/dev/null || {
    echo "❌ Missing dependencies. Please install: pip install -r requirements.txt"
    exit 1
}
echo "  Dependencies OK"
echo ""

# Check if core modules can be imported
echo "✓ Checking core modules..."
cd src
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from planner import Planner
    from executor import Executor
    from memory import Memory
    from main import Agent
    print('  All modules imported successfully')
except ImportError as e:
    print(f'  ❌ Import error: {e}')
    sys.exit(1)
"
cd ..
echo ""

# Check if .env has API key configured (if file exists)
if [ -f .env ]; then
    if grep -q "GEMINI_API_KEY=your_gemini_api_key_here" .env || ! grep -q "GEMINI_API_KEY=" .env; then
        echo "⚠️  Warning: GEMINI_API_KEY not configured in .env"
        echo "   Please add your Gemini API key to .env"
        echo ""
    else
        echo "✓ GEMINI_API_KEY found in .env"
        echo ""
    fi
fi

echo "✅ Smoke tests completed successfully!"
echo ""
echo "Next steps:"
echo "  1. Configure your GEMINI_API_KEY in .env"
echo "  2. Run the app: python src/main.py"

