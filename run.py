"""Entry point for running the Organization Matching Registry web application.

Usage:
    python run.py
"""

from __future__ import annotations

import sys
import uvicorn

if __name__ == "__main__":
    print("[INFO] Starting Organization Matching Registry server...")
    print("[INFO] Web UI available at: http://localhost:8000")
    print("[INFO] Swagger API docs at: http://localhost:8000/docs")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
