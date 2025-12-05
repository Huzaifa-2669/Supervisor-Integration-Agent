"""
Entry point for the supervisor demo. FastAPI app is assembled in app.server.
Run with:
  uvicorn main:app --reload
"""
from __future__ import annotations
import uvicorn


from app.server import app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

