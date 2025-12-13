"""
Run script for Atlantis backend.

Usage:
    python -m src.backend.run
    or
    cd src/backend && python run.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

