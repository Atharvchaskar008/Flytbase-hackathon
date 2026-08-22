"""
Entry point for running backend as a module
Usage: python -m backend
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("Starting TRACE backend via python -m backend")
    print("Use Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
