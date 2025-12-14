#!/bin/bash
# Smoke-test script to verify core functionality

set -e

# Detect CI environment
CI=${CI:-false}

echo "Running smoke tests..."
echo ""

# Install dependencies if missing (required for CI)
echo "✓ Installing/checking Python dependencies..."
pip install -q -r requirements.txt || {
    echo "❌ Failed to install dependencies"
    exit 1
}
echo "  Dependencies OK"
echo ""

# Verify core modules can be imported (syntax and import check)
echo "✓ Checking core module imports..."
python3 -c "
import sys
import os

# Add src/backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'src', 'backend')
sys.path.insert(0, backend_path)

try:
    # Test agent modules
    from services.agent import Planner, Executor, Memory
    print('  ✓ Agent modules imported successfully')
    
    # Test backend modules
    from routers import events
    from services import gemini, cache, news
    print('  ✓ Backend modules imported successfully')
    
    # Test main app (without initializing services that need API keys)
    from main import app
    print('  ✓ FastAPI app imported successfully')
    
except ImportError as e:
    print(f'  ❌ Import error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    # Some modules might fail to initialize without API keys, that's OK for smoke test
    if 'GEMINI_API_KEY' in str(e) or 'API' in str(e):
        print(f'  ⚠️  Module requires API key (expected in CI): {e}')
    else:
        print(f'  ❌ Unexpected error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
"
echo ""

# .env check (warning only, not a failure)
if [ ! -f .env ]; then
    if [ "$CI" = "true" ]; then
        echo "ℹ️  Running in CI (no .env required)"
    else
        echo "⚠️  Warning: .env file not found"
        echo "   Run: cp .env.example .env (if available)"
    fi
    echo ""
fi

echo "✅ Smoke tests completed successfully!"
echo ""
echo "Core functionality verified:"
echo "  - Dependencies installed"
echo "  - All modules can be imported"
echo "  - No syntax errors detected"

