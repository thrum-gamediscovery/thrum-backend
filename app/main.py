"""
Main entry point for the FastAPI application.

- Initializes the FastAPI app
- Includes all API routers
- Adds CORS middleware
"""

# app/main.py
from fastapi import FastAPI
from app.middleware.session_middleware import SessionIDMiddleware
from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware
from app.utils.scheduler import start_scheduler

import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.ERROR)

app = FastAPI(title="Thrum Backend")

app.add_middleware(SessionIDMiddleware)

# Allow CORS for all origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include versioned API routes
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    start_scheduler()